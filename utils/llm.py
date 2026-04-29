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
from functools import lru_cache

from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_llm

logger = logging.getLogger("fagentllm")


# ── Qwen3 helpers ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def qwen_extract(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
    llm = get_llm(temperature=temperature)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    return response.content


def qwen_json(system_prompt: str, user_prompt: str) -> dict:
    system_with_json = (
        system_prompt
        + "\n\nIMPORTANT: Respond with valid JSON only. No explanation, no markdown, no code fences."
    )
    raw = qwen_extract(system_with_json, user_prompt, temperature=0.0)
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": cleaned}


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
            if not token: continue
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
