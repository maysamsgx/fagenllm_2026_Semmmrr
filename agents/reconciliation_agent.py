"""
agents/reconciliation_agent.py
Reconciliation Agent — matches internal ledger entries against bank transactions,
then asks Qwen3 to look for systematic patterns in whatever didn't match.

Two-stage matching (both run on every unmatched item):
  1. TF-IDF cosine similarity — fast, catches exact/near-exact text matches
  2. MiniLM sentence embeddings — semantic fallback for fuzzy descriptions
If Qwen3 spots a recurring pattern in the anomalies it escalates to the Credit agent.
Matching thresholds live in directives/policies.py (RECON).
"""

from __future__ import annotations
import uuid
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState
from config import get_supabase
from db.supabase_client import db
from directives.policies import RECON
from utils.directives import inject_directive

# Nil UUID used for system-level decisions that have no real entity row.
_NIL_UUID = "00000000-0000-0000-0000-000000000000"

_SENTENCE_MODEL = None


def get_sentence_model():
    """Load MiniLM on first use — avoids slowing down server startup."""
    global _SENTENCE_MODEL
    if _SENTENCE_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SENTENCE_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            return None
    return _SENTENCE_MODEL


def tx_to_string(tx: dict) -> str:
    """Canonical text representation used for both TF-IDF and embedding encoding.

    Must be kept in sync with warm_vectors.py — both must produce identical strings
    so that offline-warmed embeddings match the live-encoded query vectors.
    """
    parts = [
        str(abs(float(tx.get("amount") or 0))),
        str(tx.get("transaction_date", "")),
        str(tx.get("counterparty", "")),
        str(tx.get("description", ""))
    ]
    text = " ".join(parts).lower()
    for noise in ["payment", "for", "wire", "ach", "transfer", "in", "out"]:
        text = text.replace(f" {noise} ", " ")
    return text.strip()


def reconciliation_node(state: FinancialState) -> FinancialState:
    try:
        trigger = state.get("trigger", "daily_reconciliation")
        if trigger in ("daily_reconciliation", "manual_reconciliation", "reconciliation_requested"):
            return _run_reconciliation(state)
        return {**state, "next_agent": END, "current_agent": "reconciliation"}
    except Exception as e:
        import logging
        import traceback
        logging.getLogger("fagentllm").error(f"Reconciliation agent crashed: {e}\n{traceback.format_exc()}")
        try:
            db.log_agent_decision(
                agent="reconciliation",
                decision_type="error",
                entity_table="system",
                entity_id=_NIL_UUID,
                technical_explanation=f"Reconciliation agent encountered a critical error: {str(e)}",
                business_explanation="The reconciliation process was interrupted due to a technical failure. Automatic matching has paused.",
                causal_explanation="Matching report not generated. Manual review of bank feeds is recommended.",
                confidence=0.0
            )
        except Exception as log_e:
            logging.getLogger("fagentllm").error(f"Failed to log crash decision: {log_e}")
        return {**state, "next_agent": END, "current_agent": "reconciliation", "error": str(e)}


def _run_reconciliation(state: FinancialState) -> FinancialState:
    run_id = str(uuid.uuid4())
    period = _current_period()

    # ── Perception: fetch unmatched transactions with DB-level limit ──────────
    internal_txs = db.select("transactions", {"matched": False, "source": "internal"}, limit=RECON.max_fetch)
    bank_txs     = db.select("transactions", {"matched": False, "source": "bank"},     limit=RECON.max_fetch)

    perception_id = db.log_agent_decision(
        agent="reconciliation",
        decision_type="perception",
        entity_table="reconciliation_reports",
        entity_id=run_id,
        technical_explanation=f"Fetched {len(internal_txs)} internal and {len(bank_txs)} bank transactions for matching.",
        business_explanation=f"Reconciliation engine initialized for {period}.",
        causal_explanation="Matching pipeline started. TF-IDF and Semantic stages active.",
        confidence=100.0
    )

    if not internal_txs:
        note = f"Reconciliation {period}: No internal transactions to match."
        completion_id = db.log_agent_decision(
            agent="reconciliation", decision_type="reconciliation_complete",
            entity_table="system", entity_id=_NIL_UUID,
            technical_explanation=note,
            business_explanation="Reconciliation run completed successfully with no items to process.",
            causal_explanation="No downstream actions required."
        )
        db.log_causal_link(perception_id, completion_id, "precedes", "No data to match.")
        return {**state, "current_agent": "reconciliation", "next_agent": END}

    # ── Orchestration: 4-Stage Reconciliation Pipeline ────────────────────────
    matched          = []
    anomalies        = []
    matched_bank_ids = set()

    # Stage 0: Pattern Memory (Episodic)
    known_patterns = db.get_recent_memories("reconciliation", None, limit=10)

    if bank_txs:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        model = get_sentence_model()

        # Pre-compute embeddings for bank transactions that are missing them.
        # Batch-encode all at once (SentenceTransformer is vectorised internally)
        # then write a single upsert — avoids N individual HTTP round-trips to Supabase.
        if model:
            missing_bank = [b for b in bank_txs if not b.get("embedding")]
            if missing_bank:
                try:
                    texts = [tx_to_string(b) for b in missing_bank]
                    batch_embs = model.encode(texts, batch_size=64, show_progress_bar=False)
                    embed_updates = []
                    for b, emb in zip(missing_bank, batch_embs):
                        b["embedding"] = emb.tolist()
                        embed_updates.append({"id": b["id"], "embedding": b["embedding"]})
                    db.upsert("transactions", embed_updates)
                except Exception:
                    pass

        all_strings      = [tx_to_string(t) for t in internal_txs] + [tx_to_string(t) for t in bank_txs]
        vectorizer       = TfidfVectorizer()
        vectorizer.fit(all_strings)
        internal_vectors = vectorizer.transform([tx_to_string(t) for t in internal_txs])
        external_vectors = vectorizer.transform([tx_to_string(t) for t in bank_txs])
        sim_matrix       = cosine_similarity(internal_vectors, external_vectors)

        counts = {"pattern": 0, "tfidf": 0, "vector": 0, "fx": 0}
        # Collect internal-tx embedding saves so we can batch-write after the loop
        # instead of issuing one Supabase UPDATE per transaction.
        pending_embed_saves: list[dict] = []

        for i, tx in enumerate(internal_txs):
            # Stage 0: check against known counterparty patterns from memory
            matched_by_pattern = False
            for p in known_patterns:
                p_data = p.get("content", {})
                if (p_data.get("counterparty") == tx.get("counterparty") and
                        p_data.get("type") == "fixed_delta"):
                    delta = p_data.get("delta", 0)
                    target_amt = float(tx.get("amount") or 0) + delta
                    for btx in bank_txs:
                        if btx["id"] in matched_bank_ids:
                            continue
                        if abs(float(btx.get("amount") or 0) - target_amt) < 0.01:
                            tx["matched"]    = True
                            tx["sim_score"]  = 1.0
                            tx["match_type"] = f"pattern_{p_data.get('reason', 'rule')}"
                            tx["matched_to"] = btx["id"]
                            btx["matched"]   = True
                            btx["sim_score"] = 1.0
                            matched_bank_ids.add(btx["id"])
                            matched.append(tx)
                            matched.append(btx)
                            counts["pattern"] += 1
                            matched_by_pattern = True
                            break
                if matched_by_pattern:
                    break
            if matched_by_pattern:
                continue

            # Compute embedding for this internal tx on demand.
            # Save is deferred — we batch-upsert all new embeddings after the loop.
            emb = tx.get("embedding")
            if not emb and model:
                try:
                    emb = model.encode(tx_to_string(tx)).tolist()
                    tx["embedding"] = emb
                    pending_embed_saves.append({"id": tx["id"], "embedding": emb})
                except Exception:
                    pass

            best_sim       = 0.0
            match_type     = "tfidf"
            best_candidate = None

            # Stage 1: TF-IDF cosine similarity
            if sim_matrix.shape[1] > 0:
                candidate_indices = np.argsort(sim_matrix[i])[::-1]
                for idx in candidate_indices:
                    cand = bank_txs[idx]
                    if cand["id"] not in matched_bank_ids:
                        best_sim       = float(sim_matrix[i][idx])
                        best_candidate = cand
                        break

            # Stage 2: In-memory cosine similarity over unmatched bank transactions.
            # Replaces the pgvector RPC which searched ALL bank rows (matched + unmatched).
            # With most rows already matched, count=5 results were exhausted by matched rows
            # before reaching the genuinely-unmatched candidates. In-memory scan is also
            # faster (no network round-trip) and only touches the current unmatched set.
            if best_sim < RECON.match_threshold and emb:
                emb_arr = np.array(emb, dtype=np.float32)
                for btx in bank_txs:
                    if btx["id"] in matched_bank_ids:
                        continue
                    btx_emb = btx.get("embedding")
                    if not btx_emb:
                        continue
                    btx_arr = np.array(btx_emb, dtype=np.float32)
                    denom = np.linalg.norm(emb_arr) * np.linalg.norm(btx_arr)
                    sim = float(np.dot(emb_arr, btx_arr) / denom) if denom > 1e-10 else 0.0
                    if sim > best_sim:
                        best_sim       = sim
                        match_type     = "vector"
                        best_candidate = btx

            tx["sim_score"]  = best_sim
            tx["match_type"] = match_type

            threshold = RECON.match_threshold if match_type == "tfidf" else RECON.semantic_match_threshold

            if best_sim >= threshold and best_candidate:
                tx["matched"]              = True
                tx["matched_to"]           = best_candidate["id"]
                best_candidate["matched"]  = True
                best_candidate["sim_score"] = best_sim
                matched_bank_ids.add(best_candidate["id"])
                matched.append(tx)
                matched.append(best_candidate)
                counts[match_type] += 1
            else:
                # Stage 3: FX Variance — catches transactions where amounts differ
                # by a small FX fluctuation but text/embedding similarity is high.
                if best_candidate and best_sim >= 0.6:
                    internal_amt = abs(float(tx.get("amount") or 0))
                    bank_amt     = abs(float(best_candidate.get("amount") or 0))
                    variance     = abs(internal_amt - bank_amt) / max(1, internal_amt)
                    if variance <= RECON.fx_tolerance:
                        tx["matched"]              = True
                        tx["match_type"]           = "fx_variance"
                        tx["sim_score"]            = 1.0 - variance
                        tx["matched_to"]           = best_candidate["id"]
                        best_candidate["matched"]  = True
                        best_candidate["sim_score"] = 1.0 - variance
                        matched_bank_ids.add(best_candidate["id"])
                        matched.append(tx)
                        matched.append(best_candidate)
                        counts["fx"] += 1
                        continue

                tx["matched"]   = False
                tx["sim_score"] = best_sim
                anomalies.append(tx)

        # Flush deferred internal-tx embeddings in one batch — single HTTP round-trip.
        if pending_embed_saves:
            try:
                db.upsert("transactions", pending_embed_saves)
            except Exception:
                pass

        # Bank transactions with no internal counterpart are also anomalies
        for btx in bank_txs:
            if btx["id"] not in matched_bank_ids:
                btx["matched"]   = False
                btx["sim_score"] = btx.get("sim_score", 0.0)
                anomalies.append(btx)

        technical_summary = (
            f"Processed {len(internal_txs)} transactions across 4 stages: "
            f"Patterns: {counts['pattern']}, TF-IDF: {counts['tfidf']}, "
            f"Vector: {counts['vector']}, FX: {counts['fx']}. "
            f"{len(anomalies)} anomalies identified."
        )
    else:
        for tx in internal_txs:
            tx["sim_score"] = 0.0
        anomalies        = internal_txs
        technical_summary = "No bank transactions available for matching; all internal items flagged as anomalies."

    # ── Orchestration: LLM anomaly analysis ────────────────────────────────────
    from utils.contracts import ReconciliationOutput
    from utils.llm import qwen_structured
    from utils.prompts import reconciliation_anomaly_prompt

    # Fast-path: if everything matched, skip the LLM call entirely.
    # Qwen3 on Groq free tier is the single largest latency contributor (~60-120 s
    # under rate pressure). There is nothing for the LLM to analyse when the
    # anomaly list is empty, so this saves the round-trip unconditionally.
    if not anomalies:
        from utils.contracts import ReconciliationOutput as _RO
        analysis = _RO(
            decision="reconciliation_complete",
            is_systematic=False,
            technical_explanation=technical_summary,
            business_explanation="All transactions matched successfully. No anomalies to analyse.",
            causal_explanation="No escalation required.",
            confidence=100.0,
        )
        systematic = False
    else:
        # Cap the anomaly sample sent to the LLM: top 10 by absolute amount.
        # Sending all 100 anomalies burns tokens and slows the response without
        # improving pattern detection — the LLM only needs enough signal to
        # identify a root cause, not an exhaustive list.
        llm_sample = sorted(anomalies, key=lambda x: abs(float(x.get("amount") or 0)), reverse=True)[:10]

        past_anomalies_ctx = ""
        potential_cids = _find_customers(anomalies)[:3]
        for cid in potential_cids:
            memories = db.get_recent_memories("reconciliation", cid, limit=1)
            if memories:
                m = memories[0]
                past_anomalies_ctx += f" [Memory: {m['content'].get('period')} customer had {m['content'].get('anomaly_count')} anomalies]"

        base_system, user = reconciliation_anomaly_prompt(llm_sample, period)
        if past_anomalies_ctx:
            user = "HISTORICAL CONTEXT: " + past_anomalies_ctx + "\n\n" + user

        system = inject_directive(base_system, "reconciliation")
        try:
            analysis = qwen_structured(system, user, ReconciliationOutput)
        except Exception as llm_err:
            import logging
            logging.getLogger("fagentllm").warning(
                f"LLM analysis failed or timed out ({llm_err}); using fallback."
            )
            analysis = ReconciliationOutput(
                is_systematic=False,
                technical_explanation=technical_summary,
                business_explanation=(
                    f"{len(anomalies)} anomalies could not be analysed by LLM "
                    "(timeout or rate limit). Manual review recommended."
                ),
                causal_explanation="LLM call failed; no systematic pattern determined.",
                confidence=0.0,
            )

        systematic = analysis.is_systematic
        if not systematic:
            reasoning_text = (analysis.technical_explanation + analysis.causal_explanation).lower()
            if any(kw in reasoning_text for kw in ["pattern", "systematic", "recurring", "ingestion"]):
                systematic = True

    # ── Explanation: log decision ─────────────────────────────────────────────
    decision_id = db.log_agent_decision(
        agent="reconciliation",
        decision_type="reconciliation_complete",
        entity_table="reconciliation_reports",
        entity_id=run_id,
        technical_explanation=technical_summary,
        business_explanation=analysis.business_explanation,
        causal_explanation=analysis.causal_explanation,
        input_state={
            "total_unmatched_internal": len(internal_txs),
            "total_unmatched_bank":     len(bank_txs),
            "match_threshold":          RECON.match_threshold,
        },
        output_action={
            "matched_pairs": len(matched) // 2,
            "anomalies":     len(anomalies),
            "systematic":    systematic,
        },
        confidence=analysis.confidence,
    )

    db.log_causal_link(perception_id, decision_id, "precedes", "Perception informed the final reconciliation match result.")

    trace = state.get("reasoning_trace", []) + [{
        "agent": "reconciliation",
        "step":  "Reconciliation Analysis",
        "technical_explanation": technical_summary,
        "business_explanation":  analysis.business_explanation,
        "causal_explanation":    analysis.causal_explanation,
    }]

    # ── Execution: persist match results to DB ────────────────────────────────
    # Only send real DB columns — runtime-only keys (sim_score, match_type,
    # embedding) are not DB columns and cause PostgREST to reject the whole batch.
    _DB_TX_COLS = {
        "id", "source", "reference", "amount", "currency", "transaction_date",
        "description", "counterparty", "invoice_id", "cash_account_id",
        "matched", "matched_to", "match_score", "discrepancy_flag", "discrepancy_type",
    }

    def _clean(tx: dict, matched: bool, mate_id: str | None, score: float) -> dict:
        base = {k: v for k, v in tx.items() if k in _DB_TX_COLS}
        base["matched"]     = matched
        base["matched_to"]  = mate_id
        base["match_score"] = round(score, 4)
        return base

    updates = []
    for tx in internal_txs:
        updates.append(_clean(tx, tx.get("matched", False), tx.get("matched_to"), tx.get("sim_score", 0)))

    # Use matched_bank_ids (the authoritative set) rather than tx.get("matched")
    # so that Stage 2 / Stage 3 bank-side matches are always included.
    for tx in bank_txs:
        if tx["id"] in matched_bank_ids:
            updates.append(_clean(tx, True, tx.get("matched_to"), tx.get("sim_score", 0)))

    if updates:
        try:
            db.upsert("transactions", updates)
        except Exception as e:
            import logging
            logging.getLogger("fagentllm").error(f"Bulk transaction match update failed: {e}")

    # ── Execution: write reconciliation report ────────────────────────────────
    sb = get_supabase()
    global_total   = sb.table("transactions").select("id", count="exact").execute().count or 0
    global_matched = sb.table("transactions").select("id", count="exact").eq("matched", True).execute().count or 0
    global_match_rate = (global_matched / max(1, global_total)) * 100.0

    discrepancy_summary = [
        {
            "id":          tx["id"],
            "description": tx.get("description"),
            "amount":      tx.get("amount"),
            "match_score": round(tx.get("sim_score", 0), 4),
            "counterparty": tx.get("counterparty")
        }
        for tx in anomalies
    ]

    report_id = db.create_reconciliation_report({
        "period":          period,
        "total_internal":  len(internal_txs),
        "total_external":  len(bank_txs),
        "matched_count":   len(matched) // 2,
        "unmatched_count": len(anomalies),
        "match_rate":      global_match_rate,
        "discrepancies":   discrepancy_summary,
        "generated_by_decision_id": decision_id,
    })

    items = []
    for tx in matched:
        items.append({
            "transaction_id": tx["id"],
            "item_type": "matched",
            "notes": f"Match: {tx.get('sim_score', 0):.2f} ({tx.get('match_type', 'unknown')})"
        })
    for tx in anomalies:
        items.append({
            "transaction_id": tx["id"],
            "item_type": "discrepancy",
            "notes": f"Unmatched. Score: {tx.get('sim_score', 0):.2f}"
        })

    db.add_reconciliation_items(report_id, items)

    # ── Communication: route to credit if systematic issue found ─────────────
    affected_customer_ids   = _find_customers(anomalies) if systematic else []
    customer_anomaly_counts = {}

    if systematic:
        all_customers = db.select("customers")
        customer_map  = {c["id"]: c for c in all_customers}

        for a in anomalies:
            desc = (a.get("description") or "").lower()
            cp   = (a.get("counterparty") or "").lower()
            for cid in affected_customer_ids:
                cust = customer_map.get(cid)
                if cust:
                    from thefuzz import fuzz
                    name = cust["name"].lower()
                    if fuzz.partial_ratio(name, desc) > 80 or fuzz.partial_ratio(name, cp) > 80:
                        customer_anomaly_counts[cid] = customer_anomaly_counts.get(cid, 0) + 1

        for cid, count in customer_anomaly_counts.items():
            db.store_memory(
                agent="reconciliation",
                entity_id=cid,
                memory_type="semantic",
                content={
                    "period":        period,
                    "anomaly_count": count,
                    "summary":       analysis.business_explanation
                }
            )

    pending           = affected_customer_ids.copy()
    target_customer_id = pending.pop(0) if pending else None
    next_agent         = "credit" if target_customer_id else END

    return {
        **state,
        "current_agent": "reconciliation",
        "next_agent":    next_agent,
        "trigger":       "customer_payment_check" if next_agent == "credit" else "done",
        "pending_risk_assessments":   pending,
        "processed_risk_assessments": [],
        "reconciliation": {
            "run_id":                  run_id,
            "report_id":               report_id,
            "decision_id":             decision_id,
            "anomaly_summary":         analysis.business_explanation,
            "anomalous_customer_ids":  affected_customer_ids,
            "customer_anomaly_counts": customer_anomaly_counts,
        },
        "reasoning_trace": trace,
        "credit": {**state.get("credit", {}), "customer_id": target_customer_id or ""},
    }


def _find_customers(anomalies: list) -> list[str]:
    """Find all unique customer IDs related to the anomalies using fuzzy matching."""
    from thefuzz import fuzz
    customers = db.select("customers")
    found_ids = []
    for a in anomalies:
        desc        = (a.get("description") or "").lower()
        counterparty = (a.get("counterparty") or "").lower()
        for c in customers:
            name = c["name"].lower()
            if fuzz.partial_ratio(name, desc) > 80 or fuzz.partial_ratio(name, counterparty) > 80:
                if c["id"] not in found_ids:
                    found_ids.append(c["id"])
    return found_ids


def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
