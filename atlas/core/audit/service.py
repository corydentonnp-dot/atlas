"""Audit service — write and query the audit log."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.repos.audit_repo import AuditRepository


@dataclass(slots=True)
class AuditEntry:
	actor: str
	action: str
	workflow_id: str
	context: dict[str, object]
	result: str
	entry_id: str = field(default_factory=lambda: str(uuid4()))
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditService:
	"""Audit log supporting both in-memory and async repository modes."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		self._entries: list[AuditEntry] = []
		self._repo: AuditRepository | None = AuditRepository(session) if session else None

	def log_action(
		self,
		actor: str,
		action: str,
		workflow_id: str,
		context: dict[str, object],
		result: str,
	) -> AuditEntry:
		"""Log action (in-memory mode — use log_action_async for persistence)."""
		entry = AuditEntry(
			actor=actor,
			action=action,
			workflow_id=workflow_id,
			context=context,
			result=result,
		)
		self._entries.append(entry)
		return entry

	async def log_action_async(
		self,
		actor: str,
		action: str,
		workflow_id: str | None,
		context: dict[str, object],
		result: str,
		error_message: str | None = None,
	) -> dict[str, object]:
		"""Log action using repository (persisted)."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		entry = await self._repo.create(actor, action, workflow_id, context, result, error_message)
		return {
			"entry_id": str(entry.id),
			"actor": entry.actor,
			"action": entry.action,
			"created_at": entry.created_at.isoformat(),
		}

	def query(
		self,
		workflow_id: str | None = None,
		action: str | None = None,
		limit: int = 100,
		offset: int = 0,
	) -> list[AuditEntry]:
		entries = self._entries
		if workflow_id is not None:
			entries = [entry for entry in entries if entry.workflow_id == workflow_id]
		if action is not None:
			entries = [entry for entry in entries if entry.action == action]
		return entries[offset : offset + limit]

	async def query_async(
		self,
		workflow_id: str | None = None,
		action: str | None = None,
		limit: int = 100,
	) -> list[dict[str, object]]:
		"""Query audit entries using repository."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		if workflow_id and action:
			entries = await self._repo.list_by_actor_and_action("system", action, limit)
		elif workflow_id:
			entries = await self._repo.list_by_workflow(workflow_id, limit)
		elif action:
			entries = await self._repo.list_by_action(action, limit)
		else:
			entries = await self._repo.export_all(limit)
		return [
			{
				"entry_id": str(e.id),
				"actor": e.actor,
				"action": e.action,
				"workflow_id": e.workflow_id,
				"result": e.result,
				"created_at": e.created_at.isoformat(),
			}
			for e in entries
		]

	def count_by_workflow(self, workflow_id: str) -> int:
		return sum(1 for entry in self._entries if entry.workflow_id == workflow_id)

	async def count_by_workflow_async(self, workflow_id: str) -> int:
		"""Count entries for a workflow using repository."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		entries = await self._repo.list_by_workflow(workflow_id)
		return len(entries)

	def export(self, export_format: str = "json") -> bytes:
		if export_format != "json":
			raise ValueError("Only JSON export is currently supported.")
		data = [asdict(entry) for entry in self._entries]
		return json.dumps(data, default=str).encode("utf-8")

	async def export_async(self, export_format: str = "json") -> bytes:
		"""Export all entries using repository."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		if export_format != "json":
			raise ValueError("Only JSON export is currently supported.")
		entries = await self._repo.export_all()
		data = [
			{
				"id": str(e.id),
				"actor": e.actor,
				"action": e.action,
				"workflow_id": e.workflow_id,
				"context": e.context,
				"result": e.result,
				"error_message": e.error_message,
				"created_at": e.created_at.isoformat(),
			}
			for e in entries
		]
		return json.dumps(data, default=str).encode("utf-8")
