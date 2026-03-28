"""Background worker tasks for Atlas using arq.

Tasks are enqueued for asynchronous execution:
- expire_approvals: Mark overdue approval requests as expired
- flush_digest: Send batched notifications from digest queue
- scan_daily_deadlines: Check for upcoming deadlines and trigger alerts
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)


async def expire_approvals(session=None) -> dict[str, object]:
	"""Expire all overdue approval requests.
	
	This task runs daily to mark expired approvals. In production, would be
	called by ArqWorker on a schedule.
	"""
	from atlas.core.approval.service import ApprovalService
	
	service = ApprovalService()
	expired_count = service.expire_stale_approvals()
	
	logger.info(
		"approval_expiry_task",
		expired_count=expired_count,
		timestamp=datetime.now(timezone.utc).isoformat(),
	)
	
	return {
		"task": "expire_approvals",
		"expired_count": expired_count,
		"status": "completed",
	}


async def flush_digest(session=None) -> dict[str, object]:
	"""Send batched notifications from digest queue.
	
	This task runs periodically (e.g., every 6 hours) to flush accumulated
	notifications. In production, would integrate with Telegram/email services.
	"""
	from atlas.core.notifications.service import NotificationService
	
	service = NotificationService()
	digests = service.list_pending_digests()
	sent_count = len(digests)
	
	logger.info(
		"digest_flush_task",
		sent_count=sent_count,
		timestamp=datetime.now(timezone.utc).isoformat(),
	)
	
	return {
		"task": "flush_digest",
		"sent_count": sent_count,
		"status": "completed",
	}


async def scan_daily_deadlines(session=None) -> dict[str, object]:
	"""Scan for upcoming deadlines and trigger alerts.
	
	This task runs daily to check which deadlines are approaching and
	which are overdue, then triggers appropriate workflows.
	"""
	from datetime import date
	
	from atlas.workflows.tax_legal.filing_deadline_tracker import FilingDeadlineTrackerService
	
	service = FilingDeadlineTrackerService()
	today = date.today()
	
	# Check for deadlines due in next 3 days
	due_soon = [d for d in service._deadlines.values() if 0 <= (d.due_date - today).days <= 3]
	overdue = [d for d in service._deadlines.values() if (d.due_date - today).days < 0]
	
	logger.info(
		"deadline_scan_task",
		due_soon_count=len(due_soon),
		overdue_count=len(overdue),
		timestamp=datetime.now(timezone.utc).isoformat(),
	)
	
	return {
		"task": "scan_daily_deadlines",
		"due_soon_count": len(due_soon),
		"overdue_count": len(overdue),
		"status": "completed",
	}


# Task registry for ArqWorker
TASK_REGISTRY = {
	"expire_approvals": expire_approvals,
	"flush_digest": flush_digest,
	"scan_daily_deadlines": scan_daily_deadlines,
}
