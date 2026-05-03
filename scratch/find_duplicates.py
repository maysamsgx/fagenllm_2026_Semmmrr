
from db.supabase_client import db
from collections import Counter

customers = db.select('customers')
names = [c['name'] for c in customers]
name_counts = Counter(names)
duplicates = {name: count for name, count in name_counts.items() if count > 1}

print(f"Found {len(duplicates)} duplicate names.")
for name, count in list(duplicates.items())[:10]:
    print(f"Name: {name}, Count: {count}")

# Let's also check IDs for one duplicate
if duplicates:
    first_dup = list(duplicates.keys())[0]
    ids = [c['id'] for c in customers if c['name'] == first_dup]
    print(f"IDs for '{first_dup}': {ids}")
