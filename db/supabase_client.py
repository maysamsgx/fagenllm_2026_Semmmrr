from typing import Any, Dict, List, Optional
from config import get_supabase

class SupabaseDB:
    """
    Our database layer. We're using this to keep all the Supabase calls in one place
    so the agents don't have to worry about the raw queries.
    """

    def __init__(self):
        self.supabase = None

    def _ensure_client(self):
        if self.supabase is None:
            self.supabase = get_supabase()
        return self.supabase

    # -- Entity Helpers --
    
    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        result = self._ensure_client().table("invoices").select("*, vendors(name)").eq("id", invoice_id).execute()
        return result.data[0] if result.data else None

    def update_invoice_status(self, invoice_id: str, status: str, extra_data: Dict[str, Any] | None = None):
        update_data = {"status": status}
        if extra_data:
            update_data.update(extra_data)
        return self.update("invoices", {"id": invoice_id}, update_data)

    def get_vendor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        result = self._ensure_client().table("vendors").select("*").eq("name", name).execute()
        return result.data[0] if result.data else None

    def ensure_vendor(self, name: str) -> str:
        v = self.get_vendor_by_name(name)
        if v: return v["id"]
        res = self._ensure_client().table("vendors").insert({"name": name}).execute()
        return res.data[0]["id"]

    def get_vendor_risk(self, vendor_id: str) -> Optional[Dict[str, Any]]:
        res = self._ensure_client().table("vendor_risk_scores") \
            .select("*").eq("vendor_id", vendor_id).order("last_assessed", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        res = self._ensure_client().table("customers").select("*").eq("id", customer_id).execute()
        return res.data[0] if res.data else None

    def get_budget(self, department_id: str, period: str) -> Optional[Dict[str, Any]]:
        res = self._ensure_client().table("budgets") \
            .select("*").eq("department_id", department_id).eq("period", period).execute()
        return res.data[0] if res.data else None

    def get_cash_balances(self) -> List[Dict[str, Any]]:
        return self._ensure_client().table("cash_accounts").select("*").execute().data

    def get_unmatched_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._ensure_client().table("transactions") \
            .select("*").eq("matched", False).limit(limit).execute().data

    # -- Reconciliation V3 --

    def create_reconciliation_report(self, data: Dict[str, Any]) -> str:
        res = self.insert("reconciliation_reports", data)
        return res.data[0]["id"]

    def add_reconciliation_items(self, report_id: str, items: List[Dict[str, Any]]):
        for item in items:
            item["report_id"] = report_id
        return self.insert("reconciliation_report_items", items)

    # -- Payments Layer V3 --

    def record_payment(self, invoice_id: str, amount: float, method: str, reference: str = None) -> str:
        data = {
            "invoice_id": invoice_id,
            "amount": amount,
            "method": method,
            "reference": reference,
            "status": "completed"
        }
        res = self.insert("payments", data)
        payment_id = res.data[0]["id"]
        
        # Mark invoice as paid
        self.update_invoice_status(invoice_id, "paid")
        return payment_id

    # -- Generic Operations --

    def update(self, table: str, filters: Dict[str, Any], data: Dict[str, Any]):
        query = self._ensure_client().table(table).update(data)
        for k, v in filters.items():
            query = query.eq(k, v)
        return query.execute()

    def select(self, table: str, filters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        query = self._ensure_client().table(table).select("*")
        if filters:
            for k, v in filters.items():
                query = query.eq(k, v)
        return query.execute().data

    def insert(self, table: str, data: Any):
        return self._ensure_client().table(table).insert(data).execute()

    # -- Intelligence Layers (V2/V3) --

    # This is a key part of our V3 architecture — logging every decision
    # so we can build a causal graph for the audit trail.
    # All explanation fields are optional: pass `reasoning=` as a shortcut
    # when you only have a single message (typically used by error paths).
    def log_agent_decision(self, agent: str, decision_type: str, entity_table: str, entity_id: str,
                           technical_explanation: str | None = None,
                           business_explanation: str | None = None,
                           causal_explanation: str | None = None,
                           reasoning: str | None = None,
                           input_state: Dict[str, Any] | None = None,
                           output_action: Dict[str, Any] | None = None,
                           confidence: float = 100.0) -> str:
        # Fan a single `reasoning` shortcut into all three slots so the trace
        # panel never has an empty event.
        if reasoning and not (technical_explanation or business_explanation or causal_explanation):
            technical_explanation = reasoning
            business_explanation = reasoning
            causal_explanation = reasoning

        snap = self.get_latest_snapshot()
        snap_id = snap["id"] if snap else None

        decision_data = {
            "agent": agent,
            "decision_type": decision_type,
            "entity_table": entity_table,
            "entity_id": entity_id,
            "technical_explanation": technical_explanation or "",
            "business_explanation": business_explanation or "",
            "causal_explanation": causal_explanation or "",
            "input_state": input_state or {},
            "output_action": output_action or {},
            "confidence": confidence,
            "snapshot_id": snap_id
        }
        res = self._ensure_client().table("agent_decisions").insert(decision_data).execute()
        return res.data[0]["id"]

    def log_causal_link(self, cause_id: str, effect_id: str, rel_type: str, explanation: str, strength: float = 1.0):
        link_data = {
            "cause_decision_id": cause_id,
            "effect_decision_id": effect_id,
            "relationship_type": rel_type,
            "explanation": explanation,
            "strength": strength
        }
        return self._ensure_client().table("causal_links").insert(link_data).execute()

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        res = self._ensure_client().table("financial_state_snapshots") \
            .select("*").order("snapshot_time", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

# Singleton instance
db = SupabaseDB()
