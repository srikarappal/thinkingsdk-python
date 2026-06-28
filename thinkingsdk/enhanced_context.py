"""
Enhanced context capture for exceptions in ThinkingSDK.

Captures comprehensive system, environment, and runtime context
when exceptions occur to provide maximum debugging information.
"""

import os
import sys
import platform
import threading
import gc
import time
import psutil
from typing import Dict, Any, List, Optional
from pathlib import Path


class EnhancedContextCapture:
    """Captures comprehensive context when exceptions occur."""
    
    # Environment variables to exclude (for privacy)
    SENSITIVE_ENV_PATTERNS = [
        'KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'PASS', 'PWD',
        'AUTH', 'CREDENTIAL', 'PRIVATE', 'API_KEY', 'ACCESS'
    ]
    
    # Environment variables to include (whitelist)
    SAFE_ENV_VARS = [
        'PATH', 'PYTHONPATH', 'PYTHON_HOME', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV',
        'PWD', 'HOME', 'USER', 'SHELL', 'TERM', 'LANG', 'LC_ALL',
        'DEBUG', 'ENV', 'ENVIRONMENT', 'NODE_ENV', 'FLASK_ENV', 'DJANGO_SETTINGS_MODULE',
        'TZ', 'HOSTNAME', 'COMPUTERNAME', 'OS', 'PROCESSOR_ARCHITECTURE'
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with optional configuration."""
        self.config = config or {}
        self.process = None
        self.start_time = time.time()
        
        # Try to initialize psutil for system info
        try:
            self.process = psutil.Process()
        except Exception:
            pass
    
    def capture_all(self) -> Dict[str, Any]:
        """Capture all enhanced context for an exception."""
        context = {}
        
        # Always capture these (low overhead, high value)
        context['system'] = self.capture_system_info()
        context['runtime'] = self.capture_runtime_info()
        context['environment'] = self.capture_environment_context()
        
        # Conditionally capture based on config
        if self.config.get('capture_threads', True):
            context['threads'] = self.capture_thread_info()
        
        return context
    
    def capture_system_info(self) -> Dict[str, Any]:
        """Capture system information (memory, CPU, disk)."""
        import socket
        
        info = {
            'platform': platform.platform(),
            'hostname': socket.gethostname(),  # Match Sentry's server_name
            'python_version': sys.version,
            'python_implementation': platform.python_implementation(),
        }
        
        if self.process:
            try:
                # Memory info
                memory_info = self.process.memory_info()
                virtual_memory = psutil.virtual_memory()
                
                info['memory'] = {
                    'process_rss_mb': memory_info.rss / 1024 / 1024,
                    'process_vms_mb': memory_info.vms / 1024 / 1024,
                    'system_total_mb': virtual_memory.total / 1024 / 1024,
                    'system_available_mb': virtual_memory.available / 1024 / 1024,
                    'system_percent': virtual_memory.percent,
                }
                
                # CPU info
                info['cpu'] = {
                    'process_percent': self.process.cpu_percent(),
                    'system_percent': psutil.cpu_percent(interval=0),
                    'system_count': psutil.cpu_count(),
                    'system_load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None,
                }
                
                # Disk info (only for CWD)
                try:
                    cwd = os.getcwd()
                    disk_usage = psutil.disk_usage(cwd)
                    info['disk'] = {
                        'cwd': cwd,
                        'free_mb': disk_usage.free / 1024 / 1024,
                        'total_mb': disk_usage.total / 1024 / 1024,
                        'percent': disk_usage.percent,
                    }
                except Exception:
                    pass
                
            except Exception as e:
                info['error'] = f"Failed to capture system info: {e}"
        
        return info
    
    def capture_runtime_info(self) -> Dict[str, Any]:
        """Capture process and runtime information."""
        info = {
            'process_id': os.getpid(),
            'process_uptime_seconds': time.time() - self.start_time,
            'python_version': '.'.join(map(str, sys.version_info[:3])),
            'python_implementation': platform.python_implementation(),
            'python_compiler': platform.python_compiler(),
            'executable': sys.executable,
            'prefix': sys.prefix,
        }
        
        # GC stats
        gc_stats = gc.get_stats()
        if gc_stats:
            latest_gc = gc_stats[-1] if gc_stats else {}
            info['gc'] = {
                'collections': [gc.get_count()],
                'thresholds': gc.get_threshold(),
                'collected': latest_gc.get('collected', 0),
                'uncollectable': latest_gc.get('uncollectable', 0),
            }
        
        # Open file descriptors (lightweight check)
        if self.process:
            try:
                info['open_files_count'] = len(self.process.open_files())
                info['connections_count'] = len(self.process.connections())
            except Exception:
                pass
        
        return info
    
    def capture_environment_context(self) -> Dict[str, Any]:
        """Capture environment context (filtered for privacy)."""
        info = {
            'cwd': os.getcwd(),
            'command_line': sys.argv,
            'python_path': sys.path[:5],  # First 5 paths only
            'environment': os.environ.get('ENVIRONMENT', os.environ.get('ENV', 'production')),  # Match Sentry
            'release': os.environ.get('RELEASE', os.environ.get('VERSION', None)),  # Release tracking
        }
        
        # Virtual environment detection
        info['virtual_env'] = {
            'active': hasattr(sys, 'real_prefix') or (
                hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
            ),
            'path': os.environ.get('VIRTUAL_ENV'),
            'conda': os.environ.get('CONDA_DEFAULT_ENV'),
        }
        
        # Filtered environment variables
        safe_env = {}
        for key in self.SAFE_ENV_VARS:
            if key in os.environ:
                value = os.environ[key]
                # Truncate long values
                if len(value) > 200:
                    value = value[:200] + '...(truncated)'
                safe_env[key] = value
        
        # Also include any DEBUG/ENV related vars
        for key, value in os.environ.items():
            if any(pattern in key.upper() for pattern in ['DEBUG', 'ENV', 'MODE']):
                if not any(sensitive in key.upper() for sensitive in self.SENSITIVE_ENV_PATTERNS):
                    if len(value) > 200:
                        value = value[:200] + '...(truncated)'
                    safe_env[key] = value
        
        info['env_vars'] = safe_env
        info['env_vars_count'] = len(os.environ)
        
        return info
    
    def capture_thread_info(self) -> Dict[str, Any]:
        """Capture thread information."""
        info = {
            'current_thread': threading.current_thread().name,
            'thread_count': threading.active_count(),
            'threads': []
        }
        
        # List all threads with their state
        for thread in threading.enumerate():
            thread_info = {
                'name': thread.name,
                'daemon': thread.daemon,
                'alive': thread.is_alive(),
                'ident': thread.ident,
            }
            
            # Add thread type if it's a special thread
            if hasattr(thread, '__class__'):
                thread_info['type'] = thread.__class__.__name__
            
            info['threads'].append(thread_info)
        
        # Check for potential deadlock (simple heuristic)
        blocked_count = sum(1 for t in threading.enumerate() if not t.daemon and t.is_alive())
        if blocked_count > 10:
            info['warning'] = f"High number of non-daemon threads: {blocked_count}"
        
        return info
    
    def get_context_size_estimate(self, context: Dict[str, Any]) -> int:
        """Estimate the size of captured context in bytes."""
        import json
        try:
            return len(json.dumps(context, default=str))
        except:
            return 0


# Singleton instance
_enhanced_context_capture = None

def get_enhanced_context() -> Optional[EnhancedContextCapture]:
    """Get the singleton enhanced context capture instance."""
    return _enhanced_context_capture

def initialize_enhanced_context(config: Optional[Dict[str, Any]] = None):
    """Initialize the enhanced context capture."""
    global _enhanced_context_capture
    _enhanced_context_capture = EnhancedContextCapture(config)
    return _enhanced_context_capture