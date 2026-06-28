# tests/test_utils.py
"""Test utilities for ThinkingSDK tests."""

import os
import sys
import time
import threading
import unittest
from unittest.mock import patch
from typing import Dict, Any, Optional
import thinkingsdk as thinking


class IsolatedTestCase(unittest.TestCase):
    """Base test case with proper isolation."""
    
    def setUp(self):
        """Set up isolated test environment."""
        super().setUp()
        
        # Store original environment variables
        self._original_env = {}
        env_vars_to_store = [
            'THINKINGSDK_SAMPLE_RATE',
            'THINKINGSDK_BATCH_SIZE', 
            'THINKINGSDK_QUEUE_SIZE',
            'THINKINGSDK_ENABLE_LOGGING',
            'THINKINGSDK_LOG_LEVEL'
        ]
        
        for var in env_vars_to_store:
            if var in os.environ:
                self._original_env[var] = os.environ[var]
                del os.environ[var]
                
        # Ensure ThinkingSDK is stopped
        try:
            thinking.stop()
        except:
            pass
            
        # Reset any global state
        thinking._instrumentation = None
        thinking._sender = None
        thinking._queue = None
        thinking._config = None
        
    def tearDown(self):
        """Clean up after test."""
        # Stop ThinkingSDK if running
        try:
            thinking.stop(timeout=1.0)
        except:
            pass
            
        # Reset global state
        thinking._instrumentation = None
        thinking._sender = None
        thinking._queue = None
        thinking._config = None
        
        # Restore environment variables
        for var, value in self._original_env.items():
            os.environ[var] = value
            
        # Clear any environment variables we might have set
        env_vars_to_clear = [
            'THINKINGSDK_SAMPLE_RATE',
            'THINKINGSDK_BATCH_SIZE', 
            'THINKINGSDK_QUEUE_SIZE',
            'THINKINGSDK_ENABLE_LOGGING',
            'THINKINGSDK_LOG_LEVEL'
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ and var not in self._original_env:
                del os.environ[var]
                
        super().tearDown()


class MockNetworkTestCase(IsolatedTestCase):
    """Test case with mock network setup."""
    
    def setUp(self):
        """Set up with mock network."""
        super().setUp()
        
        # Start patching requests
        self.requests_patcher = patch('thinkingsdk.background_sender.requests.Session')
        self.mock_session_class = self.requests_patcher.start()
        
        # Create mock session with successful responses
        self.mock_session = self.mock_session_class.return_value
        self.mock_response = self.mock_session.post.return_value
        self.mock_response.status_code = 200
        
    def tearDown(self):
        """Clean up mock network."""
        self.requests_patcher.stop()
        super().tearDown()
        
    def set_network_failure(self, exception_type=Exception, message="Network error"):
        """Configure network to fail."""
        self.mock_session.post.side_effect = exception_type(message)
        
    def set_http_status(self, status_code: int):
        """Set HTTP response status code."""
        self.mock_response.status_code = status_code
        
    def get_request_count(self) -> int:
        """Get number of HTTP requests made."""
        return self.mock_session.post.call_count


def wait_for_condition(condition_func, timeout=1.0, interval=0.01):
    """Wait for a condition to become true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False


def create_test_config(**overrides) -> Dict[str, Any]:
    """Create a test configuration with reasonable defaults."""
    config = {
        'instrumentation': {
            'sample_rate': 1.0,  # Always sample for predictable tests
            'capture_returns': False,
            'max_locals': 3,
            'max_local_length': 50
        },
        'sender': {
            'batch_size': 5,  # Small batches for faster tests
            'max_batch_wait': 0.1,  # Quick batching
            'retry_attempts': 1,  # Minimal retries for speed
            'request_timeout': 1.0  # Short timeout
        },
        'queue': {
            'maxsize': 100,  # Small queue for tests
            'drop_strategy': 'oldest'
        },
        'enable_logging': False
    }
    
    # Apply overrides
    for section, values in overrides.items():
        if section in config and isinstance(values, dict):
            config[section].update(values)
        else:
            config[section] = values
            
    return config


def start_test_sdk(api_key="test_key", server_url="http://test.com", **config_overrides):
    """Start SDK with test-friendly configuration."""
    config = create_test_config(**config_overrides)
    thinking.start(api_key, server_url, config=config)
    
    # Wait for components to be ready
    if not wait_for_condition(lambda: thinking.is_active(), timeout=0.5):
        raise RuntimeError("SDK failed to start within timeout")


def generate_test_events(count=5):
    """Generate test events by executing simple functions."""
    results = []
    
    for i in range(count):
        def test_func(x=i):
            return x * 2
            
        result = test_func()
        results.append(result)
        
    return results


def assert_stats_valid(test_case, stats):
    """Assert that stats dictionary has expected structure."""
    test_case.assertIsInstance(stats, dict)
    test_case.assertIn('sdk_active', stats)
    test_case.assertIn('config', stats)
    test_case.assertIn('queue', stats)
    test_case.assertIn('instrumentation', stats)
    test_case.assertIn('sender', stats)


class ThreadSafeTestCase(IsolatedTestCase):
    """Test case for thread safety testing."""
    
    def setUp(self):
        """Set up thread safety test."""
        super().setUp()
        self.errors = []
        self.results = []
        self.lock = threading.Lock()
        
    def add_error(self, error):
        """Thread-safe error recording."""
        with self.lock:
            self.errors.append(error)
            
    def add_result(self, result):
        """Thread-safe result recording."""
        with self.lock:
            self.results.append(result)
            
    def assert_no_errors(self):
        """Assert no errors occurred in threads."""
        self.assertEqual(len(self.errors), 0, f"Thread errors: {self.errors}")
        
    def run_concurrent_test(self, worker_func, num_threads=3, timeout=5.0):
        """Run a function concurrently in multiple threads."""
        threads = []
        
        for i in range(num_threads):
            thread = threading.Thread(target=worker_func, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=timeout)
            
        # Check for still-running threads
        alive_threads = [t for t in threads if t.is_alive()]
        if alive_threads:
            raise RuntimeError(f"{len(alive_threads)} threads still running after timeout")


def skip_if_no_network():
    """Skip test if network is not available."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            try:
                import requests
                requests.get("http://httpbin.org/status/200", timeout=1)
                return test_func(*args, **kwargs)
            except:
                raise unittest.SkipTest("Network not available")
        return wrapper
    return decorator


class PerformanceTestCase(IsolatedTestCase):
    """Test case for performance testing."""
    
    def assert_performance(self, func, max_time, *args, **kwargs):
        """Assert that function completes within max_time seconds."""
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        self.assertLess(elapsed, max_time, 
                       f"Function took {elapsed:.3f}s, expected < {max_time}s")
        return result
        
    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        return result, elapsed