"""
agents/reconciliation_agent.py
Reconciliation Agent — matches internal ledger entries against bank transactions,
then asks Qwen3 to look for systematic patterns in whatever didn't match.

Two-stage matching (both run on every unmatched item):
  1. TF-IDF cosine similarity — fast, catches exact/near-exact text matches
  2. MiniLM sentence embeddings — semantic fallback for fuzzy descriptions
If Qwen3 spots a recurring pattern in the anomalies it escalates to the Credit agent.
Matching thresholds live in directives/policies.py (RECON).
"""

from __future__ import annotations
import uuid
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import RECON
from utils.directives import inject_directive

_SENTENCE_MODEL = None

def get_sentence_model():
    """Load MiniLM on first use — avoids slowing down server startup."""
    global _SENTENCE_MODEL
    if _SENTENCE_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Using a very small but effective open-source model
            _SENTENCE_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            # Fallback to None if not installed; matching will skip semantic stage
            return None
    return _SENTENCE_MODEL


def reconciliation_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "daily_reconciliation")
    if trigger in ("daily_reconciliation", "manual_reconciliation"):
        return _run_reconciliation(state)
    return {**state, "next_agent": END, "current_agent": "reconciliation"}


def _run_reconciliation(state: FinancialState) -> FinancialState:
    run_id = str(uuid.uuid4())
    period = _current_period()

    # ── Perception: fetch unmatched transactions (balanced) ──────────────────
    internal_txs = db.select("transactions", {"matched": False, "source": "internal"})[:RECON.max_fetch]
    bank_txs     = db.select("transactions", {"matched": False, "source": "bank"})[:RECON.max_fetch]

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
                str(abs(float(tx.get("amount", 0)))),
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

        # ── Persistent Memory: Vector-DB-Backed Matching (Stage 2) ───────────────────
        model = get_sentence_model()
        
        for i, tx in enumerate(internal_txs):
            # 1. Ensure embedding exists for internal tx
            emb = tx.get("embedding")
            if not emb and model:
                emb = model.encode(tx_to_string(tx)).tolist()
                db.update("transactions", {"id": tx["id"]}, {"embedding": emb})
                tx["embedding"] = emb
            
            # 2. Vector search in DB for best bank match
            best_sim = 0.0
            match_type = "tfidf"
            
            # Start with TF-IDF from the current batch (Stage 1)
            tfidf_max = float(np.max(sim_matrix[i])) if sim_matrix.shape[1] > 0 else 0.0
            best_sim = tfidf_max
            
            # If TF-IDF is weak, try Vector Search in the DB (Stage 2)
            if best_sim < RECON.match_threshold and emb:
                vector_matches = db.vector_search_transactions(emb, threshold=0.1, count=1, source="bank")
                if vector_matches:
                    v_match = vector_matches[0]
                    if v_match["similarity"] > best_sim:
                        best_sim = v_match["similarity"]
                        match_type = "vector"
            
            tx["sim_score"] = best_sim
            tx["match_type"] = match_type
            
            # Use appropriate threshold
            threshold = RECON.match_threshold if match_type == "tfidf" else RECON.semantic_match_threshold
            
            if best_sim >= threshold:
                tx["matched"] = True
                matched.append(tx)
            else:
                tx["matched"] = False
                anomalies.append(tx)
    else:
        for tx in internal_txs:
            tx["sim_score"] = 0.0
        anomalies = internal_txs

    # ── Orchestration: LLM anomaly analysis with directive context ────────────
    from utils.contracts import ReconciliationOutput
    from utils.llm import qwen_structured
    from utils.prompts import reconciliation_anomaly_prompt

    # Persistent Agent Memory: Read semantic memories for context
    past_anomalies_ctx = ""
    potential_cids = _find_customers(anomalies)
    for cid in potential_cids:
        memories = db.get_recent_memories("reconciliation", cid, limit=1)
        if memories:
            m = memories[0]
            past_anomalies_ctx += f" [Memory: In {m['content'].get('period')}, customer had {m['content'].get('anomaly_count')} anomalies. Note: {m['content'].get('summary')}]"

    base_system, user = reconciliation_anomaly_prompt(anomalies, period)
    if past_anomalies_ctx:
        user = "HISTORICAL CONTEXT: " + past_anomalies_ctx + "\n\n" + user
        
    system            = inject_directive(base_system, "reconciliation")
    analysis          = qwen_structured(system, user, ReconciliationOutput)

    systematic = analysis.is_systematic

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
        "step":  "Reconciliation Analysis",
        "technical_explanation": analysis.technical_explanation,
        "business_explanation":  analysis.business_explanation,
        "causal_explanation":    analysis.causal_explanation,
    }]

    # ── Execution: write reconciliation report and items ──────────────────────
    discrepancy_summary = [
        {
            "id": tx["id"],
            "description": tx.get("description"),
            "amount": tx.get("amount"),
            "match_score": round(tx.get("sim_score", 0), 4),
            "counterparty": tx.get("counterparty")
        }
        for tx in anomalies
    ]

    # ── Execution: update transactions with match scores ──────────────────────
    # V3 Latency Fix: Use bulk upsert instead of individual row updates
    updates = []
    for tx in internal_txs:
        updates.append({
            "id": tx["id"],
            "amount": tx["amount"],
            "transaction_date": tx["transaction_date"],
            "counterparty": tx["counterparty"],
            "description": tx.get("description"),
            "source": tx["source"],
            "cash_account_id": tx.get("cash_account_id"),
            "invoice_id": tx.get("invoice_id"),
            "payment_id": tx.get("payment_id"),
            "match_score": round(tx.get("sim_score", 0), 4),
            "matched": tx.get("matched", False)
        })
    
    if updates:
        try:
            db.upsert("transactions", updates)
        except Exception as e:
            import logging
            logging.getLogger("fagentllm").error(f"Bulk transaction match update failed: {e}")

    # ── Execution: write reconciliation report and items ──────────────────────
    # Fetch global stats for the report to ensure it reflects system-wide accuracy
    sb = db._ensure_client()
    global_total = sb.table("transactions").select("id", count="exact").execute().count or 0
    global_matched = sb.table("transactions").select("id", count="exact").eq("matched", True).execute().count or 0
    global_match_rate = (global_matched / max(1, global_total)) * 100.0

    report_id = db.create_reconciliation_report({
        "period":          period,
        "total_internal":  len(internal_txs),
        "total_external":  len(bank_txs),
        "matched_count":   len(matched),
        "unmatched_count": len(anomalies),
        "match_rate":      global_match_rate, # System-wide rate (now including this run)
        "discrepancies":   discrepancy_summary,
        "generated_by_decision_id": decision_id,
    })

    items = [
        {"transaction_id": tx["id"], "item_type": "matched",
         "notes": f"Match ({tx.get('match_type')}): {tx.get('sim_score', 0):.2f}"}
        for tx in matched
    ] + [
        {"transaction_id": tx["id"], "item_type": "discrepancy",
         "notes": f"Below threshold. Score: {tx.get('sim_score', 0):.2f} ({tx.get('match_type')})"}
        for tx in anomalies
    ]
    db.add_reconciliation_items(report_id, items)

    # ── Communication: route to credit if systematic issue found ─────────────
    # Thesis V4: Multi-Customer Support
    affected_customer_ids = _find_customers(anomalies) if systematic else []
    
    # Calculate granular anomaly metrics per customer
    customer_anomaly_counts = {}
    if systematic:
        for a in anomalies:
            for cid in affected_customer_ids:
                # Find customer record (already fetched in _find_customers)
                cust = next((c for c in db.select("customers") if c["id"] == cid), None)
                if cust:
                    from thefuzz import fuzz
                    name = cust["name"].lower()
                    desc = (a.get("description") or "").lower()
                    cp   = (a.get("counterparty") or "").lower()
                    if fuzz.partial_ratio(name, desc) > 80 or fuzz.partial_ratio(name, cp) > 80:
                        customer_anomaly_counts[cid] = customer_anomaly_counts.get(cid, 0) + 1

        # Record semantic memories
        for cid, count in customer_anomaly_counts.items():
            db.store_memory("reconciliation", {
                "period": period,
                "anomaly_count": count,
                "summary": analysis.business_explanation
            }, memory_type="semantic", entity_id=cid)

    # V4 Orchestration: Pass all flagged customers to the pending list
    pending = affected_customer_ids.copy()
    target_customer_id = pending.pop(0) if pending else None
    next_agent = "credit" if target_customer_id else END

    return {
        **state,
        "current_agent": "reconciliation",
        "next_agent":    next_agent,
        "trigger":       "customer_payment_check" if next_agent == "credit" else "done",
        "pending_risk_assessments": pending, # Remaining customers for the loop
        "processed_risk_assessments": [],
        "reconciliation": {
            "run_id":        run_id,
            "report_id":     report_id,
            "decision_id":   decision_id,
            "anomaly_summary": analysis.business_explanation,
            "anomalous_customer_ids": affected_customer_ids,
            "customer_anomaly_counts": customer_anomaly_counts,
        },
        "reasoning_trace": trace,
        "credit": {**state.get("credit", {}), "customer_id": target_customer_id or ""},
    }


def _find_customers(anomalies: list) -> list[str]:
    """Find all unique customer IDs related to the anomalies using fuzzy matching."""
    from thefuzz import fuzz
    customers = db.select("customers")
    found_ids = []
    for a in anomalies:
        desc = (a.get("description") or "").lower()
        counterparty = (a.get("counterparty") or "").lower()
        for c in customers:
            name = c["name"].lower()
            # Catch partial matches (e.g. "Acme Corp" matches "Acme Corporation payment")
            if fuzz.partial_ratio(name, desc) > 80 or fuzz.partial_ratio(name, counterparty) > 80:
                if c["id"] not in found_ids:
                    found_ids.append(c["id"])
    return found_ids


def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
