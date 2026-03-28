"""Atlas structured logging setup."""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from atlas.core.config import AtlasSettings, get_settings

_SENSITIVE_KEYS = {
	"password",
	"token",
	"secret",
	"authorization",
	"api_key",
	"access_token",
	"refresh_token",
}


def _redact_sensitive_data(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
	for key, value in list(event_dict.items()):
		if any(sensitive_key in key.lower() for sensitive_key in _SENSITIVE_KEYS):
			event_dict[key] = "***REDACTED***"
			continue

		if isinstance(value, dict):
			_redact_sensitive_data(None, "", value)

	return event_dict


def configure_logging(settings: AtlasSettings | None = None) -> None:
	"""Configure stdlib logging and structlog processors."""
	resolved_settings = settings or get_settings()
	log_level = getattr(logging, resolved_settings.log_level.upper(), logging.INFO)

	shared_processors = [
		structlog.contextvars.merge_contextvars,
		structlog.stdlib.add_log_level,
		structlog.stdlib.add_logger_name,
		structlog.processors.TimeStamper(fmt="iso", utc=True),
		_redact_sensitive_data,
	]

	logging.basicConfig(
		format="%(message)s",
		stream=sys.stdout,
		level=log_level,
		force=True,
	)

	renderer: structlog.types.Processor
	if resolved_settings.log_format.lower() == "json":
		renderer = structlog.processors.JSONRenderer()
	else:
		renderer = structlog.dev.ConsoleRenderer(colors=True)

	structlog.configure(
		processors=[
			*shared_processors,
			structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
		],
		logger_factory=structlog.stdlib.LoggerFactory(),
		wrapper_class=structlog.stdlib.BoundLogger,
		cache_logger_on_first_use=True,
	)

	formatter = structlog.stdlib.ProcessorFormatter(
		processor=renderer,
		foreign_pre_chain=shared_processors,
	)

	root_logger = logging.getLogger()
	for handler in root_logger.handlers:
		handler.setFormatter(formatter)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
	"""Return a configured structured logger."""
	return structlog.get_logger(name)
