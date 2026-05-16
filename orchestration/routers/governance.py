from fastapi import APIRouter
from execution.db.supabase_client import db

router = APIRouter()

@router.get("/violations")
def get_violations():
    """Fetch all policy violations logged by the Governance agent."""
    violations = db.select("governance_violations")
    # Sort by creation time (latest first)
    return sorted(violations, key=lambda x: x.get("created_at", ""), reverse=True)

@router.get("/audit-log")
def get_audit_log():
    """Fetch history of audit decisions made by the Governance agent."""
    # Filter agent_decisions for governance agent
    audits = db.select("agent_decisions", {"agent": "governance"})
    return sorted(audits, key=lambda x: x.get("created_at", ""), reverse=True)

@router.get("/stats")
def get_governance_stats():
    """Aggregate statistics for governance reporting."""
    violations = db.select("governance_violations")
    audits = db.select("agent_decisions", {"agent": "governance"})
    
    severity_counts = {"low": 0, "medium": 0, "high": 0}
    for v in violations:
        sev = v.get("severity", "medium")
        if sev in severity_counts:
            severity_counts[sev] += 1
            
    avg_compliance = 0
    if audits:
        scores = [float(a.get("output_action", {}).get("compliance_score", 0)) for a in audits if isinstance(a.get("output_action"), dict)]
        if scores:
            avg_compliance = sum(scores) / len(scores)
            
    return {
        "total_violations": len(violations),
        "total_audits": len(audits),
        "violation_rate": round((len(violations) / max(1, len(audits))) * 100, 1),
        "avg_compliance_score": round(avg_compliance, 1),
        "severity_distribution": severity_counts
    }
