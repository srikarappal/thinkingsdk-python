# thinking_sdk_client/__init__.py
"""
Production-grade ThinkingSDK client. Usage inside user code:

    import thinking_sdk_client as thinking
    
    # Basic usage
    thinking.start(api_key="sk_live_XXXX", server_url="http://localhost:8000")
    
    # Advanced usage with configuration
    config = {
        'instrumentation': {'sample_rate': 0.5, 'capture_returns': True},
        'sender': {'batch_size': 100, 'retry_attempts': 5},
        'queue': {'maxsize': 20000}
    }
    thinking.start(api_key="sk_live_XXXX", server_url="http://localhost:8000", config=config)

    # Get statistics
    stats = thinking.get_stats()

    # Clean shutdown
    thinking.stop()
"""

import logging
from typing import Dict, Any, Optional

from .instrumentation import RuntimeInstrumentation
from .background_sender import BackgroundSender
from .event_queue import EventQueue
from .config import Config

# Module-level state
_instrumentation: Optional[RuntimeInstrumentation] = None
_sender: Optional[BackgroundSender] = None
_queue: Optional[EventQueue] = None
_config: Optional[Config] = None


def start(
    api_key: str, 
    server_url: str, 
    config: Optional[Dict[str, Any]] = None,
    enable_logging: bool = False
) -> None:
    """
    Start ThinkingSDK instrumentation and background sending.
    
    Args:
        api_key: API key for authentication with ThinkingSDK server
        server_url: Base URL of the ThinkingSDK server
        config: Optional configuration dictionary to override defaults
        enable_logging: Enable logging for debugging (default: False)
    
    Raises:
        RuntimeError: If SDK is already started
    """
    global _instrumentation, _sender, _queue, _config
    
    if _sender is not None:
        raise RuntimeError("ThinkingSDK is already started. Call stop() first.")
        
    # Initialize configuration
    _config = Config(config)
    
    # Set up logging if requested
    if enable_logging or _config.is_logging_enabled():
        logging.basicConfig(
            level=getattr(logging, _config.get_log_level().upper()),
            format='%(asctime)s - ThinkingSDK - %(levelname)s - %(message)s'
        )
        
    try:
        # Create components
        _queue = EventQueue(**_config.get_queue_config())
        _instrumentation = RuntimeInstrumentation(_queue, _config.get_instrumentation_config())
        _sender = BackgroundSender(_queue, api_key, server_url, _config.get_sender_config())
        
        # Start instrumentation and background sender
        _instrumentation.setup_hooks()
        _sender.start()
        
        if enable_logging or _config.is_logging_enabled():
            logging.info("ThinkingSDK started successfully")
            
    except Exception as e:
        # Clean up on failure
        stop()
        raise RuntimeError(f"Failed to start ThinkingSDK: {e}") from e


def stop(timeout: float = 5.0) -> None:
    """
    Stop ThinkingSDK instrumentation and background sending.
    
    Args:
        timeout: Maximum time to wait for graceful shutdown (seconds)
    """
    global _instrumentation, _sender, _queue, _config
    
    if _config and (_config.is_logging_enabled()):
        logging.info("Stopping ThinkingSDK...")
    
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
        logging.info("ThinkingSDK stopped")


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


# Expose key classes for advanced usage
__all__ = [
    'start', 'stop', 'get_stats', 'is_active',
    'RuntimeInstrumentation', 'BackgroundSender', 'EventQueue', 'Config'
]
