"""
utils/llm.py
Utility wrappers for:
  - Qwen3-32B (Reasoning Tier)             : Governance, Audit & Self-Reflection
  - Llama-3.1-8b (Workhorse Tier)         : High-speed Structured Extraction
  - Baidu Qianfan-OCR-Fast via OpenRouter : Primary OCR
  - Tesseract                           : Local OCR Fallback
  - Multi-Key Rotation & Tiered Model Resiliency
"""

import base64
import io
import json
import logging
import re
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_llm

logger = logging.getLogger("fagentllm")


# ── Qwen3 helpers ─────────────────────────────────────────────────────────────

# qwen3-32b is a reasoning model: it emits <think>…</think> before the answer.
# Groq lets us turn that off per-request via reasoning_effort="none".
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_OBJ_RE = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)


def _strip_reasoning(text: str) -> str:
    """Remove <think>…</think> blocks and code fences left around JSON."""
    text = _THINK_RE.sub("", text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.removeprefix("json").lstrip()
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0].rstrip()
    return text.strip()


def _coerce_json(text: str) -> dict | None:
    """Best-effort parse: strict first, then first {...} object, then None."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # First top-level object via greedy balanced match
    m = _JSON_OBJ_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # Last resort: substring between first `{` and last `}`
    if "{" in text and "}" in text:
        chunk = text[text.index("{"): text.rindex("}") + 1]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            return None
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def qwen_extract(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
    """Plain text completion via langchain. Used for free-form explanations."""
    llm = get_llm(temperature=temperature)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    return response.content


def _groq_client():
    """Direct OpenAI-compatible client for Groq. Rotates keys on every call."""
    from openai import OpenAI
    from config import get_settings, get_groq_key
    s = get_settings()
    # No caching here to ensure key rotation via get_groq_key()
    return OpenAI(api_key=get_groq_key(), base_url=s.groq_base_url)


def _groq_raw_call(
    messages: list[dict],
    model: str,
    temperature: float = 0.0,
    force_json: bool = True,
    max_tokens: int = 4096,
    use_reasoning_effort: bool = True,
) -> str:
    """
    Model-agnostic Groq API call.

    Parameters
    ----------
    use_reasoning_effort : bool
        Must be False for models that do not support the reasoning_effort
        parameter (e.g. gpt-oss-20b).
    """
    client = _groq_client()
    # 45 s hard ceiling — prevents the reconciliation background task from
    # hanging indefinitely on Groq free-tier rate pressure or slow responses.
    base: dict = dict(model=model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens,
                      timeout=45.0)
    if use_reasoning_effort:
        base["extra_body"] = {"reasoning_effort": "none"}
    try:
        if force_json:
            r = client.chat.completions.create(**base, response_format={"type": "json_object"})
        else:
            r = client.chat.completions.create(**base)
    except Exception as e:
        msg = str(e)
        if force_json and any(k in msg.lower() for k in ("response_format", "json_object", "unsupported")):
            logger.warning(f"Groq rejected response_format for {model}; retrying without JSON mode.")
            r = client.chat.completions.create(**base)
        else:
            raise
    return (r.choices[0].message.content or "").strip()


def _openrouter_client():
    """Direct OpenAI-compatible client for OpenRouter. Cached per process."""
    from openai import OpenAI
    from config import get_settings
    s = get_settings()
    if not hasattr(_openrouter_client, "_c"):
        _openrouter_client._c = OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)
    return _openrouter_client._c


def _openrouter_raw_call(
    messages: list[dict],
    model: str,
    temperature: float = 0.0,
    force_json: bool = True,
    max_tokens: int = 4096,
) -> str:
    client = _openrouter_client()
    base: dict = dict(model=model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
    # Some OpenRouter models don't support JSON mode, but we try
    try:
        if force_json:
            r = client.chat.completions.create(**base, response_format={"type": "json_object"})
        else:
            r = client.chat.completions.create(**base)
    except Exception as e:
        msg = str(e)
        if force_json and any(k in msg.lower() for k in ("response_format", "json_object", "unsupported")):
            logger.warning(f"OpenRouter rejected response_format for {model}; retrying without JSON mode.")
            r = client.chat.completions.create(**base)
        else:
            raise
    return (r.choices[0].message.content or "").strip()


def _qwen_chat_json(messages: list[dict], temperature: float = 0.0,
                    force_json: bool = True, max_tokens: int = 4096, 
                    tier: str = "reasoning") -> str:
    """Primary model call. Use _call_groq_with_fallback for resilient callers."""
    from config import get_settings
    s = get_settings()
    model = s.qwen_model if tier == "reasoning" else s.workhorse_model
    return _groq_raw_call(messages, model=model, temperature=temperature,
                          force_json=force_json, max_tokens=max_tokens,
                          use_reasoning_effort=(tier == "reasoning"))


def _call_groq_with_fallback(
    messages: list[dict],
    temperature: float = 0.0,
    force_json: bool = True,
    max_tokens: int = 1024,
    tier: str = "reasoning"
) -> tuple[str, str]:
    """
    Call primary model (Qwen3); on failure retry with fallback (gpt-oss-20b).

    max_tokens is intentionally kept at 1024 for workhorse/structured calls
    so that total request tokens (input ~2-3k + output) stays under Groq's
    6000 TPM free-tier cap for llama-3.1-8b-instant.

    Returns
    -------
    (raw_content, model_used)
        model_used is "primary" or "fallback" — logged for thesis metrics.

    Raises
    ------
    RuntimeError
        If both models fail.
    """
    from config import get_settings
    s = get_settings()

    # Primary attempt
    try:
        raw = _qwen_chat_json(messages, temperature=temperature,
                              force_json=force_json, max_tokens=max_tokens,
                              tier=tier)
        if not force_json or _coerce_json(_strip_reasoning(raw)) is not None:
            return raw, "primary"
        logger.warning(
            "Primary model (%s) returned non-JSON output; activating fallback (%s).",
            s.qwen_model, s.openrouter_fallback_model,
        )
    except Exception as exc:
        logger.warning(
            "Primary model (%s) raised %s: %s — activating fallback (%s).",
            s.qwen_model, type(exc).__name__, exc, s.openrouter_fallback_model,
        )

    # Fallback attempt (openai/gpt-oss-20b:free via OpenRouter)
    # OpenRouter has no strict TPM cap, so we give it more room
    try:
        raw = _openrouter_raw_call(messages, model=s.openrouter_fallback_model,
                             temperature=0.3, force_json=force_json,
                             max_tokens=1500)
        logger.info("Fallback model (%s) succeeded.", s.openrouter_fallback_model)
        return raw, "fallback"
    except Exception as exc2:
        raise RuntimeError(
            f"Both models failed. "
            f"Fallback ({s.openrouter_fallback_model}): {exc2}"
        ) from exc2


_JSON_SYSTEM_SUFFIX = (
    "\n\nOUTPUT CONTRACT — ABSOLUTE:\n"
    "1. Return ONLY a single JSON object.\n"
    "2. The first character of your response MUST be `{` and the last MUST be `}`.\n"
    "3. NO prose, NO markdown, NO code fences, NO <think> blocks, NO commentary.\n"
    "4. If a value is unknown, use null. Strings must be JSON-quoted."
)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4),
       reraise=True)
def qwen_json(system_prompt: str, user_prompt: str) -> dict:
    """
    Robust JSON extraction with two attempts:
      attempt 1 → JSON mode + reasoning_effort=none
      attempt 2 → corrective re-prompt with the broken output as context
    """
    system = system_prompt + _JSON_SYSTEM_SUFFIX
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_prompt},
    ]
    # Use 'workhorse' for routine JSON extraction tasks to save 'reasoning' TPM
    # max_tokens=1024 keeps total request under Groq 6000 TPM limit
    raw, model_used = _call_groq_with_fallback(messages, temperature=0.0, force_json=True, max_tokens=1024, tier="workhorse")
    logger.info("qwen_json attempt 1: model_used=%s", model_used)
    cleaned = _strip_reasoning(raw)
    parsed = _coerce_json(cleaned)
    if parsed is not None:
        return parsed

    # ── Attempt 2: tell the model exactly what it did wrong ─────────────────
    logger.warning(f"qwen_json: first attempt did not yield JSON. Raw head: {cleaned[:240]!r}")
    correction = (
        "Your previous response was NOT valid JSON. "
        "You returned this (truncated):\n"
        f"---\n{cleaned[:600]}\n---\n"
        "Now reply again. Output ONLY the JSON object — start with `{` and end with `}`. "
        "No reasoning, no prose, no fences."
    )
    messages.append({"role": "assistant", "content": cleaned[:800]})
    messages.append({"role": "user", "content": correction})
    # Correction still uses 'workhorse'
    raw2, model_used2 = _call_groq_with_fallback(messages, temperature=0.0, force_json=True, max_tokens=1024, tier="workhorse")
    logger.info("qwen_json attempt 2: model_used=%s", model_used2)
    cleaned2 = _strip_reasoning(raw2)
    parsed = _coerce_json(cleaned2)
    if parsed is not None:
        return parsed

    logger.error(f"qwen_json: both attempts failed. Final raw head: {cleaned2[:400]!r}")
    return {"error": "parse_failed", "raw": cleaned2[:1200] or cleaned[:1200]}





def qwen_structured(system_prompt: str, user_prompt: str, schema: Type[T], tier: str = "workhorse") -> T:
    """
    Same robust loop as qwen_json but validates against a Pydantic schema.
    Retries once if validation fails.
    """
    schema_doc = json.dumps(schema.model_json_schema(), indent=2)
    system = (
        system_prompt
        + "\n\nYou must return JSON that exactly matches this JSON Schema:\n"
        + schema_doc
        + _JSON_SYSTEM_SUFFIX
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_prompt},
    ]
    last_raw = ""
    for attempt in range(2):
        # Use 'workhorse' for routine structured extraction
        # max_tokens=1024 keeps total request under Groq 6000 TPM limit
        raw, model_used = _call_groq_with_fallback(messages, temperature=0.0, force_json=True, max_tokens=1024, tier="workhorse")
        logger.info("qwen_structured attempt %d: model_used=%s", attempt + 1, model_used)
        raw = raw  # keep variable name consistent below
        last_raw = raw
        cleaned = _strip_reasoning(raw)
        parsed = _coerce_json(cleaned)
        if parsed is not None:
            try:
                return schema(**parsed)
            except Exception as e:
                logger.warning(f"qwen_structured: schema mismatch on attempt {attempt + 1}: {e}")
                # Feed the bad output back for a corrective retry (keep short to save TPM)
                messages.append({"role": "assistant", "content": cleaned[:600]})
                messages.append({"role": "user", "content":
                    f"Validation failed: {e}. Return ONLY a JSON object matching "
                    "the schema. Use null for unknown values."})
                continue
        # Bad JSON entirely (keep short to save TPM)
        messages.append({"role": "assistant", "content": cleaned[:600]})
        messages.append({"role": "user", "content":
            "Invalid JSON. Output ONLY the JSON object now."})

    logger.error(f"qwen_structured: gave up after retries. Raw: {last_raw[:400]!r}")
    raise ValueError("Qwen3 returned non-JSON output even after corrective retry.")


def qwen_structured_with_reflection(system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
    """
    Cognitive Architecture: Reflection Pass (Persistent Memory Pattern).
    First calls qwen_structured, then asks the model to review its own reasoning.
    """
    # 1. Initial reasoning pass
    first_answer = qwen_structured(system_prompt, user_prompt, schema)
    
    # 2. Self-reflection pass (Uses 'reasoning' tier for audit quality)
    reflection_system = (
        "You are a senior financial auditor. Review the following decision for logical errors, "
        "causal consistency, and proportionate action. If the reasoning is sound, return the same JSON. "
        "If you find errors, return a corrected JSON object."
    )
    
    reflection_user = f"""
    Review this financial decision for logical errors, causal consistency, and proportionate action:
    {json.dumps(first_answer.model_dump(), indent=2)}
    
    Does the causal explanation match the evidence? Is the decision proportionate?
    Return ONLY the final (corrected) JSON object matching the schema.
    """
    
    return qwen_structured(reflection_system, reflection_user, schema, tier="reasoning")


def qwen_explain(context: str, question: str) -> str:
    system = (
        "You are a financial AI assistant. Explain financial decisions clearly "
        "and concisely for finance professionals. Be specific about numbers and reasons. "
        "Keep explanations under 3 sentences."
    )
    return qwen_extract(system, f"Context:\n{context}\n\nQuestion: {question}", temperature=0.4)


# ── Primary OCR: Baidu Qianfan-OCR-Fast via OpenRouter ───────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
def _baidu_ocr_call(image_bytes: bytes, media_type: str) -> str:
    """Single Baidu OCR call. Caller decides whether to fall back on failure."""
    from config import get_ocr_client

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{img_b64}"

    client = get_ocr_client()
    message = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text",
         "text": "Extract all text from this invoice image. Return only the extracted text, "
                 "preserving layout as much as possible."},
    ])
    response = client.invoke([message])
    text = (response.content or "").strip()
    if not text:
        raise RuntimeError("Baidu OCR returned empty text")
    return text


def baidu_ocr(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """Try Baidu first. On any failure fall back to local Tesseract."""
    try:
        return _baidu_ocr_call(image_bytes, media_type)
    except Exception as e:
        logger.warning(f"Baidu OCR unavailable ({e}); falling back to local Tesseract")
        return fallback_ocr(image_bytes)


# ── Fallback OCR: Tesseract ─────────────────────────────────────

def fallback_ocr(image_bytes: bytes) -> str:
    """
    Fallback OCR using Tesseract (Local). 
    If local OCR also fails, it raises a RuntimeError for safety.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        width, height = img.size
        
        # 1. Raw OCR via Tesseract
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        words: list[str] = []
        for i, w in enumerate(ocr_data["text"]):
            token = (w or "").strip()
            if not token:
                continue
            words.append(token)

        if not words:
            raise RuntimeError("Local OCR (Tesseract) found no text in the image.")

        tag = "TESSERACT"

        # Reassemble layout using Tesseract's line numbering
        lines: dict[int, list[str]] = {}
        for i, w in enumerate(ocr_data["text"]):
            token = (w or "").strip()
            if not token:
                continue
            line_idx = ocr_data["line_num"][i]
            lines.setdefault(line_idx, []).append(token)
        
        rendered = []
        for k in sorted(lines.keys()):
            rendered.append(" ".join(lines[k]))
            
        return f"[LOCAL OCR: {tag}]\n" + "\n".join(rendered)
            
    except Exception as e:
        logger.error(f"Local OCR Fallback failed: {e}")
        raise RuntimeError(f"Every OCR layer failed. Final error: {e}")


# ── PDF helpers ──────────────────────────────────────────────────────────────

def extract_pdf_text_direct(pdf_bytes: bytes) -> str | None:
    """
    Attempt to extract text directly from a digital PDF.
    If the PDF is essentially empty of text (e.g., scanned images), returns None.
    """
    try:
        import fitz
    except ImportError as e:
        raise RuntimeError("PyMuPDF (pymupdf) is required. Install with: pip install pymupdf") from e

    text_pages = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            page_text = page.get_text("text").strip()
            if page_text:
                text_pages.append(page_text)
    
    combined_text = "\n\n--- PAGE BREAK ---\n\n".join(text_pages)
    
    if len(combined_text) > 50:
        return f"[DIGITAL PDF DIRECT EXTRACT]\n{combined_text}"
    return None


def pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Render every PDF page to JPEG. Uses PyMuPDF (fitz) — that handles
    text-only PDFs correctly, unlike pypdf which only extracts embedded images.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(
            "PyMuPDF (pymupdf) is required to OCR PDFs. Install with: pip install pymupdf"
        ) from e

    images: list[bytes] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            # 200 DPI gives Tesseract a fighting chance on small text.
            pix = page.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), alpha=False)
            buf = io.BytesIO()
            from PIL import Image
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(buf, format="JPEG", quality=92)
            images.append(buf.getvalue())
    return images


def ocr_invoice(file_bytes: bytes, filename: str) -> str:
    """
    Public entry: OCR a PDF or image and return the combined text.
    Raises RuntimeError if every layer fails — the caller (invoice agent)
    should surface that as a real error rather than fabricate text.
    """
    name = filename.lower()

    if name.endswith(".pdf"):
        # 1. Try direct digital text extraction first
        direct_text = extract_pdf_text_direct(file_bytes)
        if direct_text:
            return direct_text
            
        # 2. Fall back to OCR if it's a scanned PDF
        pages = pdf_to_images(file_bytes)
        if not pages:
            raise RuntimeError(f"PDF {filename} has no renderable pages")
        return "\n\n--- PAGE BREAK ---\n\n".join(baidu_ocr(p, "image/jpeg") for p in pages)

    if name.endswith(".png"):
        return baidu_ocr(file_bytes, "image/png")
    if name.endswith((".jpg", ".jpeg")):
        return baidu_ocr(file_bytes, "image/jpeg")

    # Unknown extension — let Pillow sniff it
    return baidu_ocr(file_bytes, "image/jpeg")
