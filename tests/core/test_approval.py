"""Tests for the approval service."""

from datetime import datetime, timedelta, timezone

from atlas.core.approval.service import ApprovalService, ApprovalStatus


def test_create_and_resolve_approval():
	service = ApprovalService(ttl_hours=1)
	approval = service.create_approval("workflow_a", "send_email", {"subject": "Hi"}, "approval")

	result = service.resolve_approval(approval.approval_id, "approved", "looks good")

	assert result.status == ApprovalStatus.APPROVED
	assert service.list_pending() == []


def test_expire_stale_approvals():
	service = ApprovalService(ttl_hours=1)
	approval = service.create_approval("workflow_a", "send_email", {}, "approval")
	now = datetime.now(timezone.utc) + timedelta(hours=2)

	expired = service.expire_stale_approvals(now=now)

	assert expired == 1
	assert service.resolve_approval(approval.approval_id, "approved").status == ApprovalStatus.EXPIRED
