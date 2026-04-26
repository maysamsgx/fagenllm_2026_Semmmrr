"""
utils/llm.py
Utility wrappers for:
  - Qwen3-32B via OpenRouter  (reasoning, extraction, risk analysis)
  - Baidu Qianfan OCR Fast    (invoice image/PDF text extraction)

All agents import from here. Retry logic and error handling is centralised.
"""

import base64
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.messages import HumanMessage, SystemMessage
from config import get_llm, get_settings


# ── Qwen3 helpers ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def qwen_extract(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
    """
    Call Qwen3-32B for structured extraction tasks.
    Returns the raw string response. Use qwen_json() if you need parsed JSON.

    Retries up to 3 times with exponential backoff on failure.
    temperature=0.0 for deterministic extraction.
    """
    llm = get_llm(temperature=temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    return response.content


def qwen_json(system_prompt: str, user_prompt: str) -> dict:
    """
    Call Qwen3 expecting a JSON response. Parses and returns the dict.
    If parsing fails, returns {"error": "parse_failed", "raw": <response>}.
    """
    # Instruct the model to return only JSON
    system_with_json = (
        system_prompt
        + "\n\nIMPORTANT: Respond with valid JSON only. No explanation, no markdown, no code fences."
    )
    raw = qwen_extract(system_with_json, user_prompt, temperature=0.0)

    # Strip any accidental markdown fences
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": cleaned}


def qwen_explain(context: str, question: str) -> str:
    """
    Ask Qwen3 to generate a natural language explanation.
    Used for XAI reasoning traces. temperature=0.4 for readable prose.
    """
    system = (
        "You are a financial AI assistant. Explain financial decisions clearly "
        "and concisely for finance professionals. Be specific about numbers and reasons. "
        "Keep explanations under 3 sentences."
    )
    return qwen_extract(system, f"Context:\n{context}\n\nQuestion: {question}", temperature=0.4)


# ── Baidu Qianfan-OCR-Fast via OpenRouter ─────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def baidu_ocr(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """
    Send an image to Baidu Qianfan-OCR-Fast via OpenRouter and return extracted text.

    OpenRouter exposes Baidu OCR as a vision chat model — we send the image
    as a base64 data URL in the message content, exactly like GPT-4 Vision.

    Args:
        image_bytes: raw bytes of the image (JPEG or PNG)
        media_type:  'image/jpeg' | 'image/png'

    Returns:
        Extracted text as a single string.
    """
    from config import get_ocr_client
    from langchain_core.messages import HumanMessage

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{img_b64}"

    client = get_ocr_client()
    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": data_url},
        },
        {
            "type": "text",
            "text": "Extract all text from this invoice image. Return only the extracted text, preserving layout as much as possible.",
        },
    ])
    response = client.invoke([message])
    return response.content


def pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Convert a PDF to a list of JPEG image bytes (one per page).
    Used to feed multi-page invoices to Baidu OCR page by page.

    Requires: pip install pypdf pillow
    For the prototype we use pypdf's page rendering. Production: use pymupdf.
    """
    try:
        import io
        from pypdf import PdfReader
        from PIL import Image

        reader = PdfReader(io.BytesIO(pdf_bytes))
        images = []
        for page in reader.pages:
            # pypdf can extract page as image via its rendering pipeline
            # Simple approach: extract any embedded images from the page
            for img_obj in page.images:
                img_bytes = io.BytesIO()
                Image.open(io.BytesIO(img_obj.data)).convert("RGB").save(img_bytes, format="JPEG")
                images.append(img_bytes.getvalue())
        return images if images else []
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}")


def ocr_invoice(file_bytes: bytes, filename: str) -> str:
    """
    High-level function: accepts a PDF or image file, runs OCR, returns combined text.
    This is what the Invoice agent calls — it doesn't need to know about Baidu internals.
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        pages = pdf_to_images(file_bytes)
        if not pages:
            # Fallback: if no images embedded, try treating the PDF itself as image
            return baidu_ocr(file_bytes, "jpg")
        # OCR each page and combine
        texts = [baidu_ocr(page_bytes) for page_bytes in pages]
        return "\n\n--- PAGE BREAK ---\n\n".join(texts)

    elif filename_lower.endswith(".png"):
        return baidu_ocr(file_bytes, "png")
    else:
        # Default to JPEG
        return baidu_ocr(file_bytes, "jpg")
