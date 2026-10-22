from pydantic import BaseModel, Field, field_validator, model_validator

class GeneratedQuestion(BaseModel):
    prompt: str = Field(description="The question text shown to the student.")
    choices: list[str] = Field(description="Exactly 4 distinct answer options.")
    correct: str = Field(description="The correct answer, copied exactly from choices.")

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt is empty")
        return v.strip()

    @field_validator("choices")
    @classmethod
    def _four_distinct_choices(cls, v: list[str]) -> list[str]:
        v = [c.strip() for c in v]
        if len(v) != 4 or len(set(v)) != 4 or not all(v):
            raise ValueError("choices must be 4 distinct non-empty strings")
        return v

    @model_validator(mode="after")
    def _correct_is_a_choice(self):
        self.correct = self.correct.strip()
        if self.correct not in self.choices:
            raise ValueError("correct must be one of choices")
        return self
