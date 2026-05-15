from config import get_supabase
sb = get_supabase()

# Credit for current run
credit_id = "0da9314b-40a9-46bc-b65c-d0f934e2bb78"
credit = sb.table("agent_decisions").select("*").eq("id", credit_id).execute().data[0]
customer_id = credit["entity_id"]
print(f"Credit: {credit['created_at']} | customer={customer_id}")

# Cash decisions for this customer around the same time
cash = (sb.table("agent_decisions")
        .select("id,agent,decision_type,entity_id,created_at")
        .eq("agent", "cash")
        .gte("created_at", credit["created_at"])
        .order("created_at")
        .limit(5)
        .execute().data)
print(f"\nCash decisions after credit ({credit['created_at']}):")
for c in cash:
    print(f"  {c['created_at']} | {c['decision_type']} | {c['entity_id']}")

# Governance decisions after credit
gov = (sb.table("agent_decisions")
       .select("id,agent,decision_type,entity_id,created_at")
       .eq("agent", "governance")
       .gte("created_at", credit["created_at"])
       .order("created_at")
       .limit(5)
       .execute().data)
print(f"\nGovernance decisions after credit:")
for g in gov:
    print(f"  {g['created_at']} | {g['decision_type']} | id={g['id']}")
    links = (sb.table("causal_links")
             .select("cause_decision_id,effect_decision_id,relationship_type")
             .or_(f"cause_decision_id.eq.{g['id']},effect_decision_id.eq.{g['id']}")
             .execute().data)
    for l in links:
        print(f"    link: {l['cause_decision_id']} --{l['relationship_type']}--> {l['effect_decision_id']}")
