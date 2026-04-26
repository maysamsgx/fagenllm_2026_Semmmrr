"""
config.py
Central configuration and client initialisation for FAgentLLM.

Provider map:
  - Qwen3-32B           : Groq         (fast inference, free tier)
  - Baidu OCR Fast      : OpenRouter   (free, model: baidu/qianfan-ocr-fast)
  - Database + Storage  : Supabase
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import create_client, Client
from langchain_openai import ChatOpenAI


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # Qwen3-32B via Groq (OpenAI-compatible, free tier)
    # Get key: https://console.groq.com -> API Keys
    groq_api_key: str
    groq_base_url: str = "https://api.groq.com/openai/v1"
    qwen_model: str = "qwen/qwen3-32b"

    # Baidu Qianfan-OCR-Fast via OpenRouter (free)
    # Get key: https://openrouter.ai -> API Keys
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ocr_model: str = "baidu/qianfan-ocr-fast"

    # App
    app_env: str = "development"
    app_secret: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings - reads .env once at startup."""
    return Settings()


def get_supabase() -> Client:
    """
    Server-side Supabase client (service role key - bypasses RLS).
    Never expose this key to the frontend.
    """
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """
    Qwen3-32B via Groq.
    Groq is OpenAI-compatible -> LangChain's ChatOpenAI works directly.

    temperature=0.0  -> deterministic extraction (invoices, reconciliation)
    temperature=0.4  -> natural language explanations (XAI traces)
    """
    s = get_settings()
    return ChatOpenAI(
        model=s.qwen_model,
        api_key=s.groq_api_key,
        base_url=s.groq_base_url,
        temperature=temperature,
        max_tokens=4096,
    )


def get_ocr_client() -> ChatOpenAI:
    """
    Baidu Qianfan-OCR-Fast via OpenRouter.
    Send invoice image as base64 data URL in the message content.
    """
    s = get_settings()
    return ChatOpenAI(
        model=s.ocr_model,
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        temperature=0.0,
        max_tokens=2048,
    )
