from typing import Literal
from pydantic import BaseModel, Field

class GroundingVerdict(BaseModel):
    grounded: bool = Field(description="True only if EVERY factual claim in the ANSWER is supported by the CONTEXT.")

class JevRequest(BaseModel):
    question: str
    options: list[str]
    inputs: dict[str, str]

class PairwiseDecision(BaseModel):
    decision: Literal["A", "B"]
    probabilities: dict[Literal["A", "B"], float]
