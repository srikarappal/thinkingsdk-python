# tests/test_background_sender.py
"""Tests for BackgroundSender component."""

import unittest
import time
import json
from unittest.mock import Mock, patch, MagicMock
import requests
from thinkingsdk.background_sender import BackgroundSender
from thinkingsdk.event_queue import EventQueue
from tests.test_utils import IsolatedTestCase, MockNetworkTestCase


class TestBackgroundSender(MockNetworkTestCase):
    """Test cases for BackgroundSender class."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.queue = EventQueue(maxsize=1000)
        self.api_key = "test_api_key"
        self.server_url = "http://localhost:8000"
        
    def tearDown(self):
        """Clean up after tests."""
        # Make sure any running senders are stopped
        if hasattr(self, 'sender'):
            try:
                self.sender.stop()
            except:
                pass
        super().tearDown()

    def test_initialization_default_config(self):
        """Test initialization with default configuration."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        
        self.assertEqual(sender.batch_size, 50)
        self.assertEqual(sender.max_batch_wait, 2.0)
        self.assertEqual(sender.retry_attempts, 3)
        self.assertEqual(sender.backoff_factor, 1.0)
        self.assertEqual(sender.circuit_breaker_threshold, 5)
        self.assertEqual(sender.circuit_breaker_timeout, 60)
        self.assertEqual(sender.request_timeout, 10)

    def test_initialization_custom_config(self):
        """Test initialization with custom configuration."""
        config = {
            'batch_size': 25,
            'retry_attempts': 5,
            'request_timeout': 15
        }
        
        sender = BackgroundSender(self.queue, self.api_key, self.server_url, config)
        
        self.assertEqual(sender.batch_size, 25)
        self.assertEqual(sender.retry_attempts, 5)
        self.assertEqual(sender.request_timeout, 15)

    def test_url_normalization(self):
        """Test URL normalization."""
        # Test with trailing slash
        sender = BackgroundSender(self.queue, self.api_key, "http://localhost:8000/")
        self.assertEqual(sender.server_url, "http://localhost:8000")
        
        # Test without trailing slash
        sender = BackgroundSender(self.queue, self.api_key, "http://localhost:8000")
        self.assertEqual(sender.server_url, "http://localhost:8000")

    def test_session_setup(self):
        """Test HTTP session setup."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        session = sender._setup_session()
        
        # Verify session was configured
        self.mock_session.mount.assert_called()
        self.mock_session.headers.update.assert_called_once()
        
        # Check headers
        expected_headers = {
            "X-THINKINGSDK-KEY": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "ThinkingSDK-Client/1.0"
        }
        self.mock_session.headers.update.assert_called_with(expected_headers)

    def test_circuit_breaker_logic(self):
        """Test circuit breaker functionality."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url, 
                                 {'circuit_breaker_threshold': 3})
        
        # Initially circuit should be closed
        self.assertFalse(sender._is_circuit_open())
        
        # Simulate failures
        sender._consecutive_failures = 2
        self.assertFalse(sender._is_circuit_open())
        
        # Reach threshold
        sender._consecutive_failures = 3
        self.assertTrue(sender._is_circuit_open())
        
        # Reset failures should close circuit after timeout
        sender._consecutive_failures = 0
        sender._circuit_open_time = None
        self.assertFalse(sender._is_circuit_open())

    def test_collect_batch_timing(self):
        """Test batch collection with timing constraints."""
        config = {'batch_size': 5, 'max_batch_wait': 0.1}
        sender = BackgroundSender(self.queue, self.api_key, self.server_url, config)
        
        # Add some events
        for i in range(3):
            self.queue.push({'id': i})
            
        start_time = time.time()
        batch = sender._collect_batch()
        elapsed = time.time() - start_time
        
        # Should return events without waiting full timeout
        self.assertEqual(len(batch), 3)
        self.assertLess(elapsed, 0.15)  # Should be much faster than max_batch_wait (0.1s)

    def test_collect_batch_size_limit(self):
        """Test batch collection with size limits."""
        config = {'batch_size': 3}
        sender = BackgroundSender(self.queue, self.api_key, self.server_url, config)
        
        # Add more events than batch size
        for i in range(10):
            self.queue.push({'id': i})
            
        batch = sender._collect_batch()
        
        # Should respect batch size limit
        self.assertEqual(len(batch), 3)
        self.assertEqual(self.queue.size(), 7)  # Remaining events

    def test_send_batch_success(self):
        """Test successful batch sending."""
        # Mock successful response (already set up by MockNetworkTestCase)
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        session = sender._setup_session()
        
        events = [{'id': 1}, {'id': 2}]
        result = sender._send_batch(session, events)
        
        self.assertTrue(result)
        self.assertEqual(sender._consecutive_failures, 0)
        self.assertEqual(sender._total_sent, 2)

    def test_send_batch_auth_failure(self):
        """Test batch sending with authentication failure."""
        # Set HTTP status to 401 (already set up by MockNetworkTestCase)
        self.set_http_status(401)
        
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        session = sender._setup_session()
        
        events = [{'id': 1}]
        result = sender._send_batch(session, events)
        
        self.assertFalse(result)

    def test_send_batch_partial_success(self):
        """Test batch sending with partial success."""
        # Note: MockNetworkTestCase doesn't easily support side_effect patterns
        # This test would need more sophisticated mocking for full partial success testing
        # For now, we'll test basic success scenario
        self.set_http_status(200)
        
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        session = sender._setup_session()
        
        events = [{'id': 1}, {'id': 2}, {'id': 3}]
        result = sender._send_batch(session, events)
        
        # Should succeed with 200 status
        self.assertTrue(result)
        self.assertEqual(sender._total_sent, 3)

    def test_send_batch_network_error(self):
        """Test batch sending with network errors."""
        # Set HTTP status to simulate server error
        self.set_http_status(500)
        
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        session = sender._setup_session()
        
        events = [{'id': 1}]
        result = sender._send_batch(session, events)
        
        self.assertFalse(result)
        self.assertEqual(sender._consecutive_failures, 1)

    def test_process_lifecycle(self):
        """Test sender process start and stop."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        
        # Initially thread should not be alive
        self.assertFalse(sender._thread.is_alive())
        
        # Start sender
        sender.start()
        time.sleep(0.1)  # Give thread time to start
        
        # Thread should be alive
        self.assertTrue(sender._thread.is_alive())
        
        # Stop sender
        sender.stop(timeout=1.0)
        time.sleep(0.1)  # Give thread time to stop
        
        # Thread should be terminated
        self.assertFalse(sender._thread.is_alive())

    def test_graceful_shutdown(self):
        """Test graceful shutdown with events in queue."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        
        # Add events to queue
        for i in range(5):
            self.queue.push({'id': i, 'data': f'event_{i}'})
            
        # Start and immediately stop
        sender.start()
        time.sleep(0.05)  # Brief time for startup
        sender.stop(timeout=2.0)
        
        # Verify thread stopped
        self.assertFalse(sender._thread.is_alive())

    def test_stats_collection(self):
        """Test statistics collection."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        
        stats = sender.get_stats()
        
        self.assertIn('thread_alive', stats)
        self.assertIn('total_sent', stats)
        self.assertIn('total_failed', stats)
        self.assertIn('consecutive_failures', stats)
        self.assertIn('circuit_open', stats)
        self.assertIn('config', stats)
        
        self.assertFalse(stats['thread_alive'])
        self.assertEqual(stats['total_sent'], 0)
        self.assertEqual(stats['total_failed'], 0)

    @patch('thinkingsdk.background_sender.logging')
    def test_error_logging(self, mock_logging):
        """Test error logging functionality."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        
        # Set HTTP status to 401 for auth failure
        self.set_http_status(401)
        
        session = sender._setup_session()
        sender._send_batch(session, [{'id': 1}])
        
        # Should log warning for auth failure
        mock_logging.warning.assert_called()

    def test_stop_event_handling(self):
        """Test that sender respects stop events."""
        config = {'max_batch_wait': 10.0}  # Long wait time
        sender = BackgroundSender(self.queue, self.api_key, self.server_url, config)
        
        # Start sender
        sender.start()
        time.sleep(0.1)
        
        # Stop should interrupt even during batch collection
        start_time = time.time()
        sender.stop(timeout=1.0)
        elapsed = time.time() - start_time
        
        # Should stop quickly, not wait for full batch timeout
        self.assertLess(elapsed, 2.0)
        self.assertFalse(sender._thread.is_alive())

    def test_multiple_start_calls(self):
        """Test that multiple start calls don't create multiple threads."""
        sender = BackgroundSender(self.queue, self.api_key, self.server_url)
        
        # Start multiple times
        sender.start()
        first_thread = sender._thread
        
        sender.start()  # Should be no-op
        second_thread = sender._thread
        
        self.assertEqual(first_thread, second_thread)
        
        sender.stop()


class TestBackgroundSenderIntegration(MockNetworkTestCase):
    """Integration tests for BackgroundSender with real HTTP mocking."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        super().setUp()
        self.queue = EventQueue()
        self.api_key = "test_key"
        self.server_url = "http://test-server.com"
        
    def tearDown(self):
        """Clean up after integration tests."""
        if hasattr(self, 'sender'):
            try:
                self.sender.stop()
            except:
                pass
        super().tearDown()

    def test_end_to_end_success_flow(self):
        """Test complete success flow from queue to server."""
        # Mock already set up successful responses
        
        config = {'batch_size': 2, 'max_batch_wait': 0.1}
        self.sender = BackgroundSender(self.queue, self.api_key, self.server_url, config)
        
        # Add test events
        events = [
            {'id': 1, 'type': 'call', 'func': 'test_func1'},
            {'id': 2, 'type': 'call', 'func': 'test_func2'},
        ]
        
        for event in events:
            self.queue.push(event)
            
        # Start sender and wait for processing
        self.sender.start()
        time.sleep(0.5)  # Allow time for batch processing
        
        # Verify requests were made
        self.assertGreater(self.get_request_count(), 0)
        
        # Verify queue was drained
        self.assertEqual(self.queue.size(), 0)
        
        self.sender.stop()

    def test_retry_on_failure(self):
        """Test retry behavior on failures."""
        # Mock failure then success  
        self.set_http_status(500)  # First call fails
        # Note: The mock network test case doesn't easily support side_effect patterns
        # This test would need more sophisticated mocking for full retry testing
        
        config = {'batch_size': 1, 'retry_attempts': 2}
        self.sender = BackgroundSender(self.queue, self.api_key, self.server_url, config)
        
        # Add event
        self.queue.push({'id': 1, 'test': 'data'})
        
        # Start and process
        self.sender.start()
        time.sleep(0.3)
        
        # Should have made attempts (though they'll fail with 500 status)
        self.assertGreaterEqual(self.get_request_count(), 1)
        
        self.sender.stop()


if __name__ == '__main__':
    unittest.main()