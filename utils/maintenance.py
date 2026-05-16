from execution.db.supabase_client import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("budget_healer")

def heal_budgets():
    # Fetch all budgets for the current period (2026-Q2)
    budgets = db.select("budgets", {"period": "2026-Q2"})
    
    for b in budgets:
        util = (b['spent'] + b['committed']) / b['allocated']
        if util > 0.9: # Healing anything above 90%
            new_allocation = (b['spent'] + b['committed']) * 1.2 # Give 20% buffer
            logger.info(f"Healing {b['department_id']}: {util*100:.1f}% util. Boosting {b['allocated']} -> {new_allocation}")
            db.update("budgets", {"id": b['id']}, {"allocated": new_allocation})

if __name__ == "__main__":
    heal_budgets()
