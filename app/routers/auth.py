from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session as DBSession, select

from ..db import get_session
from ..models import User
from ..auth import hash_pw, verify_pw, make_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

class MeOut(BaseModel):
    id: int
    email: EmailStr

@router.post("/register", response_model=MeOut, status_code=201)
def register(payload: RegisterIn, db: DBSession = Depends(get_session)):
    # unique email
    exists = db.exec(select(User).where(User.email == payload.email.lower())).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    u = User(email=payload.email.lower(), password_hash=hash_pw(payload.password))
    db.add(u); db.commit(); db.refresh(u)
    return MeOut(id=u.id, email=u.email)

@router.post("/login", response_model=MeOut)
def login(payload: LoginIn, response: Response, db: DBSession = Depends(get_session)):
    u = db.exec(select(User).where(User.email == payload.email.lower())).first()
    if not u or not verify_pw(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = make_token(u.id)
    # HttpOnly cookie
    response.set_cookie(
        "access_token", token, httponly=True, secure=False, samesite="lax", max_age=60*60*12, path="/"
    )
    return MeOut(id=u.id, email=u.email)

@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return Response(status_code=204)

@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(id=user.id, email=user.email)