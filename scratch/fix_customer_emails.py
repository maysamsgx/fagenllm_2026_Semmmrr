import re
import unicodedata
from db.supabase_client import db

def normalize_name_to_email(name, existing_emails):
    # Normalize: AHMET TAHA UĞUR -> ahmet taha ugur
    # Remove accents/special chars
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8').lower()
    # Replace anything not alphanumeric with a dot
    base = re.sub(r'[^a-z0-9]+', '.', normalized).strip('.')
    domain = "example.com"
    email = f"{base}@{domain}"
    
    if email not in existing_emails:
        return email
    
    counter = 1
    while True:
        email = f"{base}.{counter}@{domain}"
        if email not in existing_emails:
            return email
        counter += 1

def fix_emails():
    print("Fetching customers...")
    customers = db.select("customers")
    print(f"Found {len(customers)} customers.")
    
    existing_emails = set()
    updates = []
    
    for c in customers:
        old_email = c.get('email')
        new_email = normalize_name_to_email(c['name'], existing_emails)
        existing_emails.add(new_email)
        
        if old_email != new_email:
            updates.append((c['id'], new_email))
    
    print(f"Planning to update {len(updates)} customers.")
    
    # Update in batches of 50 to be safe
    batch_size = 50
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        print(f"Updating batch {i//batch_size + 1}...")
        for cid, email in batch:
            db.update("customers", {"id": cid}, {"email": email})
    
    print("Successfully updated all customer emails.")

if __name__ == "__main__":
    fix_emails()
