"""
agents/reconciliation_agent.py
Reconciliation Agent — this is where we handle matching internal records with bank data.
And we track every match decision in the causal graph.
"""

from __future__ import annotations
import uuid
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json
from utils.prompts import reconciliation_anomaly_prompt

def reconciliation_node(state: FinancialState) -> FinancialState:
    # Just checking if this is a daily or manual run before we start the matching logic
    trigger = state.get("trigger", "daily_reconciliation")
    if trigger in ("daily_reconciliation", "manual_reconciliation"):
        return _run_reconciliation(state)
    return {**state, "next_agent": END, "current_agent": "reconciliation"}

def _run_reconciliation(state: FinancialState) -> FinancialState:
    run_id = str(uuid.uuid4())
    period = _current_period()

    # Fetch real unmatched transactions from Supabase
    all_unmatched = db.get_unmatched_transactions(limit=100)
    
    # Separate internal records from bank records
    internal_txs = [tx for tx in all_unmatched if tx.get("source") == "internal"]
    bank_txs = [tx for tx in all_unmatched if tx.get("source") == "bank"]
    
    if not internal_txs:
        note = f"Reconciliation {period}: No internal transactions to match."
        db.log_agent_decision("reconciliation", "reconciliation_complete", "system", "system", note)
        return {**state, "current_agent": "reconciliation", "next_agent": END}

    matched = []
    anomalies = []

    if bank_txs:
        def tx_to_string(tx):
            # We're mashing the amount, date, and description into one string so the vectorizer can compare them.
            parts = [
                str(tx.get("amount", "")),
                str(tx.get("date", "")),
                str(tx.get("counterparty_id", tx.get("counterparty", ""))),
                str(tx.get("description", ""))
            ]
            return " ".join(parts).lower()
            
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        internal_strings = [tx_to_string(tx) for tx in internal_txs]
        external_strings = [tx_to_string(tx) for tx in bank_txs]
        all_strings = internal_strings + external_strings
        
        vectorizer = TfidfVectorizer()
        vectorizer.fit(all_strings)
        
        internal_vectors = vectorizer.transform(internal_strings)
        external_vectors = vectorizer.transform(external_strings)
        
        # This gives us a similarity matrix comparing internal vs external txs.
        sim_matrix = cosine_similarity(internal_vectors, external_vectors)
        
        # Anything over 0.8 is considered a "match" for this version.
        threshold = 0.8
        
        for i, tx in enumerate(internal_txs):
            if sim_matrix.shape[1] > 0:
                max_sim = np.max(sim_matrix[i])
                tx["sim_score"] = float(max_sim)
                if max_sim >= threshold:
                    matched.append(tx)
                else:
                    anomalies.append(tx)
            else:
                tx["sim_score"] = 0.0
                anomalies.append(tx)
    else:
        # No bank transactions to match against
        for tx in internal_txs:
            tx["sim_score"] = 0.0
        anomalies = internal_txs


    # Analyze anomalies with Qwen3
    system, user = reconciliation_anomaly_prompt(anomalies, period)
    analysis = qwen_json(system, user)
    summary  = analysis.get("summary", "Discrepancies found.")
    systematic = bool(analysis.get("systematic_issue", False))

    # 1. Log the Agent Decision FIRST (to get decision_id for the report)
    decision_id = db.log_agent_decision(
        agent="reconciliation",
        decision_type="reconciliation_complete",
        entity_table="reconciliation_reports",
        entity_id=run_id,
        reasoning=summary,
        input_state={"total_unmatched_internal": len(internal_txs), "total_unmatched_bank": len(bank_txs)},
        output_action={"matched": len(matched), "anomalies": len(anomalies), "systematic": systematic}
    )

    # 2. Create the V3 Reconciliation Report (linked to decision)
    report_id = db.create_reconciliation_report({
        "period": period,
        "total_internal": len(internal_txs),
        "total_external": len(bank_txs),
        "matched_count": len(matched),
        "unmatched_count": len(anomalies),
        "match_rate": (len(matched) / max(1, len(internal_txs))) * 100.0,
        "generated_by_decision_id": decision_id
    })

    # 3. Add Item-level Traceability (V3)
    items = []
    for tx in matched:
        sim_score = tx.get("sim_score", 0.0)
        items.append({"transaction_id": tx["id"], "item_type": "matched", "notes": f"Cosine similarity match score: {sim_score:.2f}"})
    for tx in anomalies:
        sim_score = tx.get("sim_score", 0.0)
        items.append({"transaction_id": tx["id"], "item_type": "discrepancy", "notes": f"Flagged for review. Best similarity score: {sim_score:.2f}"})
    
    db.add_reconciliation_items(report_id, items)

    # If we found a systematic issue, we might want the credit agent to take a look.
    customer_id = _find_customer(anomalies) if systematic else None
    next_agent = "credit" if customer_id else END

    return {
        **state,
        "current_agent": "reconciliation",
        "next_agent":    next_agent,
        "trigger":       "customer_payment_check" if next_agent == "credit" else "done",
        "reconciliation": {
            "run_id": run_id,
            "report_id": report_id,
            "decision_id": decision_id,
            "anomaly_summary": summary
        },
        "credit": { **state.get("credit", {}), "customer_id": customer_id or "" }
    }

def _find_customer(anomalies: list) -> str | None:
    customers = db.select("customers")
    for a in anomalies:
        desc = (a.get("description") or "").lower()
        for c in customers:
            if c["name"].lower() in desc:
                return c["id"]
    return customers[0]["id"] if customers else None

def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
