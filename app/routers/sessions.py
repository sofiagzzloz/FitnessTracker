from typing import List, Optional
import datetime as dt


from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session as DBSession


from ..db import get_session
from ..auth import get_current_user
from ..models import User
from ..schemas import (
   SessionCreate,
   SessionRead,
   SessionItemCreate,
   SessionItemRead,
)
from ..services import sessions_service as svc


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead, status_code=201)
def create_session(
   payload: SessionCreate,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   return svc.create_session(db=db, user_id=user.id, payload=payload)


@router.get("", response_model=List[SessionRead])
def list_sessions(
   on_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
   start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
   end_date: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   return svc.list_sessions(db=db, user_id=user.id, on_date=on_date, start_date=start_date, end_date=end_date)


@router.get("/{session_id}", response_model=SessionRead)
def read_session(
   session_id: int,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   return svc.read_session(db=db, user_id=user.id, session_id=session_id)


@router.post("/{session_id}/items", response_model=SessionItemRead, status_code=201)
def add_item(
   session_id: int,
   payload: SessionItemCreate,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   return svc.add_item(db=db, user_id=user.id, session_id=session_id, payload=payload)


@router.get("/{session_id}/items", response_model=List[SessionItemRead])
def list_items(
   session_id: int,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   return svc.list_items(db=db, user_id=user.id, session_id=session_id)


class SessionItemUpdate(BaseModel):
   notes: Optional[str] = None
   order_index: Optional[int] = None


@router.patch("/{session_id}/items/{item_id}", response_model=SessionItemRead)
def update_item(
   session_id: int,
   item_id: int,
   payload: SessionItemUpdate,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   return svc.update_item(db=db, user_id=user.id, session_id=session_id, item_id=item_id, notes=payload.notes, order_index=payload.order_index)


@router.delete("/{session_id}/items/{item_id}", status_code=204)
def delete_item(
   session_id: int,
   item_id: int,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   svc.delete_item(db=db, user_id=user.id, session_id=session_id, item_id=item_id)
   return None


@router.delete("/{session_id}", status_code=204)
def delete_session(
   session_id: int,
   db: DBSession = Depends(get_session),
   user: User = Depends(get_current_user),
):
   svc.delete_session(db=db, user_id=user.id, session_id=session_id)
   return None