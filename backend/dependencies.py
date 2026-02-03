from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db

def get_current_user_dep(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def get_optional_user_dep(request: Request):
    return request.session.get('user')
