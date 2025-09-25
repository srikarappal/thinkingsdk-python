"""
PyMongo (MongoDB) integration for ThinkingSDK.

Adapted from sentry-sdk's pymongo integration to track MongoDB operations as breadcrumbs.
Uses PyMongo's monitoring API for zero-overhead, non-intrusive tracking.
"""

import copy
import json
from typing import Any, Dict, Union, Optional
from . import Integration


# Safe fields that don't contain PII (from Sentry)
SAFE_COMMAND_ATTRIBUTES = [
    "insert", "ordered", "find", "limit", "singleBatch",
    "aggregate", "createIndexes", "indexes", "delete",
    "findAndModify", "renameCollection", "to", "drop",
    "count", "distinct", "group", "mapReduce"
]


class PyMongoIntegration(Integration):
    """MongoDB pymongo integration."""

    identifier = "pymongo"

    def __init__(self, **options):
        super().__init__(**options)
        self.capture_queries = options.get('capture_queries', True)
        self.sanitize_queries = options.get('sanitize_queries', True)  # Remove PII by default

    @staticmethod
    def setup_once():
        """Register MongoDB command listener."""
        try:
            from pymongo import monitoring

            # Create and register our command listener
            listener = ThinkingCommandListener()
            monitoring.register(listener)

        except ImportError:
            pass  # pymongo not installed


class ThinkingCommandListener:
    """MongoDB command listener that tracks operations as breadcrumbs."""

    def __init__(self):
        self._start_times = {}  # Track operation start times for duration

    def started(self, event):
        """Called when a MongoDB command starts."""
        try:
            import time
            # Store start time for duration calculation
            self._start_times[event.request_id] = time.time()

        except Exception:
            pass

    def succeeded(self, event):
        """Called when a MongoDB command succeeds."""
        try:
            from .. import _breadcrumb_tracker
            if not _breadcrumb_tracker:
                return

            # Calculate duration
            duration = None
            if event.request_id in self._start_times:
                import time
                duration = (time.time() - self._start_times.pop(event.request_id)) * 1000

            # Get command details
            command = dict(copy.deepcopy(event.command))

            # Remove internal MongoDB fields
            command.pop("$db", None)
            command.pop("$clusterTime", None)
            command.pop("$signature", None)
            command.pop("lsid", None)  # Session ID

            # Sanitize PII if needed
            if _should_sanitize():
                command = _strip_pii(command)

            # Build breadcrumb data
            data = {
                'db.system': 'mongodb',
                'db.operation': event.command_name,
                'db.name': event.database_name,
            }

            # Add collection if available
            collection = command.get(event.command_name)
            if collection:
                data['db.mongodb.collection'] = collection

            # Add connection info
            try:
                data['server.address'] = event.connection_id[0]
                data['server.port'] = event.connection_id[1]
            except (TypeError, IndexError):
                pass

            # Add duration
            if duration is not None:
                data['duration_ms'] = round(duration, 2)

            # Add query details (limited to prevent huge breadcrumbs)
            query_str = json.dumps(command, default=str)
            if len(query_str) > 500:
                query_str = query_str[:500] + "..."
            data['db.statement'] = query_str

            # Add breadcrumb
            message = f"MongoDB {event.command_name}"
            if collection:
                message += f" ({collection})"
            if duration:
                message += f" [{round(duration)}ms]"

            _breadcrumb_tracker.add_breadcrumb(
                message=message,
                category="db",
                level="info",
                data=data
            )

        except Exception:
            pass  # Never break MongoDB operations

    def failed(self, event):
        """Called when a MongoDB command fails."""
        try:
            from .. import _breadcrumb_tracker
            if not _breadcrumb_tracker:
                return

            # Calculate duration
            duration = None
            if event.request_id in self._start_times:
                import time
                duration = (time.time() - self._start_times.pop(event.request_id)) * 1000

            # Build error breadcrumb
            data = {
                'db.system': 'mongodb',
                'db.operation': event.command_name,
                'db.name': event.database_name,
                'error': str(event.failure),
            }

            if duration is not None:
                data['duration_ms'] = round(duration, 2)

            # Add breadcrumb
            message = f"MongoDB {event.command_name} [FAILED]"
            if duration:
                message += f" ({round(duration)}ms)"

            _breadcrumb_tracker.add_breadcrumb(
                message=message,
                category="db",
                level="error",
                data=data
            )

        except Exception:
            pass


def _should_sanitize():
    """Check if we should sanitize queries."""
    try:
        from .. import _integrations
        if _integrations:
            for integration in _integrations:
                if isinstance(integration, PyMongoIntegration):
                    return integration.sanitize_queries
    except Exception:
        pass
    return True  # Default to sanitizing


def _strip_pii(command):
    """Remove PII from MongoDB commands (adapted from Sentry)."""
    command = dict(command)  # Work on a copy

    for key in list(command.keys()):
        # Skip safe fields
        if key in SAFE_COMMAND_ATTRIBUTES:
            continue

        # Special handling for update commands
        if key == "update" and "findAndModify" not in command:
            continue

        # Special handling for documents array
        if key == "documents":
            if isinstance(command[key], list):
                command[key] = f"[{len(command[key])} documents]"
            continue

        # Special handling for filter/query fields
        if key in ["filter", "query", "update"]:
            if isinstance(command[key], dict):
                # Just show keys, not values
                command[key] = {k: "***" for k in command[key].keys()}
            continue

        # Special handling for pipeline
        if key == "pipeline":
            if isinstance(command[key], list):
                command[key] = f"[{len(command[key])} stages]"
            continue

        # Default: redact the value
        command[key] = "***REDACTED***"

    return command