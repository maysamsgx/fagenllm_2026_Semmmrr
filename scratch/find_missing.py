import csv
from config import get_supabase
from pathlib import Path

CLIENTS_CSV = Path("clients.csv")

def find_missing():
    with open(CLIENTS_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader) # skip header
        csv_names = set([row[0].strip() for row in reader if row and row[0].strip()])
    
    client = get_supabase()
    db_customers = client.table("customers").select("name").execute().data
    db_names = set([c['name'].strip() for c in db_customers])
    
    missing = csv_names - db_names
    extra = db_names - csv_names
    
    print(f"CSV unique names: {len(csv_names)}")
    print(f"DB unique names:  {len(db_names)}")
    print(f"Missing in DB:    {len(missing)}")
    if missing:
        print("First 5 missing:")
        for m in list(missing)[:5]:
            print(f" - {m}")
    
    print(f"Extra in DB:      {len(extra)}")
    if extra:
        print("First 5 extra:")
        for e in list(extra)[:5]:
            print(f" - {e}")

if __name__ == "__main__":
    find_missing()
