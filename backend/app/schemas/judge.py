from pydantic import BaseModel, Field

class GroundingVerdict(BaseModel):
    grounded: bool = Field(description="True only if EVERY factual claim in the ANSWER is supported by the CONTEXT.")
