from pydantic import BaseModel, ConfigDict

class ContentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

class StructureSpec(ContentSpec):
    id: str
    mesh_name: str | None = None
    display_name_en: str
    display_name_ar: str | None = None
    aliases: list[str] = []
    relations: dict[str, list[str]] = {}

class KnowledgeSpec(ContentSpec):
    structure_id: str | None = None
    review_status: str = "DRAFT"
    source: str = ""
    source_version: str = ""
    reviewer: str | None = None
    text: str

class LessonSpec(ContentSpec):
    id: str; title: str; system: str
    model_url: str; ios_model_url: str | None = None
    review_status: str = "DRAFT"
