"""
Logging integration for ThinkingSDK.

Adapted from sentry-sdk's logging integration to capture log messages as breadcrumbs.
"""

import logging
import sys
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Dict, Any, Optional, Set
from . import Integration


# Ignored loggers to prevent recursion
_IGNORED_LOGGERS = set([
    "thinking_sdk*",
    "urllib3.connectionpool",
    "urllib3.connection"
])

# Map logging levels to breadcrumb levels
LOGGING_TO_BREADCRUMB_LEVEL = {
    logging.NOTSET: "notset",
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARN: "warning",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.FATAL: "fatal",
    logging.CRITICAL: "fatal",
}


def ignore_logger(name: str) -> None:
    """Ignore a specific logger from being captured."""
    _IGNORED_LOGGERS.add(name)


class LoggingIntegration(Integration):
    """Python logging framework integration."""

    identifier = "logging"

    def __init__(
        self,
        level: Optional[int] = logging.INFO,
        event_level: Optional[int] = logging.ERROR,
    ):
        """
        Initialize the logging integration.

        Args:
            level: Minimum level for breadcrumbs (default: INFO)
            event_level: Minimum level for events (default: ERROR)
        """
        super().__init__()
        self._breadcrumb_handler = None

        if level is not None:
            self._breadcrumb_handler = BreadcrumbHandler(level=level)

    def setup_once(self):
        """Hook into Python logging to capture messages as breadcrumbs."""
        old_callhandlers = logging.Logger.callHandlers

        def thinking_patched_callhandlers(self, record):
            # Keep a local reference to avoid issues during shutdown
            ignored_loggers = _IGNORED_LOGGERS

            try:
                return old_callhandlers(self, record)
            finally:
                # Check if we should ignore this logger
                if ignored_loggers is not None and record.name not in ignored_loggers:
                    # Check patterns
                    should_ignore = False
                    for pattern in ignored_loggers:
                        if fnmatch(record.name, pattern):
                            should_ignore = True
                            break

                    if not should_ignore:
                        # Get the integration instance
                        from .. import _integrations
                        if _integrations:
                            for integration in _integrations:
                                if isinstance(integration, LoggingIntegration):
                                    integration._handle_record(record)
                                    break

        logging.Logger.callHandlers = thinking_patched_callhandlers

    def _handle_record(self, record):
        """Process a log record."""
        if self._breadcrumb_handler is not None and record.levelno >= self._breadcrumb_handler.level:
            self._breadcrumb_handler.handle(record)


class _BaseHandler(logging.Handler):
    """Base handler with common functionality."""

    COMMON_RECORD_ATTRS = frozenset((
        "args", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "message",
        "module", "msecs", "msg", "name", "pathname", "process",
        "processName", "relativeCreated", "stack", "tags",
        "taskName", "thread", "threadName", "stack_info",
    ))

    def _can_record(self, record) -> bool:
        """Check if we should record this logger."""
        for logger in _IGNORED_LOGGERS:
            if fnmatch(record.name.strip(), logger):
                return False
        return True

    def _logging_to_breadcrumb_level(self, record) -> str:
        """Convert logging level to breadcrumb level."""
        return LOGGING_TO_BREADCRUMB_LEVEL.get(
            record.levelno,
            record.levelname.lower() if record.levelname else ""
        )

    def _extra_from_record(self, record) -> Dict[str, Any]:
        """Extract extra data from log record."""
        return {
            k: v
            for k, v in vars(record).items()
            if k not in self.COMMON_RECORD_ATTRS
            and (not isinstance(k, str) or not k.startswith("_"))
        }


class BreadcrumbHandler(_BaseHandler):
    """Handler that records log messages as breadcrumbs."""

    def emit(self, record):
        """Emit a log record as a breadcrumb."""
        try:
            self.format(record)
            return self._emit(record)
        except Exception:
            pass  # Never break logging

    def _emit(self, record):
        """Internal emit implementation."""
        if not self._can_record(record):
            return

        # Get breadcrumb tracker
        from .. import _breadcrumb_tracker
        if not _breadcrumb_tracker:
            return

        breadcrumb_data = self._breadcrumb_from_record(record)
        _breadcrumb_tracker.add_breadcrumb(
            message=breadcrumb_data["message"],
            category=breadcrumb_data["category"],
            level=breadcrumb_data["level"],
            data=breadcrumb_data.get("data")
        )

    def _breadcrumb_from_record(self, record) -> Dict[str, Any]:
        """Convert log record to breadcrumb."""
        return {
            "type": "log",
            "level": self._logging_to_breadcrumb_level(record),
            "category": record.name,
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc),
            "data": self._extra_from_record(record),
        }