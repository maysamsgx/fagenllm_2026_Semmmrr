"""
agents/reconciliation_agent.py
Reconciliation Agent — matches internal records with bank data and tracks every
decision in the causal graph.

DOE Layer: Orchestration.
  - Matching threshold from directives/policies.py (RECON)
  - LLM analyses anomaly patterns (Orchestration reasoning)
  - All DB writes in Execution phase
  - Directive injected into LLM prompt
"""

from __future__ import annotations
import uuid
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import RECON
from utils.directives import inject_directive


def reconciliation_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "daily_reconciliation")
    if trigger in ("daily_reconciliation", "manual_reconciliation"):
        return _run_reconciliation(state)
    return {**state, "next_agent": END, "current_agent": "reconciliation"}


def _run_reconciliation(state: FinancialState) -> FinancialState:
    run_id = str(uuid.uuid4())
    period = _current_period()

    # ── Perception: fetch unmatched transactions ──────────────────────────────
    all_unmatched = db.get_unmatched_transactions(limit=RECON.max_fetch)
    internal_txs  = [tx for tx in all_unmatched if tx.get("source") == "internal"]
    bank_txs      = [tx for tx in all_unmatched if tx.get("source") == "bank"]

    if not internal_txs:
        note = f"Reconciliation {period}: No internal transactions to match."
        db.log_agent_decision(
            agent="reconciliation", decision_type="reconciliation_complete",
            entity_table="system", entity_id="system",
            technical_explanation=note,
            business_explanation="Reconciliation run completed successfully with no items to process.",
            causal_explanation="No downstream actions required."
        )
        return {**state, "current_agent": "reconciliation", "next_agent": END}

    # ── Orchestration: TF-IDF cosine similarity matching ─────────────────────
    matched   = []
    anomalies = []

    if bank_txs:
        def tx_to_string(tx: dict) -> str:
            parts = [
                str(tx.get("amount", "")),
                str(tx.get("transaction_date", "")),
                str(tx.get("counterparty", "")),
                str(tx.get("description", ""))
            ]
            return " ".join(parts).lower()

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        all_strings      = [tx_to_string(t) for t in internal_txs] + [tx_to_string(t) for t in bank_txs]
        vectorizer       = TfidfVectorizer()
        vectorizer.fit(all_strings)
        internal_vectors = vectorizer.transform([tx_to_string(t) for t in internal_txs])
        external_vectors = vectorizer.transform([tx_to_string(t) for t in bank_txs])
        sim_matrix       = cosine_similarity(internal_vectors, external_vectors)

        for i, tx in enumerate(internal_txs):
            max_sim        = float(np.max(sim_matrix[i])) if sim_matrix.shape[1] > 0 else 0.0
            tx["sim_score"] = max_sim
            if max_sim >= RECON.match_threshold:
                matched.append(tx)
            else:
                anomalies.append(tx)
    else:
        for tx in internal_txs:
            tx["sim_score"] = 0.0
        anomalies = internal_txs

    # ── Orchestration: LLM anomaly analysis with directive context ────────────
    from utils.contracts import DecisionOutput
    from utils.llm import qwen_structured
    from utils.prompts import reconciliation_anomaly_prompt

    base_system, user = reconciliation_anomaly_prompt(anomalies, period)
    system            = inject_directive(base_system, "reconciliation")
    analysis          = qwen_structured(system, user, DecisionOutput)

    systematic = any(
        kw in analysis.technical_explanation.lower()
        for kw in RECON.systematic_keywords
    )

    # ── Explanation: log decision ─────────────────────────────────────────────
    decision_id = db.log_agent_decision(
        agent="reconciliation",
        decision_type="reconciliation_complete",
        entity_table="reconciliation_reports",
        entity_id=run_id,
        technical_explanation=analysis.technical_explanation,
        business_explanation=analysis.business_explanation,
        causal_explanation=analysis.causal_explanation,
        input_state={
            "total_unmatched_internal": len(internal_txs),
            "total_unmatched_bank":     len(bank_txs),
            "match_threshold":          RECON.match_threshold,
        },
        output_action={
            "matched":    len(matched),
            "anomalies":  len(anomalies),
            "systematic": systematic,
        },
        confidence=analysis.confidence,
    )

    trace = state.get("reasoning_trace", []) + [{
        "agent": "reconciliation",
        "step": "Analyse Anomalies",
        "technical_explanation": analysis.technical_explanation,
        "business_explanation": analysis.business_explanation,
        "causal_explanation": analysis.causal_explanation,
    }]

    # ── Execution: write reconciliation report and items ──────────────────────
    report_id = db.create_reconciliation_report({
        "period":          period,
        "total_internal":  len(internal_txs),
        "total_external":  len(bank_txs),
        "matched_count":   len(matched),
        "unmatched_count": len(anomalies),
        "match_rate":      (len(matched) / max(1, len(internal_txs))) * 100.0,
        "generated_by_decision_id": decision_id,
    })

    items = [
        {"transaction_id": tx["id"], "item_type": "matched",
         "notes": f"Cosine similarity: {tx.get('sim_score', 0):.2f}"}
        for tx in matched
    ] + [
        {"transaction_id": tx["id"], "item_type": "discrepancy",
         "notes": f"Below match threshold ({RECON.match_threshold}). Score: {tx.get('sim_score', 0):.2f}"}
        for tx in anomalies
    ]
    db.add_reconciliation_items(report_id, items)

    # ── Communication: route to credit if systematic issue found ─────────────
    # We find ALL customers involved in systematic anomalies
    affected_customer_ids = _find_customers(anomalies) if systematic else []
    
    # If multiple customers are affected, the graph currently only processes one at a time.
    # We'll pick the one with the most anomalies for this run.
    target_customer_id = affected_customer_ids[0] if affected_customer_ids else None
    next_agent  = "credit" if target_customer_id else END

    return {
        **state,
        "current_agent": "reconciliation",
        "next_agent":    next_agent,
        "trigger":       "customer_payment_check" if next_agent == "credit" else "done",
        "reconciliation": {
            "run_id":        run_id,
            "report_id":     report_id,
            "decision_id":   decision_id,
            "anomaly_summary": analysis.business_explanation,
            "anomalous_customer_ids": affected_customer_ids,
        },
        "reasoning_trace": trace,
        "credit": {**state.get("credit", {}), "customer_id": target_customer_id or ""},
    }


def _find_customers(anomalies: list) -> list[str]:
    """Find all unique customer IDs related to the anomalies based on description matching."""
    customers = db.select("customers")
    found_ids = []
    for a in anomalies:
        desc = (a.get("description") or "").lower()
        counterparty = (a.get("counterparty") or "").lower()
        for c in customers:
            name = c["name"].lower()
            if name in desc or name in counterparty:
                if c["id"] not in found_ids:
                    found_ids.append(c["id"])
    return found_ids


def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
