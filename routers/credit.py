from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from db.supabase_client import db
from config import get_supabase

router = APIRouter()

@router.get("/customers")
def list_customers(risk_level: str = Query(None)):
    supabase = get_supabase()
    query = supabase.table("customers").select("*")
    if risk_level:
        query = query.eq("risk_level", risk_level)
    rows = query.execute().data
    
    # Deduplicate by name (V2 fix for seeder duplicates)
    seen_names = set()
    deduped = []
    # Sort by created_at desc so we get the most recent record for a name
    sorted_rows = sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)
    for r in sorted_rows:
        name = r["name"].strip()
        if name not in seen_names:
            seen_names.add(name)
            deduped.append(r)
            
    # Calculate real total_outstanding and average delay from receivables
    receivables = supabase.table("receivables").select("customer_id, amount, status, due_date").execute().data
    customer_id_to_name = {r["id"]: r["name"].strip() for r in rows}
    
    outstandings_by_name = {}
    delays_by_name = {}
    delay_counts_by_name = {}

    from datetime import date
    today = date.today()

    for rec in receivables:
        cid = rec["customer_id"]
        name = customer_id_to_name.get(cid)
        if name:
            if rec.get("status") == "open":
                outstandings_by_name[name] = outstandings_by_name.get(name, 0.0) + float(rec.get("amount", 0) or 0)
            
            # Dynamic delay calculation for open invoices
            if rec.get("status") in ("open", "partial"):
                due_date_str = rec.get("due_date")
                if due_date_str:
                    try:
                        due = date.fromisoformat(str(due_date_str).split("T")[0])
                        delay = (today - due).days
                        if delay > 0:
                            delays_by_name[name] = delays_by_name.get(name, 0) + delay
                            delay_counts_by_name[name] = delay_counts_by_name.get(name, 0) + 1
                    except Exception:
                        pass
            
    for d in deduped:
        d_name = d["name"].strip()
        d["total_outstanding"] = outstandings_by_name.get(d_name, 0.0)
        
        count = delay_counts_by_name.get(d_name, 0)
        if count > 0:
            d["payment_delay_avg"] = delays_by_name.get(d_name, 0) / count
        else:
            d["payment_delay_avg"] = 0.0
        
    return deduped

@router.get("/aging")
def get_aging_buckets():
    from datetime import date
    today = date.today()
    supabase = get_supabase()
    rows = supabase.table("receivables").select("amount, due_date, status").eq("status", "open").execute().data

    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for r in rows:
        try:
            due = date.fromisoformat(str(r["due_date"]))
            overdue = (today - due).days
            amount = float(r.get("amount", 0) or 0)
            if overdue <= 0:
                buckets["current"] += amount
            elif overdue <= 30:
                buckets["1_30"] += amount
            elif overdue <= 60:
                buckets["31_60"] += amount
            elif overdue <= 90:
                buckets["61_90"] += amount
            else:
                buckets["over_90"] += amount
        except Exception:
            pass

    return {
        "buckets": {k: round(v, 2) for k, v in buckets.items()},
        "total_open": round(sum(buckets.values()), 2),
        "currency": "USD"
    }

@router.get("/trace/{customer_id}")
def get_credit_trace(customer_id: str):
    """V3: Standardized trace format for Credit Agent reasoning."""
    decisions = db.select("agent_decisions", {"entity_id": customer_id, "agent": "credit"})
    decisions = sorted(decisions, key=lambda d: d.get("created_at", ""))
    
    # Map to TraceEvent format
    trace = [
        {
            "agent": d.get("agent"),
            "event_type": d.get("decision_type"),
            "timestamp": d.get("created_at"),
            "technical_explanation": d.get("technical_explanation"),
            "business_explanation": d.get("business_explanation"),
            "causal_explanation": d.get("causal_explanation"),
            "reasoning": d.get("technical_explanation") or d.get("reasoning") or "",
            "details": {
                "score": d.get("output_action", {}).get("score"),
                "risk_level": d.get("output_action", {}).get("risk_level"),
                "confidence": d.get("confidence"),
                "input": d.get("input_state") or {},
                "output": d.get("output_action") or {},
            },
        }
        for d in decisions
    ]
    
    # Fetch customer name for the UI header
    customer = db.select("customers", {"id": customer_id})
    customer_name = customer[0].get("name", "Unknown") if customer else "Unknown"

    return {
        "decisions": decisions,
        "links": [], 
        "trace": trace,
        "name": customer_name
    }

@router.post("/assess/{customer_id}")
def assess_customer(customer_id: str):
    """Synchronous assessment for immediate UI feedback."""
    from agents.graph import graph
    from agents.state import initial_state
    
    try:
        # Pass customer_id as entity_id so initial_state sets trigger_entity_id correctly
        state = initial_state("customer_payment_check", customer_id)
        
        # Invoke the graph synchronously
        final_state = graph.invoke(state)
        
        if final_state.get("error"):
            raise HTTPException(status_code=400, detail=final_state["error"])

        # Extract the credit results from the final state
        credit_res = final_state.get("credit", {})
        decision_id = credit_res.get("decision_id")
        
        # Fetch the full decision object for the UI
        decision = None
        if decision_id:
            rows = db.select("agent_decisions", {"id": decision_id})
            if rows:
                decision = rows[0]
                
        return {
            "status": "complete",
            "score": credit_res.get("credit_score"),
            "risk_level": credit_res.get("risk_level"),
            "decision": decision
        }
    except Exception as e:
        import logging
        logging.getLogger("fagentllm").error(f"Credit assessment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
