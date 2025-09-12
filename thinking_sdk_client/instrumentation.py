# thinking_sdk_client/instrumentation.py
import sys
import threading
import traceback
import time
import os
import re
from typing import Any, Dict, Optional, Set, Callable
from pathlib import Path

try:
    from .strategic_sampling import StrategicSampler, RemoteConfigManager
except ImportError:
    # Fallback if strategic sampling not available
    StrategicSampler = None
    RemoteConfigManager = None


class RuntimeInstrumentation:
    """Production-grade runtime instrumentation with filtering and safety features.
    
    Captures function calls, returns, and exceptions while minimizing performance
    impact through intelligent filtering and safe data serialization.
    """
    
    # Default patterns for files/functions to ignore
    DEFAULT_IGNORE_PATTERNS = {
        # Only ignore ThinkingSDK internal paths to prevent recursion
        re.compile(r'/thinking_sdk_client/'),
    }
    
    DEFAULT_IGNORE_FUNCTIONS = {
        '__init__', '__enter__', '__exit__',
        '__getattr__', '__setattr__', '__getitem__', '__setitem__'
    }
    
    def __init__(self, queue, config: Optional[Dict[str, Any]] = None, api_client=None):
        """
        Args:
            queue: EventQueue instance for buffering events
            config: Configuration dictionary with optional settings:
                - max_locals: Max number of local variables to capture (default: 5)
                - max_local_length: Max string length for local values (default: 120)
                - capture_returns: Whether to capture function returns (default: False)
                - capture_performance: Whether to capture execution timing (default: True)
                - capture_memory: Whether to capture memory usage (default: False)
                - capture_call_patterns: Whether to detect call patterns (default: True)
                - capture_data_flow: Whether to track variable changes (default: False)
                - capture_source_lines: Whether to capture source code lines (default: False)
                - slow_function_threshold: Threshold in seconds for slow function detection (default: 0.1)
                - hot_path_threshold: Call count threshold for hot path detection (default: 50)
                - ignore_patterns: Additional regex patterns to ignore
                - ignore_functions: Additional function names to ignore
                - sample_rate: Fraction of events to capture (default: 1.0)
                - strategic_sampling: Strategic sampling configuration
            api_client: Optional API client for remote configuration updates
        """
        self.queue = queue
        self._config = config or {}
        self.api_client = api_client
        
        # Basic configuration settings
        self.max_locals = self._config.get('max_locals', 9)
        self.max_local_length = self._config.get('max_local_length', 120)
        self.capture_returns = self._config.get('capture_returns', False)
        self.sample_rate = self._config.get('sample_rate', 1.0)
        
        # Initialize strategic sampling
        strategic_config = self._config.get('strategic_sampling', {})
        self.strategic_sampling_enabled = strategic_config.get('enabled', True)
        
        if self.strategic_sampling_enabled and StrategicSampler:
            self.strategic_sampler = StrategicSampler(strategic_config)
            
            # Initialize remote config manager if enabled
            if strategic_config.get('remote_config_enabled') and RemoteConfigManager:
                self.remote_config_manager = RemoteConfigManager(
                    api_client=api_client,
                    poll_interval_seconds=strategic_config.get('remote_config_poll_interval', 300)
                )
            else:
                self.remote_config_manager = None
        else:
            self.strategic_sampler = None
            self.remote_config_manager = None
        
        # Enhanced tracking configuration
        self.capture_performance = self._config.get('capture_performance', True)
        self.capture_memory = self._config.get('capture_memory', False)
        self.capture_call_patterns = self._config.get('capture_call_patterns', True)
        self.capture_data_flow = self._config.get('capture_data_flow', False)
        self.capture_source_lines = self._config.get('capture_source_lines', False)
        self.slow_function_threshold = self._config.get('slow_function_threshold', 0.1)
        self.hot_path_threshold = self._config.get('hot_path_threshold', 50)
        
        # Runtime tracking state
        if self.capture_performance or self.capture_call_patterns:
            from collections import defaultdict
            self.function_call_counts = defaultdict(int)
            self.function_timings = defaultdict(list)
            self.call_stack = []
            
        if self.capture_memory:
            try:
                import psutil
                self.process = psutil.Process()
                self._last_memory = None
            except ImportError:
                self.capture_memory = False  # Disable if psutil not available
        
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
        self._original_sys_excepthook = None
        self._active = False
        self._event_count = 0
        
        # Exception deduplication - track exceptions captured by sys.settrace
        self._last_captured_exception = None
        
    def setup_hooks(self) -> None:
        """Set up instrumentation hooks safely."""
        if self._active:
            return
            
        try:
            # Store original hooks for cleanup
            self._original_trace = sys.gettrace()
            self._original_excepthook = threading.excepthook
            self._original_sys_excepthook = sys.excepthook
            
            # Install new hooks
            sys.settrace(self._trace_calls)
            threading.excepthook = self._thread_exception_handler
            sys.excepthook = self._main_thread_exception_handler
            
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
            sys.excepthook = self._original_sys_excepthook
            
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
    
    def _is_user_file(self, filename: str) -> bool:
        """Determine if a file is user code vs internal Python/library code."""
        return (
            not filename.startswith('<frozen') and
            not filename.startswith('<built-in>') and
            'site-packages' not in filename and
            'lib/python' not in filename and
            filename.endswith('.py') and
            # Exclude ThinkingSDK itself to prevent recursion
            '/thinking_sdk_client/' not in filename
        )
    
    def _is_user_relevant_exception(self, frame, exc_info) -> bool:
        """Check if user code is involved anywhere in the exception call stack."""
        exc_type, exc_value, exc_traceback = exc_info
        
        # Check if current executing frame is user code
        if self._is_user_file(frame.f_code.co_filename):
            return True
        
        # Walk through the exception traceback to see if any frame is user code
        current_tb = exc_traceback
        while current_tb:
            if self._is_user_file(current_tb.tb_frame.f_code.co_filename):
                return True
            current_tb = current_tb.tb_next
        
        # No user code found in the exception path
        return False
        
    def _should_sample(self) -> bool:
        """Determine if this event should be sampled (fallback method)."""
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
            
        self._event_count += 1
        return (self._event_count * self.sample_rate) % 1.0 >= 0.5
    
    def _should_capture_event(self, event_info: Dict[str, Any]) -> bool:
        """Determine if event should be captured using strategic sampling."""
        # Check for remote config updates first
        if self.remote_config_manager:
            remote_config = self.remote_config_manager.get_remote_config()
            if remote_config:
                self.strategic_sampler.update_config(remote_config)
        
        # Use strategic sampling if enabled
        if self.strategic_sampling_enabled and self.strategic_sampler:
            return self.strategic_sampler.should_capture_event(event_info)
        
        # Fallback to traditional sampling
        return self._should_sample()
        
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
            # Quick shutdown detection - Python is shutting down
            if not self._active or sys.meta_path is None:
                return None
                
            if event not in ("call", "return", "exception"):
                return self._trace_calls
                
            if not self.capture_returns and event == "return":
                return self._trace_calls
                
            if self._should_ignore_frame(frame):
                return self._trace_calls
                
            # Strategy X: Filter exceptions where user code is NOT involved anywhere in the exception path
            if event == "exception" and arg:
                exc_type, exc_value, exc_traceback = arg
                
                # Check if user code is involved anywhere in the exception call stack
                if not self._is_user_relevant_exception(frame, arg):
                    return self._trace_calls
                
                # Mark this exception as captured by sys.settrace to prevent duplicate from sys.excepthook
                self._last_captured_exception = (exc_type, str(exc_value), time.time())
                
                # Debug: Only show exceptions that pass the filter
                filename = frame.f_code.co_filename
                print(f"🚨 EXCEPTION DEBUG (FILTERED): {exc_type.__name__} in {filename} at {frame.f_code.co_name}:{frame.f_lineno}")
                
            # Build base event info for strategic sampling decision
            event_info = {
                "ts": time.time(),
                "pid": os.getpid(),
                "thread": threading.current_thread().name,
                "event": event,
                "func": frame.f_code.co_name,
                "file": str(Path(frame.f_code.co_filename).name),  # Short name for compatibility
                "file_path": frame.f_code.co_filename,  # Full path for debugging
                "line": frame.f_lineno,
            }
            
            # Add execution time for strategic sampling decision (if available from return event)
            if event == "return" and hasattr(self, 'call_stack') and self.call_stack:
                for call_info in reversed(self.call_stack):
                    if call_info["func"] == frame.f_code.co_name:
                        execution_time = time.perf_counter() - call_info["start_time"]
                        event_info["execution_time_ms"] = execution_time * 1000
                        break
            
            # Strategic sampling decision
            if not self._should_capture_event(event_info):
                return self._trace_calls
            
            # Add context if available
            try:
                from .context import Context
                current_context = Context.get_current()
                if current_context:
                    event_info["context"] = current_context
            except ImportError:
                pass
            
            # Add enhanced context based on configuration
            if self.capture_memory:
                event_info["memory"] = self._capture_memory_info()
                
            if self.capture_source_lines and event in ("call", "exception"):
                event_info["source_line"] = self._get_source_line(frame)
            
            # Add event-specific data with enhancements
            if event == "exception":
                # Exception processing working correctly
                event_info.update(self._handle_exception_event(frame, arg))
            elif event == "call":
                event_info.update(self._handle_call_event(frame))
            elif event == "return":
                event_info.update(self._handle_return_event(frame, arg))
                
            # Queue the event
            self.queue.push(event_info)
        except Exception as e:
            # Check if this is a shutdown-related error
            if "sys.meta_path is None" in str(e) or "Python is likely shutting down" in str(e):
                # Python is shutting down, disable tracing
                self._active = False
                return None
            else:
                # Debug: Print what's breaking exception handling
                print(f"🚨 ThinkingSDK exception processing failed: {e}")
                import traceback
                traceback.print_exc()
            pass
        return self._trace_calls
    
    def _assess_exception_severity_and_impact(self, exception_type: str, exception_message: str, 
                                            frame) -> Dict[str, Any]:
        """Assess exception severity and business impact from runtime context."""
        
        # Get function and file context
        func_name = frame.f_code.co_name.lower()
        file_path = frame.f_code.co_filename.lower()
        
        # Assess business impact based on function/file context
        business_impact = self._assess_business_impact(func_name, file_path, frame)
        
        # Determine severity based on exception type and business context
        severity = self._calculate_exception_severity(exception_type, business_impact, exception_message)
        
        # Get strategic sampling priority (already calculated by strategic sampler)
        priority = 'ALWAYS'  # Exceptions are always high priority in strategic sampling
        if self.strategic_sampling_enabled and self.strategic_sampler:
            # Strategic sampler determines if this should be captured
            priority = self.strategic_sampler._classify_event_priority({
                'event': 'exception',
                'func': func_name,
                'file_path': file_path
            })
        
        return {
            "severity": severity,
            "business_impact": business_impact,
            "priority": priority.name if hasattr(priority, 'name') else str(priority),
            "fix_urgency": self._calculate_fix_urgency(severity, business_impact)
        }
    
    def _assess_business_impact(self, func_name: str, file_path: str, frame) -> str:
        """Assess business impact from runtime context."""
        
        # High business impact indicators
        high_impact_keywords = [
            'payment', 'checkout', 'billing', 'order', 'purchase', 'transaction',
            'login', 'auth', 'signup', 'register', 'security', 'password',
            'api', 'database', 'db', 'sql', 'query', 'connection',
            'user', 'customer', 'account', 'profile', 'subscription'
        ]
        
        # Check function name and file path for business context
        context_text = f"{func_name} {file_path}".lower()
        
        if any(keyword in context_text for keyword in high_impact_keywords):
            return 'high'
        
        # Check local variables for business entities
        try:
            locals_dict = frame.f_locals
            for var_name, var_value in locals_dict.items():
                var_name_lower = var_name.lower()
                if any(keyword in var_name_lower for keyword in high_impact_keywords):
                    return 'high'
                
                # Check if variable contains business-critical data
                var_str = str(var_value).lower()
                if any(keyword in var_str for keyword in ['user_id', 'customer_id', 'order_id', 'payment_id']):
                    return 'high'
        except:
            pass
        
        return 'medium'
    
    def _calculate_exception_severity(self, exception_type: str, business_impact: str, 
                                    exception_message: str) -> str:
        """Calculate exception severity based on type, business impact, and context."""
        
        # Critical exceptions (code structure issues)
        critical_exceptions = [
            'SyntaxError', 'NameError', 'ImportError', 'ModuleNotFoundError'
        ]
        
        # High priority exceptions (runtime issues)  
        high_exceptions = [
            'AttributeError', 'TypeError', 'ValueError', 'KeyError', 
            'IndexError', 'ZeroDivisionError', 'FileNotFoundError'
        ]
        
        if exception_type in critical_exceptions:
            return 'critical'
        
        if exception_type in high_exceptions:
            if business_impact == 'high':
                return 'critical'  # High business impact elevates severity
            return 'high'
        
        # Business impact can elevate any exception
        if business_impact == 'high':
            return 'high'
        
        return 'medium'
    
    def _calculate_fix_urgency(self, severity: str, business_impact: str) -> str:
        """Calculate how urgently this needs to be fixed."""
        
        if severity == 'critical':
            return 'immediate'  # Fix within minutes
        
        if severity == 'high' and business_impact == 'high':
            return 'urgent'     # Fix within hours
        
        if severity == 'high':
            return 'high'       # Fix within day
        
        return 'normal'         # Fix in next sprint
        
    def _main_thread_exception_handler(self, exc_type, exc_value, exc_traceback) -> None:
        """Handle exceptions in main thread."""
        try:
            if not self._active:
                return
            
            # Check if this exception was already captured by sys.settrace (preferred)
            if self._last_captured_exception:
                last_type, last_message, last_time = self._last_captured_exception
                if (exc_type == last_type and 
                    str(exc_value) == last_message and 
                    time.time() - last_time < 1.0):  # Within 1 second
                    # Skip duplicate - sys.settrace already captured this exception
                    return
            
            # Successfully capturing main thread exceptions via sys.excepthook
            
            # Extract actual file info from the deepest traceback frame
            if exc_traceback:
                # Get the last (deepest) frame from traceback
                tb = exc_traceback
                while tb.tb_next:
                    tb = tb.tb_next
                
                actual_file = tb.tb_frame.f_code.co_filename
                actual_line = tb.tb_lineno
                actual_func = tb.tb_frame.f_code.co_name
            else:
                actual_file = "main_thread"
                actual_line = 0
                actual_func = "<module>"
            
            exc_info = {
                "ts": time.time(),
                "pid": os.getpid(),
                "thread": threading.current_thread().name,
                "event": "exception",
                "exception": {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                    "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback),
                    "structured_traceback": [
                        {
                            "file": tb.filename,
                            "line": tb.lineno,
                            "name": tb.name,
                            "text": tb.line
                        }
                        for tb in traceback.extract_tb(exc_traceback)
                    ]
                },
                "context": {"source": "sys_excepthook"},
                "func": actual_func,
                "file": str(Path(actual_file).name),  # Show real filename
                "line": actual_line
            }
            
            self.queue.push(exc_info)
        except Exception as e:
            print(f"🚨 ThinkingSDK: Failed to process main thread exception: {e}")
        
        # Call original handler to maintain normal Python behavior
        if self._original_sys_excepthook:
            try:
                self._original_sys_excepthook(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

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

    def _handle_exception_event(self, frame, exc_info) -> Dict[str, Any]:
        """Handle exception events with enhanced context."""
        exc_type, exc_val, exc_tb = exc_info
        
        # Get full traceback for AI analysis
        full_traceback = traceback.format_exception(exc_type, exc_val, exc_tb)
        
        # Extract structured stack trace with full file paths and variable context
        tb_list = traceback.extract_tb(exc_tb)
        structured_traceback = []
        
        # Walk the traceback to capture variables at each frame
        current_tb = exc_tb
        tb_index = 0
        while current_tb and tb_index < len(tb_list):
            tb_frame_info = tb_list[tb_index]
            frame_obj = current_tb.tb_frame
            
            # Capture all local and global variables for this frame
            frame_locals = self._capture_all_frame_variables(frame_obj.f_locals, 'locals')
            frame_globals = self._capture_all_frame_variables(frame_obj.f_globals, 'globals')
            
            structured_traceback.append({
                "file": tb_frame_info.filename,
                "file_path": tb_frame_info.filename,  # Full path for auto-fix
                "line": tb_frame_info.lineno,
                "func": tb_frame_info.name,
                "code": tb_frame_info.line,  # Actual line of code
                "locals": frame_locals,  # All local variables in this frame
                "globals": frame_globals,  # Relevant global variables in this frame
                "frame_index": tb_index
            })
            
            current_tb = current_tb.tb_next
            tb_index += 1
        
        # Get source context around error
        source_context = self._get_source_context(frame, lines_before=3, lines_after=3)
        
        exception_data = {
            "exception": {
                "type": exc_type.__name__,
                "message": str(exc_val),  # Use 'message' instead of 'msg' for consistency
                "traceback": full_traceback,  # Full traceback for analysis
                "traceback_summary": full_traceback[-5:],  # Last 5 for display
                "structured_traceback": structured_traceback,  # Structured for processing
                "source_context": source_context  # Code around error
            },
            "locals": self._capture_locals(frame),
            "globals": self._capture_globals(frame)  # Add globals for context
        }
        
        # Add client-side severity and business impact assessment
        exception_data.update(self._assess_exception_severity_and_impact(
            exc_type.__name__, str(exc_val), frame
        ))
        
        # Add call stack context if available
        if self.capture_call_patterns and hasattr(self, 'call_stack'):
            exception_data["call_stack_depth"] = len(self.call_stack)
            exception_data["call_stack"] = [
                {
                    "func": call.get("func"),
                    "file": call.get("file"),
                    "start_time": call.get("start_time")
                } 
                for call in self.call_stack[-10:]  # Last 10 calls
            ]
        
        # Add git repository context for auto-fix
        git_repositories = self._config.get('git_repositories', [])
        if git_repositories:
            # Use the first repository from the config
            repo_url = git_repositories[0]
            
            # Extract repo name from URL (e.g., https://github.com/user/repo -> user/repo)
            repo_full_name = None
            if repo_url.startswith('https://github.com/'):
                repo_full_name = repo_url.replace('https://github.com/', '').rstrip('/')
                if repo_full_name.endswith('.git'):
                    repo_full_name = repo_full_name[:-4]
            elif repo_url.startswith('git@github.com:'):
                repo_full_name = repo_url.replace('git@github.com:', '').rstrip('/')
                if repo_full_name.endswith('.git'):
                    repo_full_name = repo_full_name[:-4]
            
            exception_data["repository_context"] = {
                "git_repositories": git_repositories,  # Keep for backward compatibility
                "repo_full_name": repo_full_name,
                "branch": "main",  # Default branch, could be made configurable
                "commit_hash": None,  # Would need git integration to get actual commit
                "auto_fix_enabled": True
            }
        else:
            exception_data["repository_context"] = {
                "git_repositories": [],
                "repo_full_name": None,
                "branch": None,
                "commit_hash": None,
                "auto_fix_enabled": False
            }
        
        return exception_data
    
    def _handle_call_event(self, frame) -> Dict[str, Any]:
        """Handle function call events with performance and pattern tracking."""
        func_name = frame.f_code.co_name
        call_data = {
            "locals": self._capture_locals(frame)
        }
        
        # Performance and pattern tracking
        if self.capture_performance or self.capture_call_patterns:
            self.function_call_counts[func_name] += 1
            
            # Track call stack for performance measurement
            if self.capture_performance:
                import time
                call_info = {
                    "func": func_name,
                    "file": frame.f_code.co_filename,  # Full file path
                    "line": frame.f_lineno,
                    "start_time": time.perf_counter(),
                    "frame_id": id(frame)
                }
                self.call_stack.append(call_info)
            
            # Add call frequency information
            call_data["call_count"] = self.function_call_counts[func_name]
            
            # Detect patterns
            if self.capture_call_patterns:
                call_data.update(self._detect_call_patterns(func_name, frame))
        
        # Enhanced function metadata
        call_data.update({
            "arg_count": frame.f_code.co_argcount,
            "local_count": frame.f_code.co_nlocals,
            "has_varargs": bool(frame.f_code.co_flags & 0x04),
            "has_kwargs": bool(frame.f_code.co_flags & 0x08),
        })
        return call_data
    
    def _handle_return_event(self, frame, return_value) -> Dict[str, Any]:
        """Handle function return events with performance analysis."""
        func_name = frame.f_code.co_name
        return_data = {}
        
        # Capture return value if enabled
        if self.capture_returns and return_value is not None:
            return_data["return_value"] = self._safe_repr(return_value)
            return_data["return_type"] = type(return_value).__name__
            
            # Analyze return value patterns
            return_data.update(self._analyze_return_value(return_value))
        
        # Performance tracking
        if self.capture_performance and hasattr(self, 'call_stack') and self.call_stack:
            # Find matching call in stack
            for i, call_info in enumerate(reversed(self.call_stack)):
                if call_info["func"] == func_name:
                    # Calculate execution time
                    import time
                    execution_time = time.perf_counter() - call_info["start_time"]
                    
                    # Remove from call stack
                    self.call_stack.pop(len(self.call_stack) - 1 - i)
                    
                    # Add performance data
                    return_data.update({
                        "execution_time_ms": execution_time * 1000,
                        "is_slow": execution_time > self.slow_function_threshold
                    })
                    
                    # Track function timing statistics
                    self.function_timings[func_name].append(execution_time)
                    if len(self.function_timings[func_name]) > 1:
                        timings = self.function_timings[func_name]
                        return_data["avg_execution_time_ms"] = (sum(timings) / len(timings)) * 1000
                        return_data["execution_count"] = len(timings)
                    
                    # Detect performance anomalies
                    if execution_time > self.slow_function_threshold:
                        return_data["performance_alert"] = {
                            "type": "slow_function",
                            "severity": "high" if execution_time > (self.slow_function_threshold * 10) else "medium"
                        }
                    
                    break
        return return_data
    
    def _detect_call_patterns(self, func_name, frame) -> Dict[str, Any]:
        """Detect interesting call patterns."""
        patterns = {}
        
        # Detect recursive calls
        if hasattr(self, 'call_stack'):
            recursive_count = sum(1 for call in self.call_stack if call["func"] == func_name)
            if recursive_count > 0:
                patterns["is_recursive"] = True
                patterns["recursion_depth"] = recursive_count
        
        # Detect hot path functions
        if self.function_call_counts[func_name] > self.hot_path_threshold:
            patterns["is_hot_path"] = True
            
        # Detect first-time function calls
        if self.function_call_counts[func_name] == 1:
            patterns["is_first_call"] = True
        return patterns
    
    def _analyze_return_value(self, value) -> Dict[str, Any]:
        """Analyze return value for patterns."""
        analysis = {}
        
        try:
            # Basic type analysis
            value_type = type(value).__name__
            analysis["return_analysis"] = {"type": value_type}
            
            # Pattern detection
            if value is None:
                analysis["return_analysis"]["pattern"] = "null_return"
            elif isinstance(value, bool):
                analysis["return_analysis"]["pattern"] = "boolean_return"
                analysis["return_analysis"]["value"] = value
            elif isinstance(value, (list, tuple)) and len(value) == 0:
                analysis["return_analysis"]["pattern"] = "empty_collection"
            elif isinstance(value, dict) and not value:
                analysis["return_analysis"]["pattern"] = "empty_dict"
            elif isinstance(value, (int, float)) and value == 0:
                analysis["return_analysis"]["pattern"] = "zero_return"
            elif isinstance(value, str) and value == "":
                analysis["return_analysis"]["pattern"] = "empty_string"
            
            # Size analysis for collections
            if hasattr(value, '__len__'):
                try:
                    length = len(value)
                    analysis["return_analysis"]["length"] = length
                    if length > 1000:
                        analysis["return_analysis"]["size_warning"] = "large_collection"
                except:
                    pass
        except Exception:
            analysis["return_analysis"] = {"type": "unknown", "error": "analysis_failed"}            
        return analysis
    
    def _capture_memory_info(self) -> Dict[str, Any]:
        """Capture current memory usage information."""
        if not self.capture_memory or not hasattr(self, 'process'):
            return {}

        try:
            memory_info = self.process.memory_info()
            memory_data = {
                "rss": memory_info.rss,  # Resident Set Size
                "vms": memory_info.vms,  # Virtual Memory Size
                "percent": self.process.memory_percent()
            }
            
            # Calculate memory delta
            if self._last_memory is not None:
                memory_data["delta"] = memory_info.rss - self._last_memory
            self._last_memory = memory_info.rss
            return memory_data
        except Exception:
            return {"error": "memory_capture_failed"}
    
    def _get_source_line(self, frame) -> str:
        """Get the source code line being executed."""
        try:
            import linecache
            source_line = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
            return source_line.strip() if source_line else "<source unavailable>"
        except Exception:
            return "<source unavailable>"
    
    def _get_source_context(self, frame, lines_before: int = 3, lines_after: int = 3) -> Dict[str, Any]:
        """Get source code context around the current line."""
        try:
            import linecache
            filename = frame.f_code.co_filename
            current_line = frame.f_lineno
            
            context = {
                "file": filename,
                "current_line": current_line,
                "lines": {}
            }
            
            # Get lines before and after
            start = max(1, current_line - lines_before)
            end = current_line + lines_after + 1
            
            for line_no in range(start, end):
                line = linecache.getline(filename, line_no)
                if line:
                    # Mark current line
                    prefix = ">>> " if line_no == current_line else "    "
                    context["lines"][line_no] = prefix + line.rstrip()
            return context
        except Exception:
            return {"error": "Could not get source context"}
    
    def _capture_all_frame_variables(self, variables_dict: Dict, var_type: str) -> Dict[str, Any]:
        """Capture all relevant variables from a frame without PII filtering (as requested)."""
        try:
            captured = {}
            
            for key, value in variables_dict.items():
                # Skip private Python internals but keep everything else
                if var_type == 'globals' and (
                    key.startswith('__builtins__') or 
                    key in ('__name__', '__file__', '__package__', '__loader__', '__spec__')
                ):
                    continue
                
                # For locals, capture everything including private vars (debugging needs all context)
                if var_type == 'locals' or not key.startswith('__'):
                    try:
                        # Capture with type information for better Claude analysis
                        captured[key] = {
                            'value': self._safe_repr(value, max_length=1000),  # Longer for debugging
                            'type': type(value).__name__,
                            'repr': repr(value)[:500] if hasattr(value, '__repr__') else str(type(value))
                        }
                    except Exception:
                        captured[key] = {
                            'value': '<capture_failed>',
                            'type': 'unknown',
                            'repr': '<repr_failed>'
                        }
                
                # Limit total variables to prevent excessive data
                if len(captured) >= 50:  # Higher limit for debugging
                    break
                    
            return captured
        except Exception:
            return {}
    
    def _capture_globals(self, frame) -> Dict[str, str]:
        """Safely capture global variables from a frame."""
        try:
            globals_dict = {}
            
            # Only capture non-builtin globals
            for key, value in frame.f_globals.items():
                # Skip builtins and modules
                if key.startswith('__') or isinstance(value, type(os)):
                    continue
                    
                # Skip functions and classes (too verbose)
                if callable(value) and not isinstance(value, (str, int, float, bool)):
                    continue
                    
                # Limit number of globals
                if len(globals_dict) >= self.max_locals:
                    break
                    
                globals_dict[key] = self._safe_repr(value)
            return globals_dict
        except Exception:
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get instrumentation statistics."""
        stats = {
            "active": self._active,
            "event_count": self._event_count,
            "sample_rate": self.sample_rate,
            "config": self._config.copy(),
            "strategic_sampling_enabled": self.strategic_sampling_enabled
        }
        
        # Add strategic sampling statistics
        if self.strategic_sampling_enabled and self.strategic_sampler:
            stats["strategic_sampling"] = self.strategic_sampler.get_sampling_stats()
        
        # Add performance statistics if enabled
        if self.capture_performance and hasattr(self, 'function_call_counts'):
            stats["performance"] = {
                "total_function_calls": sum(self.function_call_counts.values()),
                "unique_functions": len(self.function_call_counts),
                "hot_functions": {func: count for func, count in self.function_call_counts.items() 
                                if count > self.hot_path_threshold}
            }
            
            if hasattr(self, 'function_timings'):
                slow_functions = {}
                for func, timings in self.function_timings.items():
                    avg_time = sum(timings) / len(timings) if timings else 0
                    if avg_time > self.slow_function_threshold:
                        slow_functions[func] = {
                            "avg_time_ms": avg_time * 1000,
                            "call_count": len(timings),
                            "total_time_ms": sum(timings) * 1000
                        }
                stats["performance"]["slow_functions"] = slow_functions
        return stats
    
    def mark_custom_event(self, func_name: str) -> None:
        """Mark the next event from this function as custom/business-critical."""
        if self.strategic_sampling_enabled and self.strategic_sampler:
            # This would need to be implemented with frame tracking
            pass
    
    def update_remote_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration from remote server."""
        if self.strategic_sampling_enabled and self.strategic_sampler:
            self.strategic_sampler.update_config(new_config)