from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import Session as DBSession, select

from .db import get_session
from .models import User

# ---- config ----
JWT_SECRET = "CHANGE_ME_to_a_long_random_secret"   # move to env in production
JWT_ALG    = "HS256"
JWT_TTL    = timedelta(hours=12)

pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_pw(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_pw(p: str, h: str) -> bool:
    return pwd_ctx.verify(p, h)

def make_token(user_id: int) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()),
               "exp": int((now + JWT_TTL).timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def read_token(token: str) -> int:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return int(data.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ---- dependency to protect routes ----
def get_current_user(request: Request, db: DBSession = Depends(get_session)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = read_token(token)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user