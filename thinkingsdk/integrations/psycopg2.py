"""
Psycopg2 (PostgreSQL) integration for ThinkingSDK.

Tracks raw PostgreSQL queries as breadcrumbs.
"""

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

            # Store original connect
            _orig_connect = psycopg2.connect

            # We can't patch cursor directly (immutable C type)
            # Instead, wrap the connection's cursor() method
            def _thinking_connect(*args, **kwargs):
                """Wrapped connect that returns instrumented connection."""
                conn = _orig_connect(*args, **kwargs)

                # Wrap the cursor method
                _orig_cursor = conn.cursor

                def _wrapped_cursor(*cursor_args, **cursor_kwargs):
                    """Return an instrumented cursor."""
                    cursor = _orig_cursor(*cursor_args, **cursor_kwargs)

                    # Store original methods
                    _orig_execute = cursor.execute
                    _orig_executemany = cursor.executemany

                    def _thinking_execute(query, vars=None):
                        """Wrapped execute that tracks queries."""
                        import time
                        start_time = time.time()

                        try:
                            # Call original
                            result = _orig_execute(query, vars)

                            # Track as breadcrumb
                            _add_query_breadcrumb(
                                query=query,
                                params=vars,
                                duration=(time.time() - start_time) * 1000,
                                connection=conn
                            )

                            return result

                        except Exception as e:
                            # Track error
                            _add_query_breadcrumb(
                                query=query,
                                params=vars,
                                duration=(time.time() - start_time) * 1000,
                                connection=conn,
                                error=str(e)
                            )
                            raise

                    def _thinking_executemany(query, vars_list):
                        """Wrapped executemany that tracks queries."""
                        import time
                        start_time = time.time()

                        try:
                            result = _orig_executemany(query, vars_list)

                            _add_query_breadcrumb(
                                query=query,
                                params=f"[{len(vars_list)} sets]" if vars_list else None,
                                duration=(time.time() - start_time) * 1000,
                                connection=conn,
                                executemany=True
                            )

                            return result

                        except Exception as e:
                            _add_query_breadcrumb(
                                query=query,
                                params=None,
                                duration=(time.time() - start_time) * 1000,
                                connection=conn,
                                error=str(e),
                                executemany=True
                            )
                            raise

                    # Replace methods on this cursor instance
                    cursor.execute = _thinking_execute
                    cursor.executemany = _thinking_executemany

                    return cursor

                conn.cursor = _wrapped_cursor
                return conn

            # Replace psycopg2.connect
            psycopg2.connect = _thinking_connect

        except ImportError:
            pass  # psycopg2 not installed


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