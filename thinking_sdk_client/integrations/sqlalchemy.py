"""
SQLAlchemy integration for ThinkingSDK.

Adapted from sentry-sdk's SQLAlchemy integration to track database queries as breadcrumbs.
"""

from typing import Any, Optional
from . import Integration


class SQLAlchemyIntegration(Integration):
    """SQLAlchemy ORM integration."""

    identifier = "sqlalchemy"

    def __init__(self, **options):
        super().__init__(**options)
        self.capture_params = options.get('capture_params', False)  # Privacy concern

    @staticmethod
    def setup_once():
        """Hook into SQLAlchemy to track queries as breadcrumbs."""
        try:
            from sqlalchemy.engine import Engine
            from sqlalchemy.event import listen

            # Listen to SQLAlchemy events (same as Sentry)
            listen(Engine, "before_cursor_execute", _before_cursor_execute, propagate=True)
            listen(Engine, "after_cursor_execute", _after_cursor_execute, propagate=True)
            listen(Engine, "handle_error", _handle_error, propagate=True)

        except ImportError:
            pass  # SQLAlchemy not installed


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query start."""
    try:
        import time
        # Store start time for duration calculation
        context._thinking_query_start = time.time()
        context._thinking_query_statement = statement
        context._thinking_query_params = parameters if _should_capture_params() else None
    except Exception:
        pass


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query completion as breadcrumb."""
    try:
        from .. import _breadcrumb_tracker
        if not _breadcrumb_tracker:
            return

        import time
        duration = None
        if hasattr(context, '_thinking_query_start'):
            duration = (time.time() - context._thinking_query_start) * 1000  # Convert to ms

        # Format query for display
        query_str = str(statement)
        if len(query_str) > 200:
            query_str = query_str[:200] + "..."

        # Determine operation type
        operation = _get_operation_from_query(query_str)

        # Build breadcrumb data
        data = {
            'db.operation': operation,
            'db.statement': query_str,
        }

        # Add connection info
        db_system = _get_db_system(conn.engine.name)
        if db_system:
            data['db.system'] = db_system

        if conn.engine.url:
            if conn.engine.url.database:
                data['db.name'] = conn.engine.url.database
            if conn.engine.url.host:
                data['server.address'] = conn.engine.url.host
            if conn.engine.url.port:
                data['server.port'] = conn.engine.url.port

        # Add duration if available
        if duration is not None:
            data['duration_ms'] = round(duration, 2)

        # Add params if enabled and available
        if hasattr(context, '_thinking_query_params') and context._thinking_query_params:
            data['db.params'] = _sanitize_params(context._thinking_query_params)

        if executemany:
            data['db.executemany'] = True

        # Add breadcrumb
        _breadcrumb_tracker.add_breadcrumb(
            message=f"Database {operation}" + (f" ({round(duration)}ms)" if duration else ""),
            category="db",
            level="info",
            data=data
        )

        # Clean up context
        for attr in ['_thinking_query_start', '_thinking_query_statement', '_thinking_query_params']:
            if hasattr(context, attr):
                delattr(context, attr)

    except Exception:
        pass  # Never break database operations


def _handle_error(context, *args):
    """Track database errors as breadcrumbs."""
    try:
        from .. import _breadcrumb_tracker
        if not _breadcrumb_tracker:
            return

        execution_context = context.execution_context
        if execution_context is None:
            return

        statement = getattr(execution_context, '_thinking_query_statement', 'Unknown query')

        # Add error breadcrumb
        _breadcrumb_tracker.add_breadcrumb(
            message=f"Database error",
            category="db",
            level="error",
            data={
                'db.statement': str(statement)[:200],
                'error': str(context.original_exception) if hasattr(context, 'original_exception') else 'Unknown error'
            }
        )

    except Exception:
        pass


def _get_operation_from_query(query_str):
    """Extract operation type from SQL query."""
    query_lower = query_str.lower().strip()
    if query_lower.startswith("select"):
        return "SELECT"
    elif query_lower.startswith("insert"):
        return "INSERT"
    elif query_lower.startswith("update"):
        return "UPDATE"
    elif query_lower.startswith("delete"):
        return "DELETE"
    elif query_lower.startswith("create"):
        return "CREATE"
    elif query_lower.startswith("drop"):
        return "DROP"
    elif query_lower.startswith("alter"):
        return "ALTER"
    else:
        return "query"


def _get_db_system(name):
    """Determine database system from engine name (from Sentry)."""
    name = str(name)

    if "sqlite" in name:
        return "sqlite"
    if "postgres" in name or "postgresql" in name:
        return "postgresql"
    if "mariadb" in name:
        return "mariadb"
    if "mysql" in name:
        return "mysql"
    if "oracle" in name:
        return "oracle"
    if "mssql" in name or "pyodbc" in name:
        return "mssql"

    return None


def _should_capture_params():
    """Check if we should capture query parameters."""
    try:
        from .. import _integrations
        if _integrations:
            for integration in _integrations:
                if isinstance(integration, SQLAlchemyIntegration):
                    return integration.capture_params
    except Exception:
        pass
    return False


def _sanitize_params(params):
    """Sanitize query parameters to avoid logging sensitive data."""
    if not params:
        return None

    if isinstance(params, dict):
        safe_params = {}
        for key, value in params.items():
            if any(sensitive in str(key).lower() for sensitive in
                   ['password', 'passwd', 'token', 'secret', 'key', 'auth']):
                safe_params[key] = '***REDACTED***'
            else:
                # Truncate long values
                if isinstance(value, str) and len(value) > 100:
                    safe_params[key] = value[:100] + '...'
                else:
                    safe_params[key] = value
        return safe_params
    elif isinstance(params, (list, tuple)):
        # For positional params, just truncate if too long
        return [str(p)[:100] if len(str(p)) > 100 else p for p in params[:10]]
    else:
        return str(params)[:200]