import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in environment.")
    exit(1)

SQL = """
ALTER TABLE agent_decisions 
DROP COLUMN IF EXISTS reasoning;

ALTER TABLE agent_decisions 
ADD COLUMN IF NOT EXISTS technical_explanation TEXT,
ADD COLUMN IF NOT EXISTS business_explanation TEXT,
ADD COLUMN IF NOT EXISTS causal_explanation TEXT;
"""

def run_migration():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
            conn.commit()
        print("Migration applied successfully.")
    except Exception as e:
        print(f"Error applying migration: {e}")

if __name__ == "__main__":
    run_migration()
