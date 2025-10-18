# thinking_sdk_client/__init__.py
"""
Production-grade ThinkingSDK client. Usage inside user code:

    import thinking_sdk_client as thinking
    
    # Basic usage
    thinking.start(api_key="sk_live_XXXX")
    
    # Advanced usage with configuration
    config = {
        'instrumentation': {'sample_rate': 0.5, 'capture_returns': True},
        'sender': {'batch_size': 100, 'retry_attempts': 5},
        'queue': {'maxsize': 20000}
    }
    thinking.start(api_key="sk_live_XXXX", config=config)

    # Get statistics
    stats = thinking.get_stats()

    # Clean shutdown
    thinking.stop()
"""

import os
import logging
import atexit
from typing import Dict, Any, Optional, List

from ._version import __version__, __version_info__
from .instrumentation import RuntimeInstrumentation
from .background_sender import BackgroundSender
from .event_queue import EventQueue
from .config import Config
from .config_loader import ConfigLoader
from .context import context, set_context, clear_context, add_context
from .event_deduplicator import EventDeduplicator
from .pii_scrubber import PIIScrubber
from .custom_events import BreadcrumbTracker, CustomEventTracker, Timer
from .enhanced_queue import EnhancedEventQueue

# Module-level state
_instrumentation: Optional[RuntimeInstrumentation] = None
_sender: Optional[BackgroundSender] = None
_queue: Optional[EventQueue] = None
_config: Optional[Config] = None
_deduplicator: Optional[EventDeduplicator] = None
_pii_scrubber: Optional[PIIScrubber] = None
_breadcrumb_tracker: Optional[BreadcrumbTracker] = None
_custom_event_tracker: Optional[CustomEventTracker] = None
_integrations: Optional[List] = None

#TODO: rethink hard stopping exceptions for all methods (e.g. raise Exceptions)
# This is a production-grade SDK, so we want to avoid raising exceptions
# unless absolutely necessary. Most methods will log errors instead of raising.
# However, some critical methods like start() and stop() will raise if called incorrectly.
# This should not hinder normal usage, but rather help catch misconfigurations early.

def start(
    api_key: Optional[str] = None, 
    server_url: Optional[str] = None, 
    config: Optional[Dict[str, Any]] = None,
    config_file: Optional[str] = None,
    enable_logging: Optional[bool] = None
) -> None:
    """
    Start ThinkingSDK instrumentation and background sending.
    
    Args:
        api_key: API key for authentication (overrides config file)
        server_url: Base URL of the ThinkingSDK server (overrides config file)
        config: Optional configuration dictionary (overrides config file)
        config_file: Path to YAML config file (default: searches for thinkingsdk.yaml)
        enable_logging: Enable logging for debugging (overrides config file)
    
    Priority: function args > config dict > config file > defaults
    
    Raises:
        RuntimeError: If SDK is already started
    """
    global _instrumentation, _sender, _queue, _config
    
    # Check for disable flag - this takes precedence over everything
    if os.environ.get('THINKINGSDK_DISABLE_AUTO'):
        if enable_logging:
            logging.info("ThinkingSDK disabled by THINKINGSDK_DISABLE_AUTO environment variable")
        return
    
    if _sender is not None:
        raise RuntimeError("ThinkingSDK is already started. Call stop() first.")
    
    # Load configuration from YAML file
    config_loader = ConfigLoader(config_file)
    
    # Check if SDK is enabled
    if not config_loader.is_enabled():
        if enable_logging:
            logging.debug("ThinkingSDK is disabled in configuration")
        return
    
    # Build final configuration (priority: args > config dict > yaml file)
    final_config = config_loader.config.copy()
    if config:
        # Merge user-provided config
        for key, value in config.items():
            if isinstance(value, dict) and key in final_config:
                final_config[key].update(value)
            else:
                final_config[key] = value
    
    # Override with function arguments if provided
    if api_key is None:
        api_key = config_loader.get_api_key()
    if server_url is None:
        server_url = config_loader.get("server_url", "https://api.thinkingsdk.ai")
    if enable_logging is None:
        enable_logging = config_loader.get("debug", False)
        
    # Initialize configuration
    _config = Config(final_config)
    
    # Set up logging if requested
    if enable_logging or _config.is_logging_enabled():
        logging.basicConfig(
            level=getattr(logging, _config.get_log_level().upper()),
            format='%(asctime)s - ThinkingSDK - %(levelname)s - %(message)s'
        )

    #TODO: is _queue or enhanced_queue both needed? which one should be used?
    try:
        # Create components
        _queue = EventQueue(**_config.get_queue_config())
        
        # Create PII scrubber if privacy is enabled
        global _pii_scrubber
        privacy_config = final_config.get('privacy', {})
        if privacy_config.get('sanitize_data', True):
            _pii_scrubber = PIIScrubber(privacy_config)
        
        # Create deduplicator for efficiency
        global _deduplicator
        _deduplicator = EventDeduplicator(final_config.get('deduplication', {}))
        
        # Create breadcrumb tracker
        global _breadcrumb_tracker
        _breadcrumb_tracker = BreadcrumbTracker(max_breadcrumbs=100)

        # Setup semantic event integrations for breadcrumbs
        global _integrations
        _integrations = []

        # Add standard library integration (HTTP, subprocess)
        from .integrations.stdlib import StdlibIntegration
        stdlib_integration = StdlibIntegration()
        stdlib_integration.setup_once()
        _integrations.append(stdlib_integration)

        # Add logging integration
        from .integrations.logging import LoggingIntegration
        logging_integration = LoggingIntegration(level=logging.DEBUG)
        logging_integration.setup_once()
        _integrations.append(logging_integration)

        # Add console integration (print statements)
        from .integrations.console import ConsoleIntegration
        console_integration = ConsoleIntegration(capture_print=True)
        console_integration.setup_once()
        _integrations.append(console_integration)

        # Try to add database integrations if available
        try:
            import sqlalchemy
            from .integrations.sqlalchemy import SQLAlchemyIntegration
            sqlalchemy_integration = SQLAlchemyIntegration(capture_params=False)
            sqlalchemy_integration.setup_once()
            _integrations.append(sqlalchemy_integration)
        except ImportError:
            pass  # SQLAlchemy not installed

        try:
            import psycopg2
            from .integrations.psycopg2 import Psycopg2Integration
            psycopg2_integration = Psycopg2Integration(capture_params=False)
            psycopg2_integration.setup_once()
            _integrations.append(psycopg2_integration)
        except ImportError:
            pass  # psycopg2 not installed

        try:
            import pymongo
            from .integrations.pymongo import PyMongoIntegration
            pymongo_integration = PyMongoIntegration(sanitize_queries=True)
            pymongo_integration.setup_once()
            _integrations.append(pymongo_integration)
        except ImportError:
            pass  # pymongo not installed

        try:
            import redis
            from .integrations.redis_integration import RedisIntegration
            redis_integration = RedisIntegration(max_data_size=100)
            redis_integration.setup_once()
            _integrations.append(redis_integration)
        except ImportError:
            pass  # redis not installed

        # Create custom event tracker
        global _custom_event_tracker
        _custom_event_tracker = CustomEventTracker(_queue, _breadcrumb_tracker)
        
        # Create enhanced queue that uses deduplicator and PII scrubber
        enhanced_queue = EnhancedEventQueue(_queue, _deduplicator, _pii_scrubber)
        
        _instrumentation = RuntimeInstrumentation(enhanced_queue, _config.get_instrumentation_config())
        _sender = BackgroundSender(enhanced_queue, api_key, server_url, _config.get_sender_config())
        
        # Start instrumentation and background sender
        _instrumentation.setup_hooks()
        _sender.start()
        
        # Register automatic cleanup on Python exit
        atexit.register(_cleanup_on_exit)
        
        if enable_logging or _config.is_logging_enabled():
            logging.debug("ThinkingSDK started successfully")
            
    except Exception as e:
        # Clean up on failure
        stop()
        raise RuntimeError(f"Failed to start ThinkingSDK: {e}") from e


def _cleanup_on_exit() -> None:
    """
    Automatic cleanup function called on Python exit.
    Ensures events are flushed before the program terminates.
    """
    try:
        # Silently cleanup - no output to maintain transparency
        # Only cleanup if SDK is still running
        if _sender is not None and _instrumentation is not None:
            if _config and (_config.is_logging_enabled()):
                logging.debug("ThinkingSDK: Automatic cleanup on exit - flushing events...")
            stop(timeout=3.0)  # Shorter timeout for exit handler
            if _config and (_config.is_logging_enabled()):
                logging.debug("ThinkingSDK: Exit cleanup completed")
    except Exception as e:
        # Don't let exit handler exceptions crash the program
        if _config and (_config.is_logging_enabled()):
            logging.debug(f"ThinkingSDK: Exit cleanup failed: {e}")


def stop(timeout: float = 5.0) -> None:
    """
    Stop ThinkingSDK instrumentation and background sending.
    TODO: empty the queue gracefully before stopping
    Args:
        timeout: Maximum time to wait for graceful shutdown (seconds)
    """
    global _instrumentation, _sender, _queue, _config
    
    # Unregister exit handler to prevent duplicate cleanup
    try:
        atexit.unregister(_cleanup_on_exit)
    except ValueError:
        pass  # Already unregistered
    
    if _config and (_config.is_logging_enabled()):
        logging.debug("Stopping ThinkingSDK...")
    
    # Clean up instrumentation
    if _instrumentation:
        try:
            _instrumentation.cleanup_hooks()
        except Exception as e:
            if _config and _config.is_logging_enabled():
                logging.error(f"Error cleaning up instrumentation: {e}")
        finally:
            _instrumentation = None
            
    # Stop background sender
    if _sender:
        try:
            _sender.stop(timeout=timeout)
        except Exception as e:
            if _config and _config.is_logging_enabled():
                logging.error(f"Error stopping sender: {e}")
        finally:
            _sender = None
            
    # Clear remaining state
    _queue = None
    _config = None
    
    if _config and _config.is_logging_enabled():
        logging.debug("ThinkingSDK stopped")


def get_stats() -> Dict[str, Any]:
    """
    Get statistics about the current ThinkingSDK session.
    
    Returns:
        Dictionary containing statistics from all components
        
    Raises:
        RuntimeError: If SDK is not started
    """
    if not _sender:
        raise RuntimeError("ThinkingSDK is not started. Call start() first.")
        
    stats = {
        'sdk_active': True,
        'config': _config.to_dict() if _config else {},
    }
    
    # Add component statistics
    if _queue:
        stats['queue'] = _queue.get_stats()
        
    if _instrumentation:
        stats['instrumentation'] = _instrumentation.get_stats()
        
    if _sender:
        stats['sender'] = _sender.get_stats()
        
    return stats


def is_active() -> bool:
    """
    Check if ThinkingSDK is currently active.
    
    Returns:
        True if SDK is started and running
    """
    return _sender is not None and _instrumentation is not None


def track_event(event_name: str, data: Optional[Dict[str, Any]] = None, level: str = "info") -> None:
    """
    Track a custom business event.
    
    Args:
        event_name: Name of the event (e.g., "payment_processed")
        data: Event data/metadata
        level: Event level (debug, info, warning, error, critical)
        
    Raises:
        RuntimeError: If SDK is not started
    """
    if not _custom_event_tracker:
        raise RuntimeError("ThinkingSDK is not started. Call start() first.")
    
    _custom_event_tracker.track_event(event_name, data, level)


def track_metric(metric_name: str, value: float, unit: str = "none", tags: Optional[Dict[str, str]] = None) -> None:
    """
    Track a numeric metric.
    
    Args:
        metric_name: Name of the metric
        value: Numeric value
        unit: Unit of measurement
        tags: Additional tags
        
    Raises:
        RuntimeError: If SDK is not started
    """
    if not _custom_event_tracker:
        raise RuntimeError("ThinkingSDK is not started. Call start() first.")
    
    _custom_event_tracker.track_metric(metric_name, value, unit, tags)


def add_breadcrumb(message: str, category: str = "default", level: str = "info", data: Optional[Dict[str, Any]] = None) -> None:
    """
    Add a breadcrumb to the trail.
    
    Args:
        message: Breadcrumb message
        category: Category (navigation, http, console, user, etc.)
        level: Severity level
        data: Additional data
        
    Raises:
        RuntimeError: If SDK is not started
    """
    if not _custom_event_tracker:
        raise RuntimeError("ThinkingSDK is not started. Call start() first.")
    
    _custom_event_tracker.add_breadcrumb(message, category, level, data)


def mark_feature_usage(feature_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Track feature usage for product analytics.
    
    Args:
        feature_name: Name of the feature
        metadata: Additional metadata
        
    Raises:
        RuntimeError: If SDK is not started
    """
    if not _custom_event_tracker:
        raise RuntimeError("ThinkingSDK is not started. Call start() first.")
    
    _custom_event_tracker.mark_feature_usage(feature_name, metadata)


def timer(operation_name: str, tags: Optional[Dict[str, str]] = None):
    """
    Create a timer context manager for timing operations.
    
    Args:
        operation_name: Name of the operation to time
        tags: Additional tags
        
    Returns:
        Timer context manager
        
    Example:
        with thinking.timer("database_query"):
            results = db.query("SELECT * FROM users")
    """
    if not _custom_event_tracker:
        raise RuntimeError("ThinkingSDK is not started. Call start() first.")
    
    return Timer(_custom_event_tracker, operation_name, tags)


# Expose key classes for advanced usage
__all__ = [
    '__version__', '__version_info__',
    'start', 'stop', 'get_stats', 'is_active',
    'context', 'set_context', 'clear_context', 'add_context',
    'track_event', 'track_metric', 'add_breadcrumb', 'mark_feature_usage', 'timer',
    'RuntimeInstrumentation', 'BackgroundSender', 'EventQueue', 'Config'
]
