"""Atlas exceptions — base exception classes and error hierarchy."""

from __future__ import annotations


class AtlasError(Exception):
	"""Base exception for all Atlas errors."""

	def __init__(self, message: str, code: str = "ATLAS_ERROR") -> None:
		self.message = message
		self.code = code
		super().__init__(message)


class NotFoundError(AtlasError):
	"""Resource not found."""

	def __init__(self, resource: str, resource_id: str | None = None) -> None:
		if resource_id:
			message = f"{resource} '{resource_id}' not found"
		else:
			message = f"{resource} not found"
		super().__init__(message, "NOT_FOUND")


class ValidationError(AtlasError):
	"""Input validation failed."""

	def __init__(self, message: str, field: str | None = None) -> None:
		if field:
			message = f"Validation error in '{field}': {message}"
		super().__init__(message, "VALIDATION_ERROR")


class WorkflowError(AtlasError):
	"""Workflow execution failed."""

	def __init__(self, workflow_id: str, message: str) -> None:
		super().__init__(f"Workflow '{workflow_id}' error: {message}", "WORKFLOW_ERROR")


class ApprovalError(AtlasError):
	"""Approval-related error."""

	def __init__(self, message: str) -> None:
		super().__init__(message, "APPROVAL_ERROR")


class PolicyViolationError(AtlasError):
	"""Policy check failed."""

	def __init__(self, policy_name: str, reason: str) -> None:
		super().__init__(
			f"Policy '{policy_name}' violation: {reason}",
			"POLICY_VIOLATION",
		)


class IntegrationError(AtlasError):
	"""Integration adapter error."""

	def __init__(self, integration_name: str, message: str) -> None:
		super().__init__(
			f"Integration '{integration_name}' error: {message}",
			"INTEGRATION_ERROR",
		)


class ConfigurationError(AtlasError):
	"""Configuration or setup error."""

	def __init__(self, message: str) -> None:
		super().__init__(message, "CONFIGURATION_ERROR")
