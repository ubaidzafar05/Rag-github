from pydantic import BaseModel

class IngestRequest(BaseModel):
    repo_url: str
    docs_url: str | None = None

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None
