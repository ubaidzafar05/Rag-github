from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from db_models import ChatSession
from schemas import SessionCreate, SessionResponse
from dependencies import get_current_user_dep

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("", response_model=SessionResponse)
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

@router.get("", response_model=list[SessionResponse])
def get_sessions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user['id']).order_by(ChatSession.created_at.desc()).all()
    results = []
    for s in sessions:
        last_msg = None
        if s.messages:
            last_msg = s.messages[-1].content[:50] + "..."
        results.append(SessionResponse(
            id=s.id, name=s.name, repo_url=s.repo_url, created_at=str(s.created_at), last_message=last_msg
        ))
    return results

@router.get("/{session_id}", response_model=SessionResponse)
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

@router.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user['id']).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted"}

@router.get("/{session_id}/messages")
def get_session_messages(session_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dep)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user['id']).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return [{"role": m.role, "content": m.content} for m in session.messages]
