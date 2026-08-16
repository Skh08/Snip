from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str
    text: str
    source_label: str
    section: str | None = None
    paragraph: str | None = None
    kind: str = "paragraph"
    ordinal: int
    source_type: str = "docx"
    source_url: str | None = None
    verification_status: str | None = None
    verification_url: str | None = None
    # Canonical records retain the document hierarchy and merge every visual
    # continuation belonging to one numbered regulatory provision.
    subsection: str | None = None
    fragment_count: int = 1
    complete_evidence: bool = False


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    score: float
    chunk: Chunk


class ChatResponse(BaseModel):
    answer: str
    sources: list[SearchHit]
    grounded: bool
