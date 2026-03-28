"""Workflow registry — discover, register, and manage workflows."""

from __future__ import annotations

import importlib
import pkgutil

from atlas.core.workflow.base import BaseWorkflow, WorkflowEvent, WorkflowStatus


class WorkflowRegistry:
	"""Registry of instantiated workflows by workflow_id."""

	def __init__(self) -> None:
		self._workflows: dict[str, BaseWorkflow] = {}

	def register(self, workflow: BaseWorkflow) -> None:
		if workflow.workflow_id in self._workflows:
			raise ValueError(f"Workflow already registered: {workflow.workflow_id}")
		self._workflows[workflow.workflow_id] = workflow

	def get(self, workflow_id: str) -> BaseWorkflow:
		if workflow_id not in self._workflows:
			raise KeyError(f"Workflow not found: {workflow_id}")
		return self._workflows[workflow_id]

	def list_all(self) -> list[WorkflowStatus]:
		return [workflow.get_status() for workflow in self._workflows.values()]

	def list_by_category(self, category: str) -> list[WorkflowStatus]:
		return [status for status in self.list_all() if status.category == category]

	def list_active(self) -> list[WorkflowStatus]:
		return [
			workflow.get_status()
			for workflow in self._workflows.values()
			if workflow.get_status().current_state != "idle"
		]

	def get_status(self, workflow_id: str) -> WorkflowStatus:
		return self.get(workflow_id).get_status()

	async def trigger(self, workflow_id: str, event: WorkflowEvent):
		workflow = self.get(workflow_id)
		return await workflow.run(event)

	def auto_discover(self, package: str) -> int:
		"""Import modules and register discovered BaseWorkflow subclasses."""
		imported = importlib.import_module(package)
		registered_count = 0
		for module_info in pkgutil.walk_packages(imported.__path__, prefix=f"{package}."):
			module = importlib.import_module(module_info.name)
			for value in module.__dict__.values():
				if isinstance(value, type) and issubclass(value, BaseWorkflow) and value is not BaseWorkflow:
					workflow = value()
					if workflow.workflow_id not in self._workflows:
						self.register(workflow)
						registered_count += 1
		return registered_count


default_workflow_registry = WorkflowRegistry()
