"""Atlas database session management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from atlas.core.config import AtlasSettings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: AtlasSettings | None = None) -> AsyncEngine:
	"""Create or return the shared async SQLAlchemy engine."""
	global _engine

	if _engine is None:
		resolved_settings = settings or get_settings()
		_engine = create_async_engine(
			resolved_settings.sqlalchemy_database_url,
			echo=resolved_settings.api_debug,
			pool_pre_ping=True,
			future=True,
		)

	return _engine


def get_session_factory(settings: AtlasSettings | None = None) -> async_sessionmaker[AsyncSession]:
	"""Return the shared async session factory."""
	global _session_factory

	if _session_factory is None:
		_session_factory = async_sessionmaker(
			bind=get_engine(settings),
			class_=AsyncSession,
			expire_on_commit=False,
			autoflush=False,
		)

	return _session_factory


@asynccontextmanager
async def session_scope(settings: AtlasSettings | None = None) -> AsyncIterator[AsyncSession]:
	"""Provide a transaction-aware async session context manager."""
	session_factory = get_session_factory(settings)
	session = session_factory()
	try:
		yield session
		await session.commit()
	except Exception:
		await session.rollback()
		raise
	finally:
		await session.close()


async def database_healthcheck(settings: AtlasSettings | None = None) -> bool:
	"""Run a simple query to verify database connectivity."""
	async with session_scope(settings) as session:
		result = await session.execute(text("SELECT 1"))
		return result.scalar_one() == 1


async def dispose_engine() -> None:
	"""Dispose the shared engine during app shutdown."""
	global _engine, _session_factory

	if _engine is not None:
		await _engine.dispose()
	_engine = None
	_session_factory = None
