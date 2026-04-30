"""
utils/bootstrap.py
Startup helpers that make sure every dashboard has data the moment the user opens it.

Two responsibilities:
  1. seed_if_empty() - if the database is brand-new (no vendors), run the
     synthetic seeder so the user is never staring at empty cards.
  2. ensure_initial_match_state() - if every transaction is unmatched, pair
     internal/bank rows by invoice_id+amount so the reconciliation dashboard
     opens with a realistic match rate instead of 0%.

Both are idempotent and only run when the corresponding signal is "empty".
"""
from __future__ import annotations
import logging
from typing import Iterable

logger = logging.getLogger("fagentllm.bootstrap")

AMOUNT_TOLERANCE = 5.0  # USD; covers seeded FX/rounding noise


def seed_if_empty() -> None:
    """Run the synthetic seeder if vendors is empty. No-op otherwise."""
    from config import get_supabase
    sb = get_supabase()
    try:
        count = sb.table("vendors").select("id", count="exact").limit(1).execute().count or 0
    except Exception as e:
        logger.warning(f"Could not probe vendors table: {e}")
        return

    if count > 0:
        logger.info(f"DB already has {count} vendors; skipping auto-seed.")
        return

    logger.info("Empty database detected; running synthetic seeder…")
    try:
        import seed
        data = seed.generate_all()
        seed.insert_to_supabase(data)
        logger.info("Auto-seed complete.")
    except Exception as e:
        logger.error(f"Auto-seed failed: {e}")


def ensure_initial_match_state() -> None:
    """If no transactions are matched, pair the seeded internal/bank rows."""
    from config import get_supabase
    sb = get_supabase()
    try:
        matched = sb.table("transactions").select("id", count="exact").eq("matched", True).limit(1).execute().count or 0
        total = sb.table("transactions").select("id", count="exact").limit(1).execute().count or 0
    except Exception as e:
        logger.warning(f"Could not probe transactions: {e}")
        return

    if total == 0 or matched > 0:
        # Either no data yet, or recon already ran at least once.
        return

    logger.info("All transactions unmatched; pairing seeded internal/bank rows…")

    try:
        rows = sb.table("transactions").select(
            "id,source,invoice_id,amount,matched"
        ).execute().data or []
    except Exception as e:
        logger.warning(f"Could not pull transactions: {e}")
        return

    by_invoice: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        inv = r.get("invoice_id")
        if not inv:
            continue
        bucket = by_invoice.setdefault(inv, {"internal": [], "bank": []})
        if r.get("source") in bucket:
            bucket[r["source"]].append(r)

    matches: list[tuple[str, str, float]] = []
    for inv_id, bucket in by_invoice.items():
        for it in bucket["internal"]:
            mate = _best_amount_match(it, bucket["bank"])
            if mate is None:
                continue
            score = _score(it["amount"], mate["amount"])
            matches.append((it["id"], mate["id"], score))
            matches.append((mate["id"], it["id"], score))

    if not matches:
        logger.info("No internal/bank pairs found in seed; skipping.")
        return

    # Apply updates one at a time; Supabase doesn't support bulk where IN updates.
    applied = 0
    for tx_id, mate_id, score in matches:
        try:
            sb.table("transactions").update({
                "matched": True,
                "matched_to": mate_id,
                "match_score": round(score, 3),
            }).eq("id", tx_id).execute()
            applied += 1
        except Exception as e:
            logger.warning(f"Could not mark {tx_id}: {e}")

    logger.info(f"Pre-matched {applied // 2} transaction pairs ({applied} rows updated).")


def _best_amount_match(internal: dict, candidates: Iterable[dict]) -> dict | None:
    target = abs(float(internal.get("amount") or 0))
    best, best_diff = None, AMOUNT_TOLERANCE
    for c in candidates:
        diff = abs(abs(float(c.get("amount") or 0)) - target)
        if diff <= best_diff:
            best, best_diff = c, diff
    return best


def _score(a: float | int, b: float | int) -> float:
    a, b = abs(float(a)), abs(float(b))
    if a == 0 or b == 0:
        return 0.85
    diff = abs(a - b) / max(a, b)
    # Tight matches → 0.99; loose (within tolerance) → ~0.86
    return max(0.85, 1.0 - diff * 5)
