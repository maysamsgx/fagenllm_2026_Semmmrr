"""
config.py
Central configuration and client initialisation for FAgentLLM.

Provider map:
  - Qwen3-32B           : Groq         (fast inference, free tier)
  - Baidu OCR Fast      : OpenRouter   (free, model: baidu/qianfan-ocr-fast)
  - Fallback LLM        : OpenRouter   (free, model: baidu/cobuddy)
  - Database + Storage  : Supabase
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import create_client, Client
from langchain_openai import ChatOpenAI


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str = ""
    supabase_service_key: str

    # Groq Configuration (Rate Limit Solution)
    # Provide multiple keys as a comma-separated string: "key1,key2,key3"
    groq_api_keys: str = "" 
    groq_base_url: str = "https://api.groq.com/openai/v1"
    
    # Tiered Model Strategy
    # 1. Reasoning Model (High logic, lower TPM)
    qwen_model: str = "qwen/qwen3-32b"
    
    # 2. Workhorse Model (High RPM, good for routine tasks)
    # llama-3.1-8b-instant is extremely fast for extraction
    workhorse_model: str = "llama-3.1-8b-instant"

    # OpenRouter Models (Final Fallback)
    openrouter_api_key: str = ""          # baidu/cobuddy:free  — fallback LLM
    openrouter_ocr_api_key: str = ""      # baidu/qianfan-ocr-fast:free — OCR
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_fallback_model: str = "baidu/cobuddy:free"
    ocr_model: str = "baidu/qianfan-ocr-fast:free"

    # App
    app_env: str = "development"
    app_secret: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings - reads .env once at startup."""
    return Settings()


def get_groq_key() -> str:
    """
    Round-robin rotation of Groq API keys to multiply TPM/RPM limits.
    """
    s = get_settings()
    keys = [k.strip() for k in s.groq_api_keys.split(",") if k.strip()]
    if not keys:
        # Fallback to single key if provided for backward compatibility
        return getattr(s, "groq_api_key", "")
    
    # Simple rotation based on a global counter (safe for prototype)
    if not hasattr(get_groq_key, "_counter"):
        get_groq_key._counter = 0
    
    key = keys[get_groq_key._counter % len(keys)]
    get_groq_key._counter += 1
    return key


def get_supabase() -> Client:
    """
    Server-side Supabase client (service role key - bypasses RLS).
    """
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise ValueError(
            "CRITICAL: SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from environment. "
            "Check your GitHub Secrets or .env file."
        )
    return create_client(s.supabase_url, s.supabase_service_key)


def get_llm(temperature: float = 0.0, tier: str = "reasoning") -> ChatOpenAI:
    """
    Get an LLM instance based on the required tier.
    
    - 'reasoning': Qwen3-32B (Best for governance, causal logic)
    - 'workhorse': Llama-4-Scout (30k TPM, best for routine extraction)
    """
    s = get_settings()
    model = s.qwen_model if tier == "reasoning" else s.workhorse_model
    
    return ChatOpenAI(
        model=model,
        api_key=get_groq_key(),
        base_url=s.groq_base_url,
        temperature=temperature,
        max_tokens=4096,
    )


def get_ocr_client() -> ChatOpenAI:
    """
    Baidu Qianfan-OCR-Fast via OpenRouter.
    Send invoice image as base64 data URL in the message content.
    Uses its own dedicated API key (OPENROUTER_OCR_API_KEY).
    """
    s = get_settings()
    # Use the OCR-specific key; fall back to the shared key if not set
    ocr_key = s.openrouter_ocr_api_key or s.openrouter_api_key
    return ChatOpenAI(
        model=s.ocr_model,
        api_key=ocr_key,
        base_url=s.openrouter_base_url,
        temperature=0.0,
        max_tokens=2048,
    )
