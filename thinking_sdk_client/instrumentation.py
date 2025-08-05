# thinking_sdk_client/instrumentation.py
import sys
import threading
import traceback
import time
import os
import re
from typing import Any, Dict, Optional, Set, Callable
from pathlib import Path


class RuntimeInstrumentation:
    """Production-grade runtime instrumentation with filtering and safety features.
    
    Captures function calls, returns, and exceptions while minimizing performance
    impact through intelligent filtering and safe data serialization.
    """
    
    # Default patterns for files/functions to ignore
    DEFAULT_IGNORE_PATTERNS = {
        # Standard library paths
        re.compile(r'/python\d+\.\d+/'),
        re.compile(r'/site-packages/'),
        re.compile(r'/dist-packages/'),
        # ThinkingSDK internal paths
        re.compile(r'/thinking_sdk_client/'),
        # Common framework internals
        re.compile(r'/(flask|django|fastapi|requests|urllib)/'),
    }
    
    DEFAULT_IGNORE_FUNCTIONS = {
        '<module>', '__init__', '__enter__', '__exit__',
        '__getattr__', '__setattr__', '__getitem__', '__setitem__'
    }
    
    def __init__(self, queue, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            queue: EventQueue instance for buffering events
            config: Configuration dictionary with optional settings:
                - max_locals: Max number of local variables to capture (default: 5)
                - max_local_length: Max string length for local values (default: 120)
                - capture_returns: Whether to capture function returns (default: False)
                - ignore_patterns: Additional regex patterns to ignore
                - ignore_functions: Additional function names to ignore
                - sample_rate: Fraction of events to capture (default: 1.0)
        """
        self.queue = queue
        self._config = config or {}
        
        # Configuration settings
        self.max_locals = self._config.get('max_locals', 5)
        self.max_local_length = self._config.get('max_local_length', 120)
        self.capture_returns = self._config.get('capture_returns', False)
        self.sample_rate = self._config.get('sample_rate', 1.0)
        
        # Build ignore patterns
        self.ignore_patterns = set(self.DEFAULT_IGNORE_PATTERNS)
        if 'ignore_patterns' in self._config:
            self.ignore_patterns.update(
                re.compile(p) for p in self._config['ignore_patterns']
            )
            
        # Build ignore functions
        self.ignore_functions = set(self.DEFAULT_IGNORE_FUNCTIONS)
        if 'ignore_functions' in self._config:
            self.ignore_functions.update(self._config['ignore_functions'])
            
        # State tracking
        self._original_trace = None
        self._original_excepthook = None
        self._active = False
        self._event_count = 0
        
    def setup_hooks(self) -> None:
        """Set up instrumentation hooks safely."""
        if self._active:
            return
            
        try:
            # Store original hooks for cleanup
            self._original_trace = sys.gettrace()
            self._original_excepthook = threading.excepthook
            
            # Install new hooks
            sys.settrace(self._trace_calls)
            threading.excepthook = self._thread_exception_handler
            
            self._active = True
        except Exception as e:
            # Fail silently to avoid breaking user code
            pass
            
    def cleanup_hooks(self) -> None:
        """Clean up instrumentation hooks."""
        if not self._active:
            return
            
        try:
            # Restore original hooks
            sys.settrace(self._original_trace)
            threading.excepthook = self._original_excepthook
            
            self._active = False
        except Exception:
            pass
            
    def _should_ignore_frame(self, frame) -> bool:
        """Check if a frame should be ignored based on filtering rules."""
        filename = frame.f_code.co_filename
        funcname = frame.f_code.co_name
        
        # Check function name filters
        if funcname in self.ignore_functions:
            return True
            
        # Check file path filters
        for pattern in self.ignore_patterns:
            if pattern.search(filename):
                return True
                
        return False
        
    def _should_sample(self) -> bool:
        """Determine if this event should be sampled."""
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
            
        self._event_count += 1
        return (self._event_count * self.sample_rate) % 1.0 >= 0.5
        
    def _safe_repr(self, value: Any, max_length: int = None) -> str:
        """Safely convert a value to string representation."""
        max_length = max_length or self.max_local_length
        
        try:
            # Handle common problematic types
            if hasattr(value, '__dict__') and len(value.__dict__) > 10:
                return f"<{type(value).__name__} object>"
            
            repr_str = repr(value)
            
            # Truncate if too long
            if len(repr_str) > max_length:
                return repr_str[:max_length-3] + '...'
                
            return repr_str
            
        except Exception:
            return f"<{type(value).__name__} (repr failed)>"
            
    def _capture_locals(self, frame) -> Dict[str, str]:
        """Safely capture local variables from a frame."""
        try:
            locals_dict = {}
            items = list(frame.f_locals.items())[:self.max_locals]
            
            for key, value in items:
                # Skip private/internal variables
                if key.startswith('_'):
                    continue
                    
                locals_dict[key] = self._safe_repr(value)
                
            return locals_dict
            
        except Exception:
            return {}
            
    def _trace_calls(self, frame, event: str, arg: Any) -> Optional[Callable]:
        """Main trace callback for sys.settrace."""
        try:
            # Quick filters
            if not self._active:
                return None
                
            if event not in ("call", "return", "exception"):
                return self._trace_calls
                
            if not self.capture_returns and event == "return":
                return self._trace_calls
                
            if self._should_ignore_frame(frame):
                return self._trace_calls
                
            if not self._should_sample():
                return self._trace_calls
                
            # Build event info
            event_info = {
                "ts": time.time(),
                "pid": os.getpid(),
                "thread": threading.current_thread().name,
                "event": event,
                "func": frame.f_code.co_name,
                "file": str(Path(frame.f_code.co_filename).name),  # Just filename
                "line": frame.f_lineno,
            }
            
            # Add event-specific data
            if event == "exception":
                exc_type, exc_val, exc_tb = arg
                event_info["exception"] = {
                    "type": exc_type.__name__,
                    "msg": self._safe_repr(exc_val, 500),
                    "traceback": traceback.format_exception(
                        exc_type, exc_val, exc_tb
                    )[-5:]  # Last 5 frames only
                }
            elif event == "call":
                event_info["locals"] = self._capture_locals(frame)
            elif event == "return" and arg is not None:
                event_info["return_value"] = self._safe_repr(arg)
                
            # Queue the event
            self.queue.push(event_info)
            
        except Exception:
            # Never let instrumentation break user code
            pass
            
        return self._trace_calls
        
    def _thread_exception_handler(self, args) -> None:
        """Handle exceptions in threads."""
        try:
            if not self._active:
                return
                
            exc_info = {
                "ts": time.time(),
                "pid": os.getpid(),
                "thread": getattr(args.thread, 'name', 'unknown'),
                "event": "thread_exception",
                "exception": {
                    "type": args.exc_type.__name__,
                    "msg": self._safe_repr(args.exc_value, 500),
                    "traceback": traceback.format_exception(
                        args.exc_type, args.exc_value, args.exc_traceback
                    )[-5:]  # Last 5 frames only
                },
            }
            
            self.queue.push(exc_info)
            
        except Exception:
            pass
            
        # Call original handler if it exists
        if self._original_excepthook:
            try:
                self._original_excepthook(args)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get instrumentation statistics."""
        return {
            "active": self._active,
            "event_count": self._event_count,
            "sample_rate": self.sample_rate,
            "config": self._config.copy()
        }