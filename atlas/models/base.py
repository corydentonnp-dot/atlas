"""SQLAlchemy declarative base for all Atlas models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
	"""Base class for all SQLAlchemy models."""


class TimestampMixin:
	"""Created/updated timestamp fields."""

	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		nullable=False,
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)


class UUIDPrimaryKeyMixin:
	"""String UUID primary key for portability across backends."""

	id: Mapped[str] = mapped_column(
		String(36),
		primary_key=True,
		default=lambda: str(uuid4()),
	)


class SoftDeleteMixin:
	"""Soft deletion support."""

	deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
