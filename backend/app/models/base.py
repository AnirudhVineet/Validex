"""Column helpers shared by all models."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Naive UTC datetime (stored without tz so SQLite and Postgres behave the same)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def id_column():
    return mapped_column(String(36), primary_key=True, default=new_id)


def enum_column(enum_cls: type[Enum], **kwargs):
    """Store enums as plain strings (portable, readable in the DB)."""
    return mapped_column(SAEnum(enum_cls, native_enum=False, length=40), **kwargs)
