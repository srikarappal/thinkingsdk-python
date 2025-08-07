# thinking_sdk_client/async_instrumentation.py
"""
Async/await instrumentation support for ThinkingSDK.

Handles:
- Coroutine execution tracking
- Task lifecycle monitoring
- Async context propagation
- Event loop performance
"""

import sys
import asyncio
import time
import traceback
from typing import Any, Optional, Dict, Coroutine
from functools import wraps
import weakref

from .context import Context


class AsyncInstrumentation:
    """Instrumentation for async/await code."""
    
    def __init__(self, queue, config: Optional[Dict[str, Any]] = None):
        self.queue = queue
        self.config = config or {}
        self.active_tasks: weakref.WeakSet = weakref.WeakSet()
        self._original_create_task = None
        self._original_run_coroutine = None
        self._patched = False
        
    def setup_hooks(self) -> None:
        """Install async instrumentation hooks."""
        if self._patched:
            return
            
        try:
            # Patch asyncio.create_task
            self._original_create_task = asyncio.create_task
            asyncio.create_task = self._wrapped_create_task
            
            # Patch event loop task factory
            self._patch_event_loops()
            
            self._patched = True
            
        except Exception as e:
            # Don't break user code
            pass
    
    def cleanup_hooks(self) -> None:
        """Remove async instrumentation hooks."""
        if not self._patched:
            return
            
        try:
            if self._original_create_task:
                asyncio.create_task = self._original_create_task
                
            self._patched = False
            
        except Exception:
            pass
    
    def _patch_event_loops(self) -> None:
        """Patch existing and future event loops."""
        # Patch current event loop if exists
        try:
            loop = asyncio.get_running_loop()
            self._patch_loop(loop)
        except RuntimeError:
            pass
        
        # Patch new_event_loop to catch future loops
        original_new_loop = asyncio.new_event_loop
        
        def wrapped_new_loop():
            loop = original_new_loop()
            self._patch_loop(loop)
            return loop
        
        asyncio.new_event_loop = wrapped_new_loop
    
    def _patch_loop(self, loop) -> None:
        """Patch a specific event loop."""
        original_factory = loop.get_task_factory()
        
        def task_factory(loop, coro):
            # Create task with original factory or default
            if original_factory:
                task = original_factory(loop, coro)
            else:
                task = asyncio.Task(coro, loop=loop)
            
            # Track the task
            self._track_task(task)
            return task
        
        loop.set_task_factory(task_factory)
    
    def _wrapped_create_task(self, coro, *, name=None):
        """Wrapped version of asyncio.create_task."""
        task = self._original_create_task(coro, name=name)
        self._track_task(task)
        return task
    
    def _track_task(self, task: asyncio.Task) -> None:
        """Track an async task."""
        self.active_tasks.add(task)
        
        # Capture creation context
        creation_context = Context.get_current()
        task_id = id(task)
        
        # Send task creation event
        event = {
            "ts": time.time(),
            "event": "async_task_created",
            "task_id": task_id,
            "task_name": task.get_name() if hasattr(task, 'get_name') else str(task),
            "context": creation_context,
        }
        
        # Add coroutine info
        coro = task.get_coro() if hasattr(task, 'get_coro') else None
        if coro:
            event["coroutine"] = {
                "name": coro.__name__ if hasattr(coro, '__name__') else str(coro),
                "file": coro.gi_code.co_filename if hasattr(coro, 'gi_code') else None,
                "line": coro.gi_code.co_firstlineno if hasattr(coro, 'gi_code') else None,
            }
        
        self.queue.push(event)
        
        # Add callback to track completion
        task.add_done_callback(lambda t: self._task_done(t, task_id, creation_context))
    
    def _task_done(self, task: asyncio.Task, task_id: int, creation_context: Dict[str, Any]) -> None:
        """Handle task completion."""
        end_time = time.time()
        
        event = {
            "ts": end_time,
            "event": "async_task_done",
            "task_id": task_id,
            "task_name": task.get_name() if hasattr(task, 'get_name') else str(task),
            "context": creation_context,
        }
        
        # Check if task failed
        exception = None
        try:
            exception = task.exception()
        except asyncio.CancelledError:
            event["cancelled"] = True
        except Exception as e:
            exception = e
        
        if exception:
            event["exception"] = {
                "type": type(exception).__name__,
                "msg": str(exception),
                "traceback": traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )[-5:]  # Last 5 frames
            }
        
        self.queue.push(event)
        
        # Remove from active tasks
        self.active_tasks.discard(task)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get async instrumentation statistics."""
        return {
            "active_tasks": len(self.active_tasks),
            "patched": self._patched,
        }


def async_track(func):
    """
    Decorator to track async function execution.
    
    Example:
        @async_track
        async def fetch_data(url):
            async with aiohttp.ClientSession() as session:
                return await session.get(url)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        context_data = Context.get_current()
        
        # Create event for function start
        start_event = {
            "ts": time.time(),
            "event": "async_function_start",
            "func": func.__name__,
            "module": func.__module__,
            "context": context_data,
        }
        
        # Get queue from global state (injected by main instrumentation)
        from . import _queue
        if _queue:
            _queue.push(start_event)
        
        try:
            result = await func(*args, **kwargs)
            
            # Success event
            end_event = {
                "ts": time.time(),
                "event": "async_function_complete",
                "func": func.__name__,
                "duration_ms": (time.perf_counter() - start_time) * 1000,
                "context": context_data,
            }
            
            if _queue:
                _queue.push(end_event)
            
            return result
            
        except Exception as e:
            # Error event
            error_event = {
                "ts": time.time(),
                "event": "async_function_error",
                "func": func.__name__,
                "duration_ms": (time.perf_counter() - start_time) * 1000,
                "exception": {
                    "type": type(e).__name__,
                    "msg": str(e),
                },
                "context": context_data,
            }
            
            if _queue:
                _queue.push(error_event)
            
            raise
    
    return wrapper


class AsyncContextManager:
    """Track async context managers (async with statements)."""
    
    def __init__(self, original_cm, name: str = None):
        self.original_cm = original_cm
        self.name = name or str(original_cm)
        self.enter_time = None
        
    async def __aenter__(self):
        self.enter_time = time.perf_counter()
        
        # Track enter
        from . import _queue
        if _queue:
            _queue.push({
                "ts": time.time(),
                "event": "async_context_enter",
                "name": self.name,
                "context": Context.get_current(),
            })
        
        return await self.original_cm.__aenter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (time.perf_counter() - self.enter_time) * 1000 if self.enter_time else 0
        
        # Track exit
        from . import _queue
        if _queue:
            event = {
                "ts": time.time(),
                "event": "async_context_exit",
                "name": self.name,
                "duration_ms": duration,
                "context": Context.get_current(),
            }
            
            if exc_type:
                event["exception"] = {
                    "type": exc_type.__name__,
                    "msg": str(exc_val),
                }
            
            _queue.push(event)
        
        return await self.original_cm.__aexit__(exc_type, exc_val, exc_tb)


def track_async_context(cm, name: str = None):
    """
    Track an async context manager.
    
    Example:
        async with track_async_context(aiohttp.ClientSession(), "http_session"):
            # Session usage is tracked
            pass
    """
    return AsyncContextManager(cm, name)


# Integration with aiohttp (if available)
def patch_aiohttp():
    """Patch aiohttp for automatic request tracking."""
    try:
        import aiohttp
        
        original_request = aiohttp.ClientSession._request
        
        async def tracked_request(self, method, url, **kwargs):
            # Propagate trace ID in headers
            from .context import inject_to_headers
            
            headers = kwargs.get('headers', {})
            inject_to_headers(headers)
            kwargs['headers'] = headers
            
            # Track the request
            start_time = time.perf_counter()
            
            try:
                response = await original_request(self, method, url, **kwargs)
                
                # Log successful request
                from . import _queue
                if _queue:
                    _queue.push({
                        "ts": time.time(),
                        "event": "http_request",
                        "method": method,
                        "url": str(url),
                        "status": response.status,
                        "duration_ms": (time.perf_counter() - start_time) * 1000,
                        "context": Context.get_current(),
                    })
                
                return response
                
            except Exception as e:
                # Log failed request
                from . import _queue
                if _queue:
                    _queue.push({
                        "ts": time.time(),
                        "event": "http_request_error",
                        "method": method,
                        "url": str(url),
                        "error": str(e),
                        "duration_ms": (time.perf_counter() - start_time) * 1000,
                        "context": Context.get_current(),
                    })
                raise
        
        aiohttp.ClientSession._request = tracked_request
        
    except ImportError:
        pass  # aiohttp not installed