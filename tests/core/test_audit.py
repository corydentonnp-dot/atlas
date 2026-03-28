"""Tests for the audit service."""

from atlas.core.audit.service import AuditService


def test_audit_log_and_query():
	service = AuditService()
	service.log_action("system", "check", "workflow_a", {"k": "v"}, "ok")
	service.log_action("system", "check", "workflow_b", {"k": "v"}, "ok")

	results = service.query(workflow_id="workflow_a")

	assert len(results) == 1
	assert results[0].workflow_id == "workflow_a"


def test_audit_export_json_bytes():
	service = AuditService()
	service.log_action("system", "check", "workflow_a", {}, "ok")

	data = service.export("json")

	assert isinstance(data, bytes)
	assert b"workflow_a" in data
