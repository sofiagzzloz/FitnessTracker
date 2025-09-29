from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import Session as DBSession, select

from .db import get_session
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---- cookie config (use SAME values for set & delete) ----
SESSION_COOKIE   = "session"
COOKIE_PATH      = "/"
COOKIE_DOMAIN    = None       # keep None on localhost; set your domain in prod
COOKIE_SAMESITE  = "lax"
COOKIE_SECURE    = False      # True only on HTTPS

# ---- token config ----
JWT_SECRET = "CHANGE_ME_to_a_long_random_secret"   # move to env in prod
JWT_ALG    = "HS256"
JWT_TTL    = timedelta(hours=12)

# ---- password hashing ----
# pip install "passlib[argon2]"
pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_pw(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_pw(p: str, h: str) -> bool:
    return pwd_ctx.verify(p, h)

# ---- JWT helpers ----
def make_token(user_id: int) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + JWT_TTL).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def read_token(token: str) -> int:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return int(data.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ---- cookie helpers ----
def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
        max_age=int(JWT_TTL.total_seconds()),
    )

def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
    )

# ---- dependencies ----
def get_current_user(request: Request, db: DBSession = Depends(get_session)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = read_token(token)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_optional_user(request: Request, db: DBSession = Depends(get_session)) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        user_id = read_token(token)
    except HTTPException:
        return None
    return db.get(User, user_id)

# ---- schemas ----
class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

# ---- routes ----
@router.post("/register")
def register(payload: RegisterIn, response: Response, db: DBSession = Depends(get_session)):
    email = payload.email.lower().strip()
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # unique email
    exists = db.exec(select(User).where(User.email == email)).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")

    u = User(email=email, password_hash=hash_pw(payload.password))
    db.add(u)
    db.commit()
    db.refresh(u)

    # optional: auto-login on register
    token = make_token(u.id)
    set_session_cookie(response, token)
    return {"ok": True, "user": {"id": u.id, "email": u.email}}

@router.post("/login")
def login(payload: LoginIn, response: Response, db: DBSession = Depends(get_session)):
    email = payload.email.lower().strip()
    u = db.exec(select(User).where(User.email == email)).first()
    if not u or not verify_pw(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = make_token(u.id)
    set_session_cookie(response, token)
    return {"ok": True, "user": {"id": u.id, "email": u.email}}

@router.post("/logout")
def api_logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}

@router.get("/debug-cookie")
def debug_cookie(request: Request):
    return {"cookies": dict(request.cookies)}