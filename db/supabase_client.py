from typing import Any, Dict, List, Optional
import uuid as _uuid_lib
from config import get_supabase

# ── Deterministic UUID namespace — must match erp_seed.py ────────────────────
# uuid5(NAMESPACE_DNS, 'fagent-llm.enterprise.seed') is the same namespace used
# by the seeder so that department UUIDs stay stable across runs.
_SEED_NAMESPACE = _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, 'fagent-llm.enterprise.seed')

def _slug_to_uuid(slug: str) -> str:
    """Derive a stable UUID from a department/entity slug, matching the seeder logic."""
    return str(_uuid_lib.uuid5(_SEED_NAMESPACE, f"dept-{slug}"))

class SupabaseDB:
    """
    Our database layer. We're using this to keep all the Supabase calls in one place
    so the agents don't have to worry about the raw queries.
    """

    def __init__(self):
        self.supabase = None
        self._dept_uuid_cache: Dict[str, str] = {}  # slug -> UUID string

    def _ensure_client(self):
        if self.supabase is None:
            self.supabase = get_supabase()
        return self.supabase

    def get_department_uuid(self, dept_slug: str) -> str:
        """Translate a department slug (e.g. 'marketing') to a stable UUID.

        The departments table uses short string IDs (e.g. 'marketing') as its
        primary key, not UUIDs.  But agent_memory.entity_id is a UUID column,
        so we derive a deterministic UUID from the slug via the same uuid5
        namespace used by erp_seed.py — guaranteeing stability across runs.

        Results are cached so the DB is queried at most once per process.
        """
        if dept_slug in self._dept_uuid_cache:
            return self._dept_uuid_cache[dept_slug]
        # Derive stable UUID from the slug (same formula as seeder's gen_uuid)
        dept_uuid = _slug_to_uuid(dept_slug)
        self._dept_uuid_cache[dept_slug] = dept_uuid
        return dept_uuid

    # -- Entity Helpers --
    
    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        result = self._ensure_client().table("invoices").select("*, vendors(name)").eq("id", invoice_id).execute()
        return result.data[0] if result.data else None

    def find_duplicate_invoice(self, vendor_id: str, invoice_number: str) -> Optional[Dict[str, Any]]:
        """
        Thesis Improvement: Fraud Prevention Layer.
        Checks for an existing invoice with the same vendor and number to prevent double-payment.
        We check for any status that indicates the invoice is being or has been processed.
        """
        res = self._ensure_client().table("invoices") \
            .select("*") \
            .eq("vendor_id", vendor_id) \
            .eq("invoice_number", invoice_number) \
            .in_("status", ["approved", "paid", "awaiting_approval"]) \
            .execute()
        return res.data[0] if res.data else None

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
        vendor_id = res.data[0]["id"]
        # Bootstrap a baseline risk record so downstream checks never see a null score.
        # New vendors have no payment history, so we apply a neutral medium baseline
        # (50/100) until the first reassessment runs.
        try:
            self._ensure_client().table("vendor_risk_scores").insert({
                "vendor_id": vendor_id,
                "risk_score": 50.0,
                "risk_level": "medium",
                "factors": {"reason": "new_vendor_no_history"},
            }).execute()
        except Exception:
            pass
        return vendor_id

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

    def upsert(self, table: str, data: Any):
        return self._ensure_client().table(table).upsert(data).execute()

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
        """Records a directed edge between two agent decisions."""
        link_data = {
            "cause_decision_id": cause_id,
            "effect_decision_id": effect_id,
            "relationship_type": rel_type,
            "explanation": explanation,
            "strength": strength
        }
        return self._ensure_client().table("causal_links").insert(link_data).execute()
    
    # -- Persistent Agent Memory & Vector Patterns (V4) --

    def store_memory(self, agent: str, content: Dict[str, Any], memory_type: str = "episodic", entity_id: str | None = None):
        """Persist an episodic/temporal memory entry.

        entity_id MUST be a valid UUID — callers that hold a department slug
        should call get_department_uuid(slug) first.
        """
        data = {
            "agent": agent,
            "content": content,
            "memory_type": memory_type,
            "entity_id": entity_id,
        }
        try:
            return self.insert("agent_memory", data)
        except Exception as e:
            import logging
            logging.getLogger("fagentllm").warning(f"Could not store memory: {e}")
            return None

    def get_recent_memories(self, agent: str, entity_id: str | None = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch the most-recent memory entries for an agent.

        entity_id MUST be a valid UUID — callers that hold a department slug
        should call get_department_uuid(slug) first.
        """
        try:
            query = self._ensure_client().table("agent_memory").select("*").eq("agent", agent)
            if entity_id:
                query = query.eq("entity_id", entity_id)
            res = query.order("created_at", desc=True).limit(limit).execute()
            return res.data
        except Exception as e:
            import logging
            logging.getLogger("fagentllm").warning(f"Could not fetch memories: {e}")
            return []

    def vector_search_transactions(self, embedding: List[float], threshold: float = 0.7, count: int = 5, source: str = "bank") -> List[Dict[str, Any]]:
        params = {
            "query_embedding": embedding,
            "match_threshold": threshold,
            "match_count": count,
            "p_source": source
        }
        res = self._ensure_client().rpc("match_transactions", params).execute()
        return res.data

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        res = self._ensure_client().table("financial_state_snapshots") \
            .select("*").order("snapshot_time", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def get_research_metrics(self) -> Dict[str, Any]:
        """Calculates real-world performance metrics for the thesis dashboard."""
        client = self._ensure_client()
        
        # 1. Total Liquidity
        accounts = client.table("cash_accounts").select("current_balance").execute().data
        total_cash = sum(a["current_balance"] for a in accounts) / 1_000_000 # In Millions
        
        # 2. Latest Reconciliation Match Rate
        recon = client.table("reconciliation_reports").select("match_rate").order("generated_at", desc=True).limit(1).execute().data
        match_rate = recon[0]["match_rate"] if recon else 0
        
        # 3. AP Health (Paid Invoices)
        paid = client.table("invoices").select("id", count="exact").eq("status", "paid").execute().count or 0
        total_inv = client.table("invoices").select("id", count="exact").execute().count or 1
        
        # 4. Decisions & Links
        dec_count = client.table("agent_decisions").select("id", count="exact").execute().count or 0
        link_count = client.table("causal_links").select("id", count="exact").execute().count or 0

        # DSO = (total open receivables / revenue collected in last 90 days) × 90
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        ar_rows  = client.table("receivables").select("amount").eq("status", "open").execute().data
        pay_rows = client.table("payments").select("amount").gte("payment_date", cutoff).eq("status", "completed").execute().data
        total_ar    = sum(float(r.get("amount", 0)) for r in ar_rows)
        revenue_90d = sum(float(p.get("amount", 0)) for p in pay_rows)
        dso_days = round((total_ar / revenue_90d) * 90, 1) if revenue_90d > 0 else 0.0

        return {
            "liquidity_m": round(total_cash, 1),
            "match_rate": round(float(match_rate), 1),
            "paid_invoices": paid,
            "total_invoices": total_inv,
            "total_decisions": dec_count,
            "total_causal_links": link_count,
            "dso_days": dso_days,
        }

    def get_historical_liquidity(self, limit: int = 12) -> List[Dict[str, Any]]:
        """Fetches historical balance snapshots for trend analysis."""
        snaps = self._ensure_client().table("financial_state_snapshots") \
            .select("snapshot_time, total_cash") \
            .order("snapshot_time", desc=True).limit(limit).execute().data
        # Return in chronological order
        return [{"name": s["snapshot_time"][:10], "val": float(s["total_cash"])/1_000_000} for s in reversed(snaps)]

    def get_forecast_data(self, limit: int = 13) -> List[Dict[str, Any]]:
        """Fetches 13-week cash flow projections."""
        res = self._ensure_client().table("cash_flow_forecasts") \
            .select("forecast_date, projected_inflow, projected_outflow, net_position") \
            .order("forecast_date", desc=False).limit(limit).execute().data
        
        # We need a running total of cash starting from current balance
        accounts = self._ensure_client().table("cash_accounts").select("current_balance").execute().data
        current_liquidity = sum(a["current_balance"] for a in accounts) / 1_000_000

        forecast = []
        running_total = current_liquidity
        for r in res:
            # Simple projection: each week adds the net position
            # Note: net_position is in absolute dollars in DB, convert to M
            net_m = float(r["net_position"] or 0) / 1_000_000
            running_total += net_m
            forecast.append({
                "name": r["forecast_date"],
                "val": round(running_total, 2),
                "inflow": float(r["projected_inflow"] or 0) / 1_000_000,
                "outflow": float(r["projected_outflow"] or 0) / 1_000_000
            })
        
        # If no forecast data in DB, return empty list or some defaults
        return forecast

# Singleton instance
db = SupabaseDB()
