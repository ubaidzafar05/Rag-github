from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.ingestion import clone_repo, run_repomix, crawl_docs, TEMP_DIR
from services.graph import build_knowledge_graph
from services.chat import get_chat_response
from database import engine, get_db
from db_models import Base, ChatSession, ChatMessage, User
from sqlalchemy.orm import Session
from fastapi import Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os

# Load Auth Keys from parent directory
auth_keys_path = "c:/pyPractice/auth-keys/auth_export/keys/.env"
load_dotenv(auth_keys_path)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Github RAG Chat API")

# Add Session Middleware for Auth (adjust secret_key in production)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth Setup
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Global context storage for MVP (In production, use Redis/DB)
# Mapping: "latest" -> content string
# Or we could map repo_url -> content if we passed it in chat
APP_STATE = {
    "current_repo_content": "",
    "current_repo": "",
    "current_repo_url": ""
}

from services.chat import GENAI_API_KEY
if not GENAI_API_KEY:
    print("WARNING: GENAI_API_KEY is not set. Chat will not functional.")

class IngestRequest(BaseModel):
    repo_url: str
    docs_url: str | None = None

class ApplyRequest(BaseModel):
    file_path: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None

class ChatResponse(BaseModel):
    response: str
    session_id: int

class SessionCreate(BaseModel):
    repo_url: str
    name: str | None = None

class SessionResponse(BaseModel):
    id: int
    name: str
    repo_url: str
    created_at: str
    last_message: str | None

    class Config:
        from_attributes = True

@app.get("/login")
async def login(request: Request):
    # Retrieve redirect_uri from env or build it manually to match Google Console
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") 
    if not redirect_uri:
        # Fallback if env not set, but explicit is better for mismatch errors
        redirect_uri = str(request.url_for('auth'))
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback", name="auth")
async def auth(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        # If token exchange fails
        raise HTTPException(status_code=400, detail=str(e))
        
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # DB: Find or Create User
    user = db.query(User).filter(User.email == user_info['email']).first()
    if not user:
        user = User(
            email=user_info['email'],
            name=user_info.get('name'),
            picture=user_info.get('picture')
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Set Session
    request.session['user'] = {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}
    return RedirectResponse(url='http://localhost:3000')

@app.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='http://localhost:3000')

@app.get("/user/me")
def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Dependency to get current user (for protected routes)
def get_current_user_dep(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Github RAG Chat Backend Running"}

@app.post("/ingest")
def ingest_endpoint(request: IngestRequest):
    try:
        # 1. Clone
        repo_path = clone_repo(request.repo_url)
        # 2. Run Repomix
        packed_content = run_repomix(repo_path)
        
        if not packed_content:
            raise HTTPException(status_code=500, detail="Repomix failed to generate output.")
            
        # 3. (Optional) Crawl Docs
        docs_content = ""
        if request.docs_url:
            docs_content = crawl_docs(request.docs_url)
            packed_content += f"\n\n--- DOCUMENTATION ({request.docs_url}) ---\n{docs_content}"

        # 4. Store in verification
        APP_STATE["current_repo_content"] = packed_content
        APP_STATE["current_repo"] = repo_path
        APP_STATE["current_repo_url"] = request.repo_url
        
        return {"status": "success", "message": "Repository ingested successfully", "size": len(packed_content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions", response_model=SessionResponse)
def create_session(session_in: SessionCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    db_session = ChatSession(repo_url=session_in.repo_url, name=session_in.name or "New Chat", user_id=current_user['id'])
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return SessionResponse(
        id=db_session.id, 
        name=db_session.name, 
        repo_url=db_session.repo_url, 
        created_at=str(db_session.created_at),
        last_message=None
    )

@app.get("/sessions", response_model=list[SessionResponse])
def get_sessions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user['id']).order_by(ChatSession.created_at.desc()).all()
    # Simple serialization
    results = []
    for s in sessions:
        last_msg = None
        if s.messages:
            last_msg = s.messages[-1].content[:50] + "..."
        results.append(SessionResponse(
            id=s.id, name=s.name, repo_url=s.repo_url, created_at=str(s.created_at), last_message=last_msg
        ))
    return results

@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user['id']).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    last_msg = None
    if session.messages:
        last_msg = session.messages[-1].content[:50] + "..."
        
    return SessionResponse(
        id=session.id, 
        name=session.name, 
        repo_url=session.repo_url, 
        created_at=str(session.created_at), 
        last_message=last_msg
    )

@app.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user['id']).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted"}

@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user['id']).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return [{"role": m.role, "content": m.content} for m in session.messages]

@app.get("/graph")
def get_graph(repo_url: str):
    # Check if this is the active repo
    if APP_STATE.get("current_repo_url") == repo_url and APP_STATE.get("current_repo"):
        target_dir = Path(APP_STATE["current_repo"])
    else:
        # Fallback to default name if state lost (might fail if we used timestamp)
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        target_dir = TEMP_DIR / repo_name
    
    if not target_dir.exists():
         raise HTTPException(status_code=404, detail="Repository not found. Please ingest first.")
         
    return build_knowledge_graph(str(target_dir))

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, session_id: int | None = None, db: Session = Depends(get_db)):
    # ... (existing chat logic)
    context = APP_STATE.get("current_repo_content", "")
    if not context:
        return ChatResponse(response="Please ingest a repository first.", session_id=session_id or 0)

    try:
        # 3. Call Gemini
        answer = get_chat_response(request.message, request.history or [], context)
        
        # 4. Persist if we have a session_id
        if session_id:
            user_msg = ChatMessage(session_id=session_id, role="user", content=request.message)
            ai_msg = ChatMessage(session_id=session_id, role="model", content=answer)
            db.add(user_msg)
            db.add(ai_msg)
            db.commit()
            
        return ChatResponse(response=answer, session_id=session_id or 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from services.editor import apply_code_patch

@app.post("/apply")
def apply_fix(request: ApplyRequest):
    repo_path = APP_STATE.get("current_repo")
    if not repo_path:
        raise HTTPException(status_code=400, detail="No repository ingested.")
    
    try:
        apply_code_patch(repo_path, request.file_path, request.content)
        return {"status": "success", "message": f"Applied fix to {request.file_path}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
