# thinking_sdk_client/context.py
"""
Context propagation for request IDs, user IDs, and custom metadata.

Usage:
    with thinking.context(user_id="123", request_id="abc-def"):
        process_request()  # All events include this context
        
    # Or set globally
    thinking.set_context({"environment": "production", "version": "1.2.3"})
"""

import contextvars
import threading
import uuid
from typing import Dict, Any, Optional, ContextManager
from contextlib import contextmanager

# Context variables for async-safe context propagation
_request_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'thinking_request_context',
    default={}
)

# Thread-local storage for non-async code
_thread_local = threading.local()

# Global context (shared across all threads/coroutines)
_global_context: Dict[str, Any] = {}
_global_context_lock = threading.Lock()


class Context:
    """Manages context propagation for ThinkingSDK events."""
    
    @staticmethod
    def set_global(key: str, value: Any) -> None:
        """Set a global context value (applies to all events)."""
        with _global_context_lock:
            _global_context[key] = value
    
    @staticmethod
    def update_global(context: Dict[str, Any]) -> None:
        """Update global context with multiple values."""
        with _global_context_lock:
            _global_context.update(context)
    
    @staticmethod
    def clear_global() -> None:
        """Clear all global context."""
        with _global_context_lock:
            _global_context.clear()
    
    @staticmethod
    def get_current() -> Dict[str, Any]:
        """Get the current combined context (global + local)."""
        # Start with global context
        with _global_context_lock:
            combined = _global_context.copy()
        
        # Add thread-local context (for sync code)
        if hasattr(_thread_local, 'context'):
            combined.update(_thread_local.context)
        
        # Add async context (for async code)
        try:
            async_context = _request_context.get()
            combined.update(async_context)
        except LookupError:
            pass
        
        return combined
    
    @staticmethod
    @contextmanager
    def local(**kwargs) -> ContextManager[Dict[str, Any]]:
        """
        Create a local context scope.
        
        Example:
            with Context.local(user_id="123", request_id="abc"):
                # These values are included in all events within this scope
                process_request()
        """
        # Generate request_id if not provided
        if 'request_id' not in kwargs and 'trace_id' not in kwargs:
            kwargs['request_id'] = str(uuid.uuid4())
        
        # Check if we're in async context
        try:
            # Try async context first
            token = _request_context.set(kwargs)
            try:
                yield kwargs
            finally:
                _request_context.reset(token)
        except Exception:
            # Fall back to thread-local for sync code
            old_context = getattr(_thread_local, 'context', {}).copy()
            if not hasattr(_thread_local, 'context'):
                _thread_local.context = {}
            
            _thread_local.context.update(kwargs)
            try:
                yield kwargs
            finally:
                _thread_local.context = old_context
    
    @staticmethod
    def add_to_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Add current context to an event."""
        context = Context.get_current()
        if context:
            event['context'] = context
        return event


# Convenience functions for module-level API
def set_context(context: Dict[str, Any]) -> None:
    """Set global context values."""
    Context.update_global(context)


def clear_context() -> None:
    """Clear global context."""
    Context.clear_global()


class AsyncContextManager:
    """Context manager that works with both sync and async code."""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.context_value = None
        self.token = None
        self.old_context = None
        
    def __enter__(self):
        """Sync context manager entry."""
        if 'request_id' not in self.kwargs and 'trace_id' not in self.kwargs:
            self.kwargs['request_id'] = str(uuid.uuid4())
        
        # Try async context first
        try:
            self.token = _request_context.set(self.kwargs)
        except Exception:
            # Fall back to thread-local for sync code
            self.old_context = getattr(_thread_local, 'context', {}).copy()
            if not hasattr(_thread_local, 'context'):
                _thread_local.context = {}
            _thread_local.context.update(self.kwargs)
        
        return self.kwargs
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        if self.token:
            try:
                _request_context.reset(self.token)
            except:
                pass
        elif self.old_context is not None:
            _thread_local.context = self.old_context
    
    async def __aenter__(self):
        """Async context manager entry."""
        if 'request_id' not in self.kwargs and 'trace_id' not in self.kwargs:
            self.kwargs['request_id'] = str(uuid.uuid4())
        
        self.token = _request_context.set(self.kwargs)
        return self.kwargs
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.token:
            _request_context.reset(self.token)


def context(**kwargs):
    """
    Create a context scope for tracking IDs and metadata.
    Works with both sync and async code.
    
    Sync example:
        with context(user_id="123"):
            process_request()
    
    Async example:
        async with context(user_id="123"):
            await async_process()
    """
    return AsyncContextManager(**kwargs)


def add_context(key: str, value: Any) -> None:
    """Add a single context value globally."""
    Context.set_global(key, value)


# Decorators for function-level context
def with_context(**context_kwargs):
    """
    Decorator to add context to all events within a function.
    
    Example:
        @with_context(operation="payment_processing")
        def process_payment(user_id, amount):
            # All events will include operation="payment_processing"
            pass
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            # Async function
            async def wrapper(*args, **kwargs):
                with context(**context_kwargs):
                    return await func(*args, **kwargs)
        else:
            # Sync function
            def wrapper(*args, **kwargs):
                with context(**context_kwargs):
                    return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


# Integration with instrumentation
def inject_context(event: Dict[str, Any]) -> None:
    """Inject current context into an event (called by instrumentation)."""
    context_data = Context.get_current()
    if context_data:
        event['context'] = context_data


# Auto-generate trace IDs for distributed tracing
def generate_trace_id() -> str:
    """Generate a unique trace ID for distributed tracing."""
    return str(uuid.uuid4())


def get_or_create_trace_id() -> str:
    """Get existing trace ID from context or create a new one."""
    current = Context.get_current()
    return current.get('trace_id') or current.get('request_id') or generate_trace_id()


# HTTP header integration for distributed tracing
TRACE_HEADER_NAME = 'X-ThinkingSDK-Trace-ID'
USER_HEADER_NAME = 'X-ThinkingSDK-User-ID'


def extract_from_headers(headers: Dict[str, str]) -> Dict[str, Any]:
    """Extract context from HTTP headers."""
    context = {}
    
    if TRACE_HEADER_NAME in headers:
        context['trace_id'] = headers[TRACE_HEADER_NAME]
    
    if USER_HEADER_NAME in headers:
        context['user_id'] = headers[USER_HEADER_NAME]
    
    return context


def inject_to_headers(headers: Dict[str, str]) -> None:
    """Inject context into HTTP headers for propagation."""
    current = Context.get_current()
    
    if 'trace_id' in current:
        headers[TRACE_HEADER_NAME] = current['trace_id']
    elif 'request_id' in current:
        headers[TRACE_HEADER_NAME] = current['request_id']
    
    if 'user_id' in current:
        headers[USER_HEADER_NAME] = str(current['user_id'])


import asyncio
import sys