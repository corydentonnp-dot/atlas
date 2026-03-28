"""Notification service — route and deliver notifications."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError


class NotificationPriority(StrEnum):
	LOW = "low"
	NORMAL = "normal"
	HIGH = "high"


@dataclass(slots=True)
class NotificationMessage:
	recipient: str
	message: str
	priority: NotificationPriority = NotificationPriority.NORMAL
	channel: str = "log"
	created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True, slots=True)
class NotificationResult:
	delivered: bool
	channel: str
	recipient: str
	message: str
	reason: str = ""


class NotificationService:
	"""Notification router with digest support for quiet hours."""

	def __init__(
		self,
		quiet_hours_start: str = "22:00",
		quiet_hours_end: str = "07:00",
		timezone_name: str = "America/New_York",
	) -> None:
		self._quiet_hours_start = self._parse_hhmm(quiet_hours_start)
		self._quiet_hours_end = self._parse_hhmm(quiet_hours_end)
		try:
			self._timezone = ZoneInfo(timezone_name)
		except ZoneInfoNotFoundError:
			self._timezone = timezone.utc
		self._channels: dict[str, Callable[[NotificationMessage], NotificationResult]] = {
			"log": self._log_channel
		}
		self._digest_queue: list[NotificationMessage] = []

	def _parse_hhmm(self, value: str) -> time:
		hour_str, minute_str = value.split(":")
		return time(hour=int(hour_str), minute=int(minute_str))

	def register_channel(
		self,
		name: str,
		channel_impl: Callable[[NotificationMessage], NotificationResult],
	) -> None:
		self._channels[name] = channel_impl

	def is_quiet_hours(self, now: datetime | None = None) -> bool:
		local = (now or datetime.now(tz=self._timezone)).astimezone(self._timezone).time()
		if self._quiet_hours_start <= self._quiet_hours_end:
			return self._quiet_hours_start <= local < self._quiet_hours_end
		return local >= self._quiet_hours_start or local < self._quiet_hours_end

	def send(
		self,
		recipient: str,
		message: str,
		priority: NotificationPriority = NotificationPriority.NORMAL,
		channel: str = "log",
	) -> NotificationResult:
		notification = NotificationMessage(
			recipient=recipient,
			message=message,
			priority=priority,
			channel=channel,
		)

		if self.is_quiet_hours() and priority != NotificationPriority.HIGH:
			self.queue_for_digest(notification)
			return NotificationResult(False, channel, recipient, message, "Queued for digest due to quiet hours.")

		channel_fn = self._channels.get(channel, self._channels["log"])
		return channel_fn(notification)

	def send_approval_request(self, recipient: str, approval_id: str, workflow_id: str) -> NotificationResult:
		message = f"Approval needed: {workflow_id} ({approval_id})"
		return self.send(recipient, message, priority=NotificationPriority.HIGH, channel="log")

	def queue_for_digest(self, notification: NotificationMessage) -> None:
		self._digest_queue.append(notification)

	def flush_digest(self, recipient: str, channel: str = "log") -> list[NotificationResult]:
		if not self._digest_queue:
			return []

		joined = "\n".join(f"- {item.message}" for item in self._digest_queue)
		self._digest_queue.clear()
		return [self.send(recipient, f"Digest:\n{joined}", NotificationPriority.NORMAL, channel)]

	def _log_channel(self, notification: NotificationMessage) -> NotificationResult:
		return NotificationResult(
			delivered=True,
			channel="log",
			recipient=notification.recipient,
			message=notification.message,
		)
