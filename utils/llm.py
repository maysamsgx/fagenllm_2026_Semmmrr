"""
utils/llm.py
Utility wrappers for:
  - Qwen3-32B via Groq                       (reasoning / extraction / risk)
  - Baidu Qianfan-OCR-Fast via OpenRouter    (primary OCR)
  - Tesseract + LayoutLMv3                   (local OCR fallback)
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
    """Direct OpenAI-compatible client for Groq. Cached per process."""
    from openai import OpenAI
    from config import get_settings
    s = get_settings()
    if not hasattr(_groq_client, "_c"):
        _groq_client._c = OpenAI(api_key=s.groq_api_key, base_url=s.groq_base_url)
    return _groq_client._c


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
        parameter (e.g. llama-3.3-70b-versatile).
    """
    client = _groq_client()
    base: dict = dict(model=model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
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


def _qwen_chat_json(messages: list[dict], temperature: float = 0.0,
                    force_json: bool = True, max_tokens: int = 4096) -> str:
    """Primary model call. Use _call_groq_with_fallback for resilient callers."""
    from config import get_settings
    s = get_settings()
    return _groq_raw_call(messages, model=s.qwen_model, temperature=temperature,
                          force_json=force_json, max_tokens=max_tokens,
                          use_reasoning_effort=True)


def _call_groq_with_fallback(
    messages: list[dict],
    temperature: float = 0.0,
    force_json: bool = True,
    max_tokens: int = 4096,
) -> tuple[str, str]:
    """
    Call primary model (Qwen3); on failure retry with fallback (llama-3.3-70b).

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
                              force_json=force_json, max_tokens=max_tokens)
        if not force_json or _coerce_json(_strip_reasoning(raw)) is not None:
            return raw, "primary"
        logger.warning(
            "Primary model (%s) returned non-JSON output; activating fallback (%s).",
            s.qwen_model, s.groq_fallback_model,
        )
    except Exception as exc:
        logger.warning(
            "Primary model (%s) raised %s: %s — activating fallback (%s).",
            s.qwen_model, type(exc).__name__, exc, s.groq_fallback_model,
        )

    # Fallback attempt (llama-3.3-70b-versatile)
    try:
        raw = _groq_raw_call(messages, model=s.groq_fallback_model,
                             temperature=1.0, force_json=force_json,
                             max_tokens=1024, use_reasoning_effort=False)
        logger.info("Fallback model (%s) succeeded.", s.groq_fallback_model)
        return raw, "fallback"
    except Exception as exc2:
        raise RuntimeError(
            f"Both models failed. "
            f"Fallback ({s.groq_fallback_model}): {exc2}"
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
    raw, model_used = _call_groq_with_fallback(messages, temperature=0.0, force_json=True)
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
    messages.append({"role": "assistant", "content": cleaned[:1500]})
    messages.append({"role": "user", "content": correction})
    raw2, model_used2 = _call_groq_with_fallback(messages, temperature=0.0, force_json=True)
    logger.info("qwen_json attempt 2: model_used=%s", model_used2)
    cleaned2 = _strip_reasoning(raw2)
    parsed = _coerce_json(cleaned2)
    if parsed is not None:
        return parsed

    logger.error(f"qwen_json: both attempts failed. Final raw head: {cleaned2[:400]!r}")
    return {"error": "parse_failed", "raw": cleaned2[:1200] or cleaned[:1200]}





def qwen_structured(system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
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
        raw, model_used = _call_groq_with_fallback(messages, temperature=0.0, force_json=True)
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
                # Feed the bad output back for a corrective retry
                messages.append({"role": "assistant", "content": cleaned[:1500]})
                messages.append({"role": "user", "content":
                    f"Validation failed: {e}. Return ONLY a JSON object that strictly matches "
                    "the schema above. Use null for unknown values."})
                continue
        # Bad JSON entirely
        messages.append({"role": "assistant", "content": cleaned[:1500]})
        messages.append({"role": "user", "content":
            "Your previous response was not valid JSON. Output ONLY the JSON object now."})

    logger.error(f"qwen_structured: gave up after retries. Raw: {last_raw[:400]!r}")
    raise ValueError("Qwen3 returned non-JSON output even after corrective retry.")


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
    """Try Baidu first. On any failure fall back to local Tesseract + LayoutLMv3."""
    try:
        return _baidu_ocr_call(image_bytes, media_type)
    except Exception as e:
        logger.warning(f"Baidu OCR unavailable ({e}); falling back to Tesseract+LayoutLMv3")
        return fallback_ocr(image_bytes)


# ── Fallback OCR: Tesseract ─────────────────────────────────────

def fallback_ocr(image_bytes: bytes) -> str:
    """
    Fallback OCR using Tesseract (Local). 
    If local OCR also fails, returns a Mock Invoice for demo safety.
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
        boxes: list[list[int]] = []
        for i, w in enumerate(ocr_data["text"]):
            token = (w or "").strip()
            if not token:
                continue
            x, y, w_, h_ = ocr_data["left"][i], ocr_data["top"][i], ocr_data["width"][i], ocr_data["height"][i]
            # LayoutLMv3 wants boxes scaled to [0, 1000]
            boxes.append([
                max(0, int(1000 * x / width)),
                max(0, int(1000 * y / height)),
                min(1000, int(1000 * (x + w_) / width)),
                min(1000, int(1000 * (y + h_) / height)),
            ])
            words.append(token)

        if not words:
            raise RuntimeError("Local OCR (Tesseract) found no text in the image.")

        tag = "TESSERACT"

        # Reassemble layout
        lines: dict[int, list[tuple[int, str]]] = {}
        for word, box in zip(words, boxes):
            line_key = box[1] // 12
            lines.setdefault(line_key, []).append((box[0], word))
        
        rendered = []
        for k in sorted(lines.keys()):
            rendered.append(" ".join(w for _, w in sorted(lines[k], key=lambda t: t[0])))
            
        return f"[LOCAL OCR: {tag}]\n" + "\n".join(rendered)
            
    except Exception as e:
        logger.error(f"Local OCR Fallback failed: {e}")
        raise RuntimeError(f"Every OCR layer failed. Final error: {e}")


# ── PDF helpers ──────────────────────────────────────────────────────────────

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
