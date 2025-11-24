from __future__ import annotations
from typing import Optional, Any
import datetime as dt
from fastapi import HTTPException


def ensure_owner(obj: Any, user_id: int, what: str = "resource") -> None:
    if not obj or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")


def normalize_whitespace(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    compact = " ".join(value.strip().split())
    return compact or None


def case_insensitive_equal(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


def today() -> dt.date:
    return dt.date.today()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)
