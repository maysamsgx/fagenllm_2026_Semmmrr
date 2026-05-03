from db.supabase_client import db

def deduplicate_customers():
    print("Fetching all customers...")
    customers = db.select("customers")
    print(f"Initial count: {len(customers)}")
    
    # Group by name
    by_name = {}
    for c in customers:
        name = c['name'].strip()
        if name not in by_name:
            by_name[name] = []
        by_name[name].append(c)
    
    ids_to_delete = []
    for name, records in by_name.items():
        if len(records) > 1:
            # Sort by created_at desc (keep the newest one)
            records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            # Keep index 0, mark the rest for deletion
            for r in records[1:]:
                ids_to_delete.append(r['id'])
    
    print(f"Identified {len(ids_to_delete)} duplicate records to delete.")
    
    if not ids_to_delete:
        print("No duplicates found.")
        return

    # Delete in batches
    batch_size = 50
    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i:i + batch_size]
        print(f"Deleting batch {i//batch_size + 1}...")
        for cid in batch:
            # Note: We need a direct delete method. 
            # If db.delete is not available, we might need to use raw client.
            # I'll check db.py or use the supabase client directly.
            pass

if __name__ == "__main__":
    # I need to verify if 'db' has a delete method.
    # If not, I'll use the raw client.
    from config import get_supabase
    client = get_supabase()
    
    def run_dedupe():
        customers = client.table("customers").select("id, name, created_at").execute().data
        print(f"Initial count: {len(customers)}")
        
        by_name = {}
        for c in customers:
            name = c['name'].strip()
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(c)
        
        ids_to_delete = []
        for name, records in by_name.items():
            if len(records) > 1:
                records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                for r in records[1:]:
                    ids_to_delete.append(r['id'])
        
        print(f"Identified {len(ids_to_delete)} duplicates.")
        
        for cid in ids_to_delete:
            client.table("customers").delete().eq("id", cid).execute()
        
        print(f"Cleanup complete. Deleted {len(ids_to_delete)} records.")
        
        new_count = client.table("customers").select("id", count="exact").execute().count
        print(f"Final unique count: {new_count}")

    run_dedupe()
