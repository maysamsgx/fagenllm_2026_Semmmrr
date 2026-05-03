from db.supabase_client import db

def verify():
    customers = db.select("customers")
    print("Sample mappings:")
    for c in customers[:10]:
        print(f"{c['name']} -> {c['email']}")

if __name__ == "__main__":
    verify()
