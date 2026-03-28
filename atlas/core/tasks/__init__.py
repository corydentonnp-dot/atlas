"""Atlas task/job execution layer — async task queue via arq.

Background worker tasks for automating maintenance operations:
- expire_approvals: Mark overdue approval requests as expired (daily)
- flush_digest: Send batched notifications from digest queue (6 hourly)
- scan_daily_deadlines: Check for upcoming deadlines and trigger alerts (daily)

In production, these tasks run via ArqWorker with scheduled triggers.
For development, can be invoked directly via task module functions.
"""

from atlas.core.tasks.tasks import TASK_REGISTRY, expire_approvals, flush_digest, scan_daily_deadlines

__all__ = ["expire_approvals", "flush_digest", "scan_daily_deadlines", "TASK_REGISTRY"]

