from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from db_models import RepoIngestion, ChatSession, ChatMessage
from schemas import ChatRequest, ChatResponse
from services.chat import get_chat_response
from services.retrieval import build_index, format_chunks, load_index, retrieve, save_index
from services.graph import build_knowledge_graph

router = APIRouter(tags=["chat"])

def get_repo_ingestion(db: Session, repo_url: str) -> RepoIngestion | None:
    return db.query(RepoIngestion).filter(RepoIngestion.repo_url == repo_url).first()

@router.get("/graph")
def get_graph(repo_url: str, db: Session = Depends(get_db)):
    ingestion = get_repo_ingestion(db, repo_url)
    if not ingestion or not ingestion.local_path:
        raise HTTPException(status_code=404, detail="Repository not ingested or path lost.")
    
    target_dir = Path(ingestion.local_path)
    
    if not target_dir.exists():
         raise HTTPException(status_code=404, detail="Repository not found. Please ingest first.")
         
    return build_knowledge_graph(str(target_dir))

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    session_id: int | None = None,
    db: Session = Depends(get_db),
    http_request: Request = None,
):
    current_user = None
    repo_url = request.repo_url
    context = ""
    repo_index = ""
    repo_path = None
    
    try:
        history = request.history or []
        if session_id:
            current_user = http_request.session.get("user") if http_request else None
            if not current_user:
                raise HTTPException(status_code=401, detail="Not authenticated")
                
            session = (
                db.query(ChatSession)
                .filter(ChatSession.id == session_id, ChatSession.user_id == current_user["id"])
                .first()
            )
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            repo_url = session.repo_url
            history = [{"role": msg.role, "content": msg.content} for msg in session.messages]

        # Load context from DB
        if repo_url:
             ingestion = get_repo_ingestion(db, repo_url)
             if ingestion:
                 context = ingestion.content
                 repo_index = ingestion.repo_index
                 repo_path = ingestion.local_path
        
        if not context:
            return ChatResponse(
                response="Please ingest a repository first.",
                session_id=session_id or 0,
                citations=[],
            )

        # Retrieval Index loading
        retrieval_index = None
        if repo_path:
             retrieval_index = load_index(repo_path, repo_url)
             if not retrieval_index:
                 retrieval_index = build_index(repo_path)
                 save_index(repo_path, retrieval_index, repo_url)

        snippets = retrieve(request.message, retrieval_index) if retrieval_index else []
        snippet_context = format_chunks(snippets)
        citations = [
            {
                "path": snippet.path,
                "start_line": snippet.start_line,
                "end_line": snippet.end_line,
            }
            for snippet in snippets
        ]

        # Call Gemini
        answer = get_chat_response(
            request.message,
            history,
            snippet_context,
            repo_url,
            repo_index,
        )
        
        # Persist if we have a session_id
        if session_id:
            user_msg = ChatMessage(session_id=session_id, role="user", content=request.message)
            ai_msg = ChatMessage(session_id=session_id, role="model", content=answer)
            db.add(user_msg)
            db.add(ai_msg)
            db.commit()
            
        return ChatResponse(response=answer, session_id=session_id or 0, citations=citations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
