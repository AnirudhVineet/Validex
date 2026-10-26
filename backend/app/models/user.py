from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import Role
from app.models.base import enum_column, id_column, utcnow


class Institution(Base):
    """A SYNTHETIC institution plus its mock institute record."""

    __tablename__ = "institutions"

    id: Mapped[str] = id_column()
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500), default="")
    state: Mapped[str] = mapped_column(String(100), default="")
    aicte_ref: Mapped[str] = mapped_column(String(50), unique=True)  # fictional identifier
    prior_eoa_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_intake: Mapped[int] = mapped_column(Integer, default=0)
    faculty_count: Mapped[int] = mapped_column(Integer, default=0)
    deficiency_status: Mapped[str] = mapped_column(String(50), default="none")
    ter_payment_status: Mapped[str] = mapped_column(String(50), default="paid")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = id_column()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = enum_column(Role)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
