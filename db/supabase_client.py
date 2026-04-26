
from typing import Any, Dict, List, Optional
from config import get_supabase

class SupabaseDB:
    """
    Database abstraction layer for FAgentLLM.
    Provides simple methods for agents to interact with Supabase tables.
    """

    def __init__(self):
        self.supabase = None

    def _ensure_client(self):
        if self.supabase is None:
            self.supabase = get_supabase()
        return self.supabase

    def create_invoice(self, data: Dict[str, Any]):
        return self._ensure_client().table("invoices").insert(data).execute()

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        result = self._ensure_client().table("invoices").select("*").eq("id", invoice_id).execute()
        return result.data[0] if result.data else None

    def update_invoice_status(self, invoice_id: str, status: str, extra_data: Dict[str, Any] = None):
        update_data = {"status": status}
        if extra_data:
            update_data.update(extra_data)
        return self.update("invoices", {"id": invoice_id}, update_data)

    def update(self, table: str, filters: Dict[str, Any], data: Dict[str, Any]):
        query = self._ensure_client().table(table).update(data)
        for k, v in filters.items():
            query = query.eq(k, v)
        return query.execute()

    def select(self, table: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = self._ensure_client().table(table).select("*")
        for k, v in filters.items():
            query = query.eq(k, v)
        return query.execute().data

    def log_agent_event(self, agent: str, event_type: str, entity_id: str, details: Dict[str, Any], reasoning: str = ""):
        event_data = {
            "agent": agent,
            "event_type": event_type,
            "entity_id": entity_id,
            "details": details,
            "reasoning": reasoning
        }
        return self._ensure_client().table("agent_events").insert(event_data).execute()

# Singleton instance
db = SupabaseDB()
