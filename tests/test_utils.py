
from utils.llm import _strip_reasoning, _coerce_json
from utils.contracts import DecisionOutput

def test_strip_reasoning():
    raw = "<think>Calculating...</think>```json\n{\"test\": 1}\n```"
    assert _strip_reasoning(raw) == "{\"test\": 1}"
    
    raw_clean = "{\"test\": 2}"
    assert _strip_reasoning(raw_clean) == "{\"test\": 2}"

def test_coerce_json():
    # Strict JSON
    assert _coerce_json('{"key": "value"}') == {"key": "value"}
    
    # JSON with surrounding prose
    text = "Here is the result: {\"score\": 0.85} hope this helps."
    assert _coerce_json(text) == {"score": 0.85}
    
    # Broken JSON
    assert _coerce_json("not json") is None

def test_decision_output_schema():
    data = {
        "technical_explanation": "Test tech",
        "business_explanation": "Test biz",
        "causal_explanation": "Test causal",
        "confidence": 0.95,
        "decision": "approve"
    }
    obj = DecisionOutput(**data)
    assert obj.confidence == 0.95
    assert obj.decision == "approve"
