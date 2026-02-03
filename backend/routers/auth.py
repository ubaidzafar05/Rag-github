from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from db_models import User
from database import get_db
from core.security import oauth
from core.config import settings

router = APIRouter()

@router.get("/login")
async def login(request: Request):
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    if not redirect_uri:
        redirect_uri = str(request.url_for('auth'))
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback", name="auth")
async def auth(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

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

    request.session['user'] = {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}
    return RedirectResponse(url='http://localhost:3000')

@router.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='http://localhost:3000')

@router.get("/user/me")
def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
