"""Tests for the notification service."""

from datetime import datetime

from atlas.core.notifications.service import NotificationPriority, NotificationService


def test_notification_send_delivers_outside_quiet_hours():
	service = NotificationService(quiet_hours_start="23:00", quiet_hours_end="23:30")
	result = service.send("user", "hello", NotificationPriority.NORMAL)

	assert result.delivered is True


def test_notification_digest_queueing_during_quiet_hours():
	service = NotificationService(quiet_hours_start="00:00", quiet_hours_end="23:59")
	queued = service.send("user", "queued", NotificationPriority.NORMAL)
	flushed = service.flush_digest("user")

	assert queued.delivered is False
	assert len(flushed) == 1
	assert "Digest:" in flushed[0].message


def test_high_priority_bypasses_digest():
	service = NotificationService(quiet_hours_start="00:00", quiet_hours_end="23:59")
	result = service.send("user", "urgent", NotificationPriority.HIGH)

	assert result.delivered is True
