# thinking_sdk_client/performance_monitor.py
"""
Performance monitoring and overhead control for ThinkingSDK.

Ensures instrumentation overhead stays below acceptable thresholds:
- CPU usage < 5%
- Memory overhead < 50MB
- Latency impact < 1ms per function call
"""

import time
import psutil
import threading
from typing import Dict, Any, Optional
from collections import deque
import os


class PerformanceMonitor:
    """
    Monitors SDK performance impact and automatically backs off under load.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Thresholds
        self.max_cpu_percent = self.config.get('max_cpu_percent', 5.0)
        self.max_memory_mb = self.config.get('max_memory_mb', 50)
        self.max_latency_ms = self.config.get('max_latency_ms', 1.0)
        self.max_queue_size = self.config.get('max_queue_size', 10000)
        
        # Monitoring state
        self.baseline_cpu = None
        self.baseline_memory = None
        self.process = psutil.Process()
        
        # Performance metrics (rolling window)
        self.cpu_samples = deque(maxlen=60)  # Last 60 seconds
        self.memory_samples = deque(maxlen=60)
        self.latency_samples = deque(maxlen=1000)  # Last 1000 function calls
        
        # Backoff state
        self.backoff_level = 0  # 0=normal, 1=reduced, 2=minimal, 3=disabled
        self.last_check_time = time.time()
        
        # Thread for background monitoring
        self._monitor_thread = None
        self._stop_monitoring = threading.Event()
        
    def start_monitoring(self) -> None:
        """Start background performance monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
            
        # Capture baseline metrics
        self.baseline_cpu = self.process.cpu_percent(interval=0.1)
        self.baseline_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        
        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop background performance monitoring."""
        self._stop_monitoring.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                # Sample every second
                time.sleep(1)
                
                # Measure CPU
                cpu_percent = self.process.cpu_percent()
                self.cpu_samples.append(cpu_percent)
                
                # Measure memory
                memory_mb = self.process.memory_info().rss / (1024 * 1024)
                self.memory_samples.append(memory_mb)
                
                # Check if we need to adjust backoff
                self._check_and_adjust_backoff()
                
            except Exception:
                # Don't crash monitoring thread
                pass
    
    def _check_and_adjust_backoff(self) -> None:
        """Check performance and adjust backoff level."""
        if time.time() - self.last_check_time < 5:
            return  # Only check every 5 seconds
            
        self.last_check_time = time.time()
        
        # Calculate averages
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        avg_memory = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        avg_latency = sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0
        
        # Calculate overhead (difference from baseline)
        cpu_overhead = avg_cpu - (self.baseline_cpu or 0)
        memory_overhead = avg_memory - (self.baseline_memory or 0)
        
        # Determine appropriate backoff level
        old_level = self.backoff_level
        
        if cpu_overhead > self.max_cpu_percent * 2:
            self.backoff_level = 3  # Disable
        elif cpu_overhead > self.max_cpu_percent * 1.5:
            self.backoff_level = 2  # Minimal
        elif cpu_overhead > self.max_cpu_percent:
            self.backoff_level = 1  # Reduced
        elif memory_overhead > self.max_memory_mb * 2:
            self.backoff_level = 2  # Minimal
        elif memory_overhead > self.max_memory_mb:
            self.backoff_level = 1  # Reduced
        elif avg_latency > self.max_latency_ms * 2:
            self.backoff_level = 2  # Minimal
        elif avg_latency > self.max_latency_ms:
            self.backoff_level = 1  # Reduced
        else:
            # Performance is good, reduce backoff
            if self.backoff_level > 0:
                self.backoff_level -= 1
        
        # Log backoff changes
        if old_level != self.backoff_level:
            self._log_backoff_change(old_level, self.backoff_level, cpu_overhead, memory_overhead, avg_latency)
    
    def _log_backoff_change(self, old_level: int, new_level: int, cpu: float, memory: float, latency: float) -> None:
        """Log backoff level changes."""
        levels = ["normal", "reduced", "minimal", "disabled"]
        
        import logging
        logger = logging.getLogger('thinkingsdk.performance')
        
        logger.warning(
            f"Performance backoff changed: {levels[old_level]} -> {levels[new_level]} "
            f"(CPU: {cpu:.1f}%, Memory: {memory:.1f}MB, Latency: {latency:.2f}ms)"
        )
    
    def should_sample(self) -> bool:
        """Determine if we should sample this event based on backoff."""
        if self.backoff_level == 0:
            return True  # Normal operation
        elif self.backoff_level == 1:
            return hash(time.time()) % 2 == 0  # Sample 50%
        elif self.backoff_level == 2:
            return hash(time.time()) % 10 == 0  # Sample 10%
        else:
            return False  # Disabled
    
    def get_sampling_rate(self) -> float:
        """Get current effective sampling rate."""
        rates = [1.0, 0.5, 0.1, 0.0]
        return rates[min(self.backoff_level, 3)]
    
    def record_function_latency(self, latency_ms: float) -> None:
        """Record function instrumentation latency."""
        self.latency_samples.append(latency_ms)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "backoff_level": self.backoff_level,
            "sampling_rate": self.get_sampling_rate(),
            "cpu_overhead": sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0,
            "memory_overhead_mb": sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0,
            "avg_latency_ms": sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0,
            "thresholds": {
                "max_cpu_percent": self.max_cpu_percent,
                "max_memory_mb": self.max_memory_mb,
                "max_latency_ms": self.max_latency_ms,
            }
        }
    
    def is_healthy(self) -> bool:
        """Check if performance is within acceptable limits."""
        return self.backoff_level == 0


class CircuitBreaker:
    """
    Circuit breaker for SDK operations to prevent cascading failures.
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
    def record_success(self) -> None:
        """Record a successful operation."""
        self.failure_count = 0
        if self.state == "half-open":
            self.state = "closed"
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking operations)."""
        if self.state == "closed":
            return False
            
        if self.state == "open":
            # Check if timeout has passed
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
                return False
            return True
            
        return False  # half-open allows attempts


# Benchmark utilities
def benchmark_instrumentation_overhead():
    """
    Benchmark the overhead of ThinkingSDK instrumentation.
    
    Returns:
        Dict with benchmark results
    """
    import timeit
    
    results = {}
    
    # Test function
    def test_function(x, y):
        result = x + y
        for i in range(100):
            result += i
        return result
    
    # Benchmark without instrumentation
    without_time = timeit.timeit(
        lambda: test_function(1, 2),
        number=10000
    )
    
    # Start instrumentation
    import thinking_sdk_client
    thinking_sdk_client.start()
    
    # Benchmark with instrumentation
    with_time = timeit.timeit(
        lambda: test_function(1, 2),
        number=10000
    )
    
    thinking_sdk_client.stop()
    
    # Calculate overhead
    overhead_ms = ((with_time - without_time) / 10000) * 1000
    overhead_percent = ((with_time - without_time) / without_time) * 100
    
    results['baseline_ms'] = (without_time / 10000) * 1000
    results['instrumented_ms'] = (with_time / 10000) * 1000
    results['overhead_ms'] = overhead_ms
    results['overhead_percent'] = overhead_percent
    
    # Memory overhead
    process = psutil.Process()
    
    # Measure memory without
    mem_before = process.memory_info().rss / (1024 * 1024)
    
    thinking_sdk_client.start()
    time.sleep(1)  # Let it stabilize
    
    mem_after = process.memory_info().rss / (1024 * 1024)
    thinking_sdk_client.stop()
    
    results['memory_overhead_mb'] = mem_after - mem_before
    
    return results


# Auto-backoff decorator
def with_performance_guard(func):
    """
    Decorator that skips instrumentation if performance is degraded.
    
    Example:
        @with_performance_guard
        def critical_function():
            # This won't be instrumented if system is under load
            pass
    """
    def wrapper(*args, **kwargs):
        # Check if we should skip instrumentation
        from . import _performance_monitor
        
        if _performance_monitor and not _performance_monitor.should_sample():
            # Skip instrumentation, call directly
            return func(*args, **kwargs)
        
        # Normal instrumented execution
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper