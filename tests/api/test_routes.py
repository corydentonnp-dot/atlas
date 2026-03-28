"""Tests for Atlas API routes — health, readiness, workflows, approvals, audit."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import app
from atlas.api.routes import approval_service, audit_service


@pytest.fixture
def client() -> TestClient:
	"""Provide a FastAPI test client."""
	return TestClient(app)


@pytest.fixture(autouse=True)
def reset_services() -> None:
	"""Reset in-memory services before each test."""
	approval_service._approvals.clear()
	audit_service._entries.clear()
	yield


class TestHealthEndpoints:
	"""Tests for health and readiness endpoints."""

	def test_health_returns_ok(self, client: TestClient) -> None:
		"""GET /health returns ok status."""
		response = client.get("/health")
		assert response.status_code == 200

		data = response.json()
		assert data["status"] == "ok"
		assert "timestamp" in data

	def test_ready_checks_dependencies(self, client: TestClient) -> None:
		"""GET /ready checks database and redis."""
		response = client.get("/ready")
		assert response.status_code == 200

		data = response.json()
		assert "status" in data
		assert "database" in data
		assert "redis" in data
		assert isinstance(data["database"], bool)
		assert isinstance(data["redis"], bool)


class TestWorkflowEndpoints:
	"""Tests for workflow error handling."""

	def test_get_workflow_not_found(self, client: TestClient) -> None:
		"""GET /workflows/{id} returns 404 for unknown workflow."""
		response = client.get("/workflows/nonexistent_workflow")
		assert response.status_code == 404

	def test_trigger_workflow_not_found(self, client: TestClient) -> None:
		"""POST /workflows/{id}/trigger returns 404 for unknown workflow."""
		response = client.post(
			"/workflows/nonexistent_workflow/trigger",
			json={"event_type": "test"},
		)
		assert response.status_code == 404


class TestApprovalEndpoints:
	"""Tests for approval management endpoints."""

	def test_list_approvals_empty(self, client: TestClient) -> None:
		"""GET /approvals returns empty list when no approvals exist."""
		response = client.get("/approvals")
		assert response.status_code == 200

		approvals = response.json()
		assert isinstance(approvals, list)
		assert len(approvals) == 0

	def test_approve_approval_not_found(self, client: TestClient) -> None:
		"""POST /approvals/{id}/approve returns 404 for unknown approval."""
		response = client.post("/approvals/nonexistent/approve")
		assert response.status_code == 404

	def test_reject_approval_not_found(self, client: TestClient) -> None:
		"""POST /approvals/{id}/reject returns 404 for unknown approval."""
		response = client.post("/approvals/nonexistent/reject")
		assert response.status_code == 404


class TestAuditEndpoints:
	"""Tests for audit log endpoints."""

	def test_query_audit_empty(self, client: TestClient) -> None:
		"""GET /audit returns empty list when no entries exist."""
		response = client.get("/audit")
		assert response.status_code == 200

		entries = response.json()
		assert isinstance(entries, list)
		assert len(entries) == 0

	def test_query_audit_with_workflow_filter(self, client: TestClient) -> None:
		"""GET /audit?workflow_id=X filters by workflow."""
		response = client.get("/audit?workflow_id=test_workflow")
		assert response.status_code == 200

		entries = response.json()
		assert isinstance(entries, list)

	def test_query_audit_with_action_filter(self, client: TestClient) -> None:
		"""GET /audit?action=X filters by action."""
		response = client.get("/audit?action=workflow_trigger")
		assert response.status_code == 200

		entries = response.json()
		assert isinstance(entries, list)
