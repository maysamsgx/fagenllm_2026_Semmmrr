"""
scripts/warm_vectors.py
Pre-computes MiniLM embeddings for all transactions that are missing them.

Run this once after seeding the DB (or after importing new transaction batches)
so that pgvector semantic search in Stage 2 has full coverage.

IMPORTANT: uses tx_to_string() from the reconciliation agent to guarantee that
the text encoding here is byte-for-byte identical to what the agent encodes at
query time.  Divergent encodings produce cosine similarity ~0 and break Stage 2.
"""

from agents.reconciliation_agent import get_sentence_model, tx_to_string
from db.supabase_client import db
from dotenv import load_dotenv

load_dotenv()


def warm_vectors():
    print("Initializing Vector Warming Protocol (V4)...")
    model = get_sentence_model()
    if not model:
        print("Error: Could not load sentence-transformer model.")
        return

    client = db._ensure_client()
    total  = 0
    while True:
        rows = (client.table("transactions")
                .select("id, description, counterparty, amount, transaction_date")
                .is_("embedding", "null")
                .limit(50)
                .execute().data)
        if not rows:
            print(f"All vectors are warmed! ({total} rows updated)")
            break

        print(f"Processing batch of {len(rows)} items...")
        for r in rows:
            try:
                emb = model.encode(tx_to_string(r)).tolist()
                client.table("transactions").update({"embedding": emb}).eq("id", r["id"]).execute()
                total += 1
            except Exception as e:
                print(f"Failed to update {r['id']}: {e}")

        print(f"Batch completed. Running total: {total}")


if __name__ == "__main__":
    warm_vectors()
