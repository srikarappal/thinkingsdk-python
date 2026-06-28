"""
Redis integration for ThinkingSDK.

Adapted from sentry-sdk's redis integration to track Redis operations as breadcrumbs.
Uses monkey-patching with minimal overhead.
"""

from typing import Any
from . import Integration


class RedisIntegration(Integration):
    """Redis cache integration."""

    identifier = "redis"

    def __init__(self, **options):
        super().__init__(**options)
        self.max_data_size = options.get('max_data_size', 100)  # Truncate large values
        self.cache_prefixes = options.get('cache_prefixes', [])  # Track specific key prefixes

    @staticmethod
    def setup_once():
        """Hook into Redis client to track operations."""
        try:
            from redis import StrictRedis, Redis

            # Patch Redis client execute_command
            _patch_redis_execute(StrictRedis)
            _patch_redis_execute(Redis)

            # Patch pipeline execution
            _patch_redis_pipeline()

        except ImportError:
            pass  # redis not installed


def _patch_redis_execute(redis_cls):
    """Patch Redis execute_command to track operations."""
    old_execute = redis_cls.execute_command

    def thinking_execute_command(self, *args, **kwargs):
        """Wrapped execute_command that tracks operations."""
        import time
        start_time = time.time()

        # Get command name and args
        command = args[0] if args else "unknown"
        command_args = args[1:] if len(args) > 1 else []

        try:
            # Call original - user intent flows unchanged
            result = old_execute(self, *args, **kwargs)

            # Track successful operation
            _add_redis_breadcrumb(
                command=command,
                args=command_args,
                duration=(time.time() - start_time) * 1000,
                connection=self
            )

            return result

        except Exception as e:
            # Track failed operation
            _add_redis_breadcrumb(
                command=command,
                args=command_args,
                duration=(time.time() - start_time) * 1000,
                connection=self,
                error=str(e)
            )
            raise  # Re-raise to preserve user flow

    redis_cls.execute_command = thinking_execute_command


def _patch_redis_pipeline():
    """Patch Redis pipeline to track batch operations."""
    try:
        from redis.client import Pipeline

        old_execute = Pipeline.execute

        def thinking_pipeline_execute(self, *args, **kwargs):
            """Wrapped pipeline execute."""
            import time
            start_time = time.time()

            # Count commands in pipeline
            command_count = len(self.command_stack) if hasattr(self, 'command_stack') else 0

            try:
                # Call original
                result = old_execute(self, *args, **kwargs)

                # Track pipeline execution
                _add_redis_breadcrumb(
                    command="PIPELINE",
                    args=[f"{command_count} commands"],
                    duration=(time.time() - start_time) * 1000,
                    connection=self
                )

                return result

            except Exception as e:
                _add_redis_breadcrumb(
                    command="PIPELINE",
                    args=[f"{command_count} commands"],
                    duration=(time.time() - start_time) * 1000,
                    connection=self,
                    error=str(e)
                )
                raise

        Pipeline.execute = thinking_pipeline_execute

    except ImportError:
        pass


def _add_redis_breadcrumb(command, args=None, duration=None, connection=None, error=None):
    """Add a Redis operation breadcrumb."""
    try:
        from .. import _breadcrumb_tracker
        if not _breadcrumb_tracker:
            return

        # Format command for display
        command_upper = str(command).upper()

        # Build breadcrumb data
        data = {
            'db.system': 'redis',
            'db.operation': command_upper,
        }

        # Add connection info if available
        if connection:
            try:
                pool = connection.connection_pool
                if pool:
                    kwargs = pool.connection_kwargs
                    if 'host' in kwargs:
                        data['server.address'] = kwargs['host']
                    if 'port' in kwargs:
                        data['server.port'] = kwargs['port']
                    if 'db' in kwargs:
                        data['db.index'] = kwargs['db']
            except:
                pass

        # Add sanitized args (don't include actual data values)
        if args and _should_capture_args(command_upper):
            sanitized_args = _sanitize_redis_args(command_upper, args)
            if sanitized_args:
                data['db.redis.args'] = sanitized_args

        # Add duration
        if duration is not None:
            data['duration_ms'] = round(duration, 2)

        # Add error if failed
        if error:
            data['error'] = error

        # Determine level
        level = "error" if error else "info"

        # Build message
        message = f"Redis {command_upper}"
        if args and command_upper in ['GET', 'SET', 'DEL', 'HGET', 'HSET']:
            # Show key for common operations
            key = str(args[0]) if args else None
            if key and len(key) < 50:
                message += f" ({key})"
        if duration:
            message += f" [{round(duration)}ms]"
        if error:
            message += " [FAILED]"

        _breadcrumb_tracker.add_breadcrumb(
            message=message,
            category="cache" if _is_cache_operation(command_upper) else "db",
            level=level,
            data=data
        )

    except Exception:
        pass  # Never break Redis operations


def _should_capture_args(command):
    """Determine if we should capture args for this command."""
    # Only capture args for read operations and key-only operations
    safe_commands = {
        'GET', 'MGET', 'EXISTS', 'TYPE', 'TTL', 'PTTL',
        'HGET', 'HMGET', 'HLEN', 'HKEYS', 'HEXISTS',
        'SCARD', 'SISMEMBER', 'SMEMBERS',
        'ZCARD', 'ZCOUNT', 'ZSCORE', 'ZRANK',
        'LLEN', 'LINDEX', 'LRANGE',
        'DEL', 'UNLINK', 'EXPIRE', 'PEXPIRE',
        'KEYS', 'SCAN', 'RANDOMKEY'
    }
    return command in safe_commands


def _sanitize_redis_args(command, args):
    """Sanitize Redis command arguments to avoid logging sensitive data."""
    if not args:
        return None

    # For write operations, only show keys, not values
    if command in ['SET', 'MSET', 'HSET', 'HMSET', 'LPUSH', 'RPUSH', 'SADD', 'ZADD']:
        # Only return the key(s), not the value(s)
        if args:
            key = str(args[0])[:50]  # Truncate long keys
            return [key, '***VALUE***']

    # For read operations, show keys but truncate if too long
    sanitized = []
    for i, arg in enumerate(args[:5]):  # Max 5 args
        arg_str = str(arg)
        if len(arg_str) > 50:
            arg_str = arg_str[:50] + '...'
        sanitized.append(arg_str)

    if len(args) > 5:
        sanitized.append(f'...+{len(args)-5} more')

    return sanitized


def _is_cache_operation(command):
    """Determine if this is a cache operation vs database operation."""
    cache_commands = {
        'GET', 'SET', 'DEL', 'EXISTS', 'EXPIRE', 'TTL',
        'INCR', 'DECR', 'INCRBY', 'DECRBY',
        'MGET', 'MSET', 'SETEX', 'SETNX', 'GETSET'
    }
    return command in cache_commands