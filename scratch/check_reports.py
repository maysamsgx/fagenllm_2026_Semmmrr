from db.supabase_client import db
import json

def check_reports():
    reports = db.select("reconciliation_reports")
    sorted_reports = sorted(reports, key=lambda x: x.get("generated_at", ""), reverse=True)[:5]
    print(json.dumps(sorted_reports, indent=2))

if __name__ == "__main__":
    check_reports()
