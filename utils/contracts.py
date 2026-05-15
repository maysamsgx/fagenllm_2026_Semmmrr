"""
utils/contracts.py
Strict Pydantic models for Agent JSON Contracts.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List


class DecisionOutput(BaseModel):
    decision: str = Field(description="The primary decision made by the agent.")
    confidence: float = Field(description="Confidence score between 0 and 100.")
    technical_explanation: str = Field(description="Raw reasoning trace, data lineage, and input-output mapping.")
    business_explanation: str = Field(description="Impact on KPIs: cash flow, budget variance, DSO/receivables.")
    causal_explanation: str = Field(description="Cross-domain impact: how this affects other agents and financial states.")
    cross_domain_signals: Dict[str, Any] = Field(default_factory=dict, description="Structured signals to pass to downstream agents.")


class ReconciliationOutput(DecisionOutput):
    is_systematic: bool = Field(
        description=(
            "True if the anomalies form a recurring or systematic pattern — "
            "e.g. the same counterparty consistently underpaying, repeated timing delays "
            "for the same entity, or identical amount gaps across multiple transactions. "
            "False if the anomalies appear isolated or random."
        )
    )

class GovernanceOutput(DecisionOutput):
    compliance_score: int = Field(description="Score from 0 to 100 on how well the decisions align with fiscal policy.")
    is_audit_safe: bool = Field(description="True if the audit trail is complete and no policy violations were found.")
    findings: List[str] = Field(description="List of specific governance findings or flags.")
    cause: str = Field(description="The primary root cause for the final audit verdict.")
    actions: List[str] = Field(description="The specific corrective or validating actions taken during the audit.")
    effects: List[str] = Field(description="The downstream consequences of this governance decision.")
    verdict: str = Field(description="The final audit result: PASSED, FLAGGED, or BLOCKED.")
