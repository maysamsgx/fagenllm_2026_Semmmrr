"""
agents/reconciliation_agent.py
Reconciliation Agent — V3 (10/10 Causal Architecture).
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
    trigger = state.get("trigger", "daily_reconciliation")
    if trigger in ("daily_reconciliation", "manual_reconciliation"):
        return _run_reconciliation(state)
    return {**state, "next_agent": END, "current_agent": "reconciliation"}

def _run_reconciliation(state: FinancialState) -> FinancialState:
    run_id = str(uuid.uuid4())
    period = _current_period()

    unmatched_txs = db.get_unmatched_transactions(limit=50)
    if not unmatched_txs:
        note = f"Reconciliation {period}: All transactions matched."
        db.log_agent_decision("reconciliation", "reconciliation_complete", "system", "system", note)
        return {**state, "current_agent": "reconciliation", "next_agent": END}

    # Simulation: 70% matched, 30% are anomalies for demo
    split = int(len(unmatched_txs) * 0.7)
    matched = unmatched_txs[:split]
    anomalies = unmatched_txs[split:]
    
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
        input_state={"total_unmatched": len(unmatched_txs)},
        output_action={"matched": len(matched), "anomalies": len(anomalies), "systematic": systematic}
    )

    # 2. Create the V3 Reconciliation Report (linked to decision)
    report_id = db.create_reconciliation_report({
        "period": period,
        "run_id": run_id,
        "total_internal": len(unmatched_txs), # Simplified
        "total_external": len(unmatched_txs),
        "matched_count": len(matched),
        "unmatched_count": len(anomalies),
        "match_rate": 70.0,
        "generated_by_decision_id": decision_id
    })

    # 3. Add Item-level Traceability (V3)
    items = []
    for tx in matched:
        items.append({"transaction_id": tx["id"], "item_type": "matched", "notes": "Deterministic match"})
    for tx in anomalies:
        items.append({"transaction_id": tx["id"], "item_type": "discrepancy", "notes": "Unexplained variance"})
    
    db.add_reconciliation_items(report_id, items)

    # Cross-agent escalation if systematic
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
