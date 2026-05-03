from db.supabase_client import db
import json

report_id = "dcba4d0b-2dac-4f22-9a4b-96f80aca2db2"
report = db.select("reconciliation_reports", {"id": report_id})
print("REPORT:")
print(json.dumps(report, indent=2))

decision_id = report[0]["generated_by_decision_id"]
decision = db.select("agent_decisions", {"id": decision_id})
print("\nDECISION:")
print(json.dumps(decision, indent=2))
