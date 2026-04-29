"""
utils/contracts.py
Strict Pydantic models for Agent JSON Contracts.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict

class DecisionOutput(BaseModel):
    decision: str = Field(description="The primary decision made by the agent.")
    confidence: float = Field(description="Confidence score between 0 and 100.")
    technical_explanation: str = Field(description="Raw reasoning trace, data lineage, and input-output mapping.")
    business_explanation: str = Field(description="Impact on KPIs: cash flow, budget variance, DSO/receivables.")
    causal_explanation: str = Field(description="Cross-domain impact: how this affects other agents and financial states.")
    cross_domain_signals: Dict[str, Any] = Field(default_factory=dict, description="Structured signals to pass to downstream agents.")
