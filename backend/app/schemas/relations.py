from typing import Literal
from pydantic import BaseModel, Field


class Relation(BaseModel):
    subject: str = Field(description="Structure id from the lesson list.")
    predicate: Literal["connects_to", "part_of"]
    object: str = Field(description="Structure id from the lesson list.")


class DiagramRelations(BaseModel):
    relations: list[Relation] = Field(default_factory=list, description="Empty if nothing applies.")
