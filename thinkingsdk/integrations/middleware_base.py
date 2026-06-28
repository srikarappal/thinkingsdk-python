"""
Base middleware wrapper for framework integrations.

Provides consistent middleware wrapping similar to Sentry's approach.
"""

import sys
import contextvars
from typing import Any, Callable, Optional, Dict
from functools import wraps


# Context variables for proper async isolation
current_request_context = contextvars.ContextVar('tsdk_request_context', default=None)
current_exception_context = contextvars.ContextVar('tsdk_exception_context', default=None)


class MiddlewareWrapper:
    """Base class for wrapping framework middleware."""
    
    def __init__(self, original_middleware):
        self.original_middleware = original_middleware
        
    def __call__(self, *args, **kwargs):
        """Wrap middleware call to capture exceptions."""
        try:
            return self.original_middleware(*args, **kwargs)
        except Exception as e:
            # Store exception context
            self._capture_exception_context(e, args, kwargs)
            raise
    
    def _capture_exception_context(self, exception, args, kwargs):
        """Store exception context for later retrieval."""
        try:
            context = {
                'exception': exception,
                'middleware': self.original_middleware.__class__.__name__,
                'args': self._sanitize_args(args),
                'kwargs': self._sanitize_kwargs(kwargs),
            }
            current_exception_context.set(context)
        except Exception:
            pass
    
    def _sanitize_args(self, args):
        """Sanitize middleware arguments."""
        # Basic sanitization - override in subclasses
        return str(args)[:100]
    
    def _sanitize_kwargs(self, kwargs):
        """Sanitize middleware keyword arguments."""
        # Basic sanitization - override in subclasses
        safe_kwargs = {}
        for k, v in kwargs.items():
            if k not in ['password', 'secret', 'token']:
                safe_kwargs[k] = str(v)[:100]
        return safe_kwargs


class AsyncMiddlewareWrapper(MiddlewareWrapper):
    """Wrapper for async middleware."""
    
    async def __call__(self, *args, **kwargs):
        """Wrap async middleware call."""
        try:
            return await self.original_middleware(*args, **kwargs)
        except Exception as e:
            self._capture_exception_context(e, args, kwargs)
            raise


def wrap_middleware(middleware):
    """Wrap middleware with exception tracking."""
    import asyncio
    
    # Check if middleware is async
    if asyncio.iscoroutinefunction(middleware):
        return AsyncMiddlewareWrapper(middleware)
    else:
        return MiddlewareWrapper(middleware)


def get_request_context():
    """Get current request context from contextvars."""
    return current_request_context.get()


def set_request_context(context: Dict[str, Any]):
    """Set request context in contextvars."""
    current_request_context.set(context)


def get_exception_context():
    """Get current exception context from contextvars."""
    return current_exception_context.get()


def clear_context():
    """Clear all context variables."""
    current_request_context.set(None)
    current_exception_context.set(None)