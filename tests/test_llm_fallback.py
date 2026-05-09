import pytest
from unittest.mock import patch
from utils.llm import qwen_structured
from utils.contracts import DecisionOutput

def test_llm_fallback_mechanism():
    """
    Simulates a failure in the primary Qwen3 model (via Groq) 
    and ensures the system correctly falls back to gpt-oss-20b (via OpenRouter) 
    without crashing.
    """
    call_counts = {"qwen": 0, "gpt-oss-20b": 0}
    
    def mock_groq_raw_call(messages, model, *args, **kwargs):
        call_counts["qwen"] += 1
        raise Exception("Groq Qwen API Timeout")

    def mock_openrouter_raw_call(messages, model, *args, **kwargs):
        call_counts["gpt-oss-20b"] += 1
        return '{"decision": "approved", "confidence": 0.95, "technical_explanation": "fallback", "business_explanation": "fallback", "causal_explanation": "fallback", "is_systematic": false, "action": "approve"}'

    with patch("utils.llm._groq_raw_call", side_effect=mock_groq_raw_call):
        with patch("utils.llm._openrouter_raw_call", side_effect=mock_openrouter_raw_call):
            result = qwen_structured("system", "user", DecisionOutput)
            
            # Verify fallback logic crossed providers successfully
            assert call_counts["qwen"] == 1
            assert call_counts["gpt-oss-20b"] == 1
            assert result.decision == "approved"
            assert result.confidence == 0.95
