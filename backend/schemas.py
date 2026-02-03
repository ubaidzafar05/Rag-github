from pydantic import BaseModel
from typing import List, Optional, Dict

class IngestRequest(BaseModel):
    repo_url: str
    docs_url: Optional[str] = None

class IngestStatus(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
    repo_url: Optional[str] = None

class ApplyRequest(BaseModel):
    repo_url: str
    file_path: str
    content: str
    approved: bool = False
    validation_commands: Optional[List[str]] = None

class ApplyPreviewRequest(BaseModel):
    repo_url: str
    file_path: str
    content: str

class ApplyValidateRequest(BaseModel):
    repo_url: str
    commands: List[str]

class ApplyReviewRequest(BaseModel):
    repo_url: str
    file_path: str
    content: str
    validation_commands: Optional[List[str]] = None

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict]] = None
    repo_url: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: int
    citations: List[Dict] = []

class SessionCreate(BaseModel):
    repo_url: str
    name: Optional[str] = None

class SessionResponse(BaseModel):
    id: int
    name: str
    repo_url: str
    created_at: str
    last_message: Optional[str]

    class Config:
        from_attributes = True
