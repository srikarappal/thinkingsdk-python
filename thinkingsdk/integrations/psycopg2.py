"""
Psycopg2 (PostgreSQL) integration for ThinkingSDK.

Tracks raw PostgreSQL queries as breadcrumbs.

Instrumentation goes through psycopg2's own connection_factory / cursor_factory extension points
rather than assigning to attributes on the returned objects. That is not a style preference:
psycopg2.extensions.connection and .cursor are C types with no instance __dict__, so
``conn.cursor = ...`` and ``cursor.execute = ...`` raise AttributeError on every real connection.
Both are subclassable, and subclassing is what psycopg2 documents for exactly this purpose.
"""

import time
from typing import Any
from . import Integration


class Psycopg2Integration(Integration):
    """PostgreSQL psycopg2 integration."""

    identifier = "psycopg2"

    def __init__(self, **options):
        super().__init__(**options)
        self.capture_params = options.get('capture_params', False)

    @staticmethod
    def setup_once():
        """Hook into psycopg2 to track queries."""
        try:
            import psycopg2
            from psycopg2.extensions import connection as _BaseConnection
            from psycopg2.extensions import cursor as _BaseCursor
        except ImportError:
            return  # psycopg2 not installed

        # Idempotent: setup_once() can be reached more than once (a re-init, a test suite calling
        # start() repeatedly). Without this the second pass wraps the wrapper and every query is
        # recorded twice.
        if getattr(psycopg2.connect, "_thinkingsdk_wrapped", False):
            return

        _orig_connect = psycopg2.connect

        class ThinkingCursor(_BaseCursor):
            """Records each statement as a breadcrumb, then gets out of the way."""

            def execute(self, query, vars=None):
                start_time = time.time()
                try:
                    result = super().execute(query, vars)
                except Exception as exc:
                    _add_query_breadcrumb(
                        query=query,
                        params=vars,
                        duration=(time.time() - start_time) * 1000,
                        connection=self.connection,
                        error=str(exc),
                    )
                    raise
                _add_query_breadcrumb(
                    query=query,
                    params=vars,
                    duration=(time.time() - start_time) * 1000,
                    connection=self.connection,
                )
                return result

            def executemany(self, query, vars_list):
                start_time = time.time()
                try:
                    result = super().executemany(query, vars_list)
                except Exception as exc:
                    _add_query_breadcrumb(
                        query=query,
                        params=None,
                        duration=(time.time() - start_time) * 1000,
                        connection=self.connection,
                        error=str(exc),
                        executemany=True,
                    )
                    raise
                _add_query_breadcrumb(
                    query=query,
                    params=f"[{len(vars_list)} sets]" if vars_list else None,
                    duration=(time.time() - start_time) * 1000,
                    connection=self.connection,
                    executemany=True,
                )
                return result

        class ThinkingConnection(_BaseConnection):
            """Hands out ThinkingCursor unless the caller asked for something else."""

            def cursor(self, *args, **kwargs):
                # A caller's own cursor_factory always wins, whether passed here or to connect().
                # RealDictCursor and NamedTupleCursor change what rows look like, so silently
                # replacing one would corrupt results rather than merely lose a breadcrumb.
                if "cursor_factory" not in kwargs and getattr(self, "cursor_factory", None) is None:
                    kwargs["cursor_factory"] = ThinkingCursor
                return super().cursor(*args, **kwargs)

        def _thinking_connect(*args, **kwargs):
            """Return an instrumented connection, unless the caller supplied their own factory."""
            kwargs.setdefault("connection_factory", ThinkingConnection)
            return _orig_connect(*args, **kwargs)

        _thinking_connect._thinkingsdk_wrapped = True
        psycopg2.connect = _thinking_connect


def _add_query_breadcrumb(query, params=None, duration=None, connection=None, error=None, executemany=False):
    """Add a database query breadcrumb."""
    try:
        from .. import _breadcrumb_tracker
        if not _breadcrumb_tracker:
            return

        # Format query
        query_str = str(query)
        if len(query_str) > 200:
            query_str = query_str[:200] + "..."

        # Determine operation
        operation = _get_operation_from_query(query_str)

        # Build breadcrumb data
        data = {
            'db.system': 'postgresql',
            'db.operation': operation,
            'db.statement': query_str,
        }

        # Add connection info if available
        if connection:
            try:
                dsn = connection.get_dsn_parameters()
                if 'dbname' in dsn:
                    data['db.name'] = dsn['dbname']
                if 'host' in dsn:
                    data['server.address'] = dsn['host']
                if 'port' in dsn:
                    data['server.port'] = dsn['port']
            except:
                pass

        # Add duration
        if duration is not None:
            data['duration_ms'] = round(duration, 2)

        # Add params if enabled
        if params and _should_capture_params():
            data['db.params'] = _sanitize_params(params)

        if executemany:
            data['db.executemany'] = True

        # Determine level
        level = "error" if error else "info"
        if error:
            data['error'] = error

        # Add breadcrumb
        message = f"PostgreSQL {operation}"
        if duration:
            message += f" ({round(duration)}ms)"
        if error:
            message += " [FAILED]"

        _breadcrumb_tracker.add_breadcrumb(
            message=message,
            category="db",
            level=level,
            data=data
        )

    except Exception:
        pass  # Never break database operations


def _get_operation_from_query(query_str):
    """Extract operation type from SQL query."""
    query_lower = query_str.lower().strip()

    operations = {
        "select": "SELECT",
        "insert": "INSERT",
        "update": "UPDATE",
        "delete": "DELETE",
        "create": "CREATE",
        "drop": "DROP",
        "alter": "ALTER",
        "begin": "TRANSACTION",
        "commit": "COMMIT",
        "rollback": "ROLLBACK",
    }

    for prefix, operation in operations.items():
        if query_lower.startswith(prefix):
            return operation

    return "query"


def _should_capture_params():
    """Check if we should capture query parameters."""
    try:
        from .. import _integrations
        if _integrations:
            for integration in _integrations:
                if isinstance(integration, Psycopg2Integration):
                    return integration.capture_params
    except:
        pass
    return False


def _sanitize_params(params):
    """Sanitize query parameters."""
    if not params:
        return None

    if isinstance(params, dict):
        safe = {}
        for k, v in params.items():
            if any(s in str(k).lower() for s in ['password', 'token', 'secret', 'key']):
                safe[k] = '***REDACTED***'
            else:
                safe[k] = str(v)[:100] if v else None
        return safe
    elif isinstance(params, (list, tuple)):
        return [str(p)[:100] if p else None for p in params[:10]]
    else:
        return str(params)[:200]