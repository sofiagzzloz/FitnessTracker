from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session as DBSession, select

from ..db import get_session
from ..models import User
from ..auth import (
    hash_pw,
    verify_pw,
    make_token,
    get_current_user,
    ACCESS_COOKIE,
    JWT_TTL,
)

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
    email = payload.email.lower()
    exists = db.exec(select(User).where(User.email == email)).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    u = User(email=email, password_hash=hash_pw(payload.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return MeOut(id=u.id, email=u.email)


@router.post("/login", response_model=MeOut)
def login(payload: LoginIn, response: Response, db: DBSession = Depends(get_session)):
    email = payload.email.lower()
    u = db.exec(select(User).where(User.email == email)).first()
    if not u or not verify_pw(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = make_token(u.id)
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        httponly=True,
        secure=False,  # True in prod (HTTPS)
        samesite="lax",
        path="/",
        max_age=int(JWT_TTL.total_seconds()),
    )
    return MeOut(id=u.id, email=u.email)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(key=ACCESS_COOKIE, path="/")
    return


@router.get("/me", response_model=MeOut)
def me(user: User | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return MeOut(id=user.id, email=user.email)
