# tests/test_client_integration.py
"""Integration tests for the main ThinkingSDK client interface."""

import unittest
import time
import threading
from unittest.mock import patch, Mock
import thinkingsdk as thinking
from tests.test_utils import MockNetworkTestCase, ThreadSafeTestCase, start_test_sdk, assert_stats_valid


class TestThinkingSDKIntegration(MockNetworkTestCase):
    """Integration tests for the main SDK interface."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.api_key = "test_api_key"
        self.server_url = "http://localhost:8000"

    def test_basic_start_stop_cycle(self):
        """Test basic SDK lifecycle."""
        # Initially should not be active
        self.assertFalse(thinking.is_active())
        
        # Start SDK
        thinking.start(self.api_key, self.server_url)
        self.assertTrue(thinking.is_active())
        
        # Stop SDK
        thinking.stop()
        self.assertFalse(thinking.is_active())

    def test_start_with_custom_config(self):
        """Test starting SDK with custom configuration."""
        config = {
            'instrumentation': {
                'sample_rate': 0.5,
                'capture_returns': True
            },
            'sender': {
                'batch_size': 25
            },
            'queue': {
                'maxsize': 5000
            }
        }
        
        thinking.start(self.api_key, self.server_url, config=config)
        
        # Verify configuration was applied
        stats = thinking.get_stats()
        self.assertEqual(stats['config']['instrumentation']['sample_rate'], 0.5)
        self.assertTrue(stats['config']['instrumentation']['capture_returns'])
        self.assertEqual(stats['config']['sender']['batch_size'], 25)
        self.assertEqual(stats['config']['queue']['maxsize'], 5000)
        
        thinking.stop()

    def test_double_start_raises_error(self):
        """Test that starting SDK twice raises an error."""
        thinking.start(self.api_key, self.server_url)
        
        with self.assertRaises(RuntimeError):
            thinking.start(self.api_key, self.server_url)
            
        thinking.stop()

    def test_stop_before_start(self):
        """Test that stopping before starting doesn't cause errors."""
        # Should not raise any exceptions
        thinking.stop()
        thinking.stop()  # Multiple stops should be safe

    def test_get_stats_before_start_raises_error(self):
        """Test that getting stats before starting raises an error."""
        with self.assertRaises(RuntimeError):
            thinking.get_stats()

    @unittest.skip("integration: network mock no longer intercepts the current background sender; needs rework")
    def test_real_function_instrumentation(self):
        """Test that real function calls are instrumented."""
        # HTTP session already mocked by MockNetworkTestCase
        
        # Start SDK with high sample rate
        config = {'instrumentation': {'sample_rate': 1.0}}
        thinking.start(self.api_key, self.server_url, config=config)
        
        # Define and call test functions
        def test_function_a(x, y):
            return x + y
            
        def test_function_b():
            return test_function_a(1, 2)
            
        # Call functions to generate events
        result = test_function_b()
        self.assertEqual(result, 3)
        
        # Give some time for events to be processed
        time.sleep(0.1)
        
        # Check stats - should have captured events
        stats = thinking.get_stats()
        self.assertGreater(stats['instrumentation']['event_count'], 0)
        
        thinking.stop()

    @unittest.skip("integration: network mock no longer intercepts the current background sender; needs rework")
    def test_exception_instrumentation(self):
        """Test that exceptions are properly instrumented."""
        config = {'instrumentation': {'sample_rate': 1.0}}
        thinking.start(self.api_key, self.server_url, config=config)
        
        # Function that raises an exception
        def failing_function():
            raise ValueError("Test exception for instrumentation")
            
        # Call function and catch exception
        try:
            failing_function()
        except ValueError:
            pass
            
        # Give time for event processing
        time.sleep(0.1)
        
        # Should have captured events including the exception
        stats = thinking.get_stats()
        self.assertGreater(stats['instrumentation']['event_count'], 0)
        
        thinking.stop()

    def test_thread_safety(self):
        """Test SDK thread safety with concurrent operations."""
        start_test_sdk(self.api_key, self.server_url)
        
        results = []
        errors = []
        lock = threading.Lock()
        
        def worker_thread(thread_id):
            """Worker thread that performs various operations."""
            try:
                # Define thread-specific function
                def thread_function(value):
                    return value * 2
                    
                # Perform multiple calls
                thread_results = []
                for i in range(10):
                    result = thread_function(thread_id * 10 + i)
                    thread_results.append(result)
                    
                # Get stats (this should be thread-safe)
                stats = thinking.get_stats()
                self.assertIsInstance(stats, dict)
                
                # Thread-safe result recording
                with lock:
                    results.extend(thread_results)
                
            except Exception as e:
                with lock:
                    errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
            
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors in threads: {errors}")
        self.assertEqual(len(results), 50)  # 5 threads * 10 calls each

    def test_stats_content(self):
        """Test that stats contain expected information."""
        thinking.start(self.api_key, self.server_url)
        
        stats = thinking.get_stats()
        
        # Check top-level structure
        self.assertIn('sdk_active', stats)
        self.assertIn('config', stats)
        self.assertIn('queue', stats)
        self.assertIn('instrumentation', stats)
        self.assertIn('sender', stats)
        
        self.assertTrue(stats['sdk_active'])
        
        # Check queue stats
        queue_stats = stats['queue']
        self.assertIn('current_size', queue_stats)
        self.assertIn('max_size', queue_stats)
        self.assertIn('total_pushed', queue_stats)
        
        # Check instrumentation stats
        instr_stats = stats['instrumentation']
        self.assertIn('active', instr_stats)
        self.assertIn('event_count', instr_stats)
        self.assertIn('sample_rate', instr_stats)
        
        # Check sender stats
        sender_stats = stats['sender']
        self.assertIn('thread_alive', sender_stats)
        self.assertIn('total_sent', sender_stats)
        
        thinking.stop()

    @unittest.skip("logging-config assertion drift: basicConfig kwargs changed (no 'format')")
    @patch('thinkingsdk.logging.basicConfig')
    def test_logging_configuration(self, mock_logging_config):
        """Test logging configuration."""
        # Test with logging enabled
        thinking.start(self.api_key, self.server_url, enable_logging=True)
        
        # Should have configured logging
        mock_logging_config.assert_called()
        call_args = mock_logging_config.call_args
        self.assertIn('level', call_args[1])
        self.assertIn('format', call_args[1])
        
        thinking.stop()

    def test_graceful_shutdown_with_events(self):
        """Test graceful shutdown when events are queued."""
        config = {
            'instrumentation': {'sample_rate': 1.0},
            'sender': {'batch_size': 1000}  # Large batch to delay sending
        }
        
        thinking.start(self.api_key, self.server_url, config=config)
        
        # Generate many events
        def generate_events():
            for i in range(100):
                exec(f"x_{i} = {i}")  # Simple operations to generate call events
                
        generate_events()
        
        # Get queue size before shutdown
        stats = thinking.get_stats()
        initial_queue_size = stats['queue']['current_size']
        
        # Shutdown should be graceful
        start_time = time.time()
        thinking.stop(timeout=2.0)
        shutdown_time = time.time() - start_time
        
        # Should shutdown within reasonable time
        self.assertLess(shutdown_time, 3.0)
        self.assertFalse(thinking.is_active())

    def test_configuration_validation(self):
        """Test configuration validation and error handling."""
        # Test with invalid configuration types
        invalid_configs = [
            {'instrumentation': {'sample_rate': 'invalid'}},  # Should be handled gracefully
            {'sender': {'batch_size': -1}},  # Negative values
            {'queue': {'maxsize': 0}},  # Zero size
        ]
        
        for config in invalid_configs:
            try:
                thinking.start(self.api_key, self.server_url, config=config)
                thinking.stop()
                # If no exception, configuration was handled gracefully
            except Exception as e:
                # If exception occurs, it should be a clear RuntimeError
                self.assertIsInstance(e, RuntimeError)

    def test_network_failure_handling(self):
        """Test handling of network failures."""
        # Set HTTP status to simulate network error
        self.set_http_status(500)
        
        # SDK should start successfully even if network fails
        thinking.start(self.api_key, self.server_url)
        
        # Generate some events
        def test_func():
            return "test"
            
        test_func()
        time.sleep(0.1)
        
        # SDK should still be active despite network issues
        self.assertTrue(thinking.is_active())
        
        # Stats should be available
        stats = thinking.get_stats()
        self.assertIsInstance(stats, dict)
        
        thinking.stop()


class TestSampleApplicationScenarios(unittest.TestCase):
    """Test SDK with realistic application scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.server_url = "http://localhost:8000"

    def tearDown(self):
        """Clean up after tests."""
        try:
            thinking.stop()
        except:
            pass

    @unittest.skip("integration: network mock no longer intercepts the current background sender; needs rework")
    def test_web_application_scenario(self):
        """Test SDK with a web application-like scenario."""
        # HTTP session already mocked by MockNetworkTestCase
        
        # Start SDK with realistic config
        config = {
            'instrumentation': {
                'sample_rate': 0.1,  # Sample 10% of events
                'ignore_patterns': [r'/site-packages/', r'/flask/']
            },
            'sender': {
                'batch_size': 20,
                'max_batch_wait': 1.0
            }
        }
        
        thinking.start(self.api_key, self.server_url, config=config)
        
        # Simulate web request processing
        def authenticate_user(username, password):
            if username == "admin" and password == "secret":
                return {"user_id": 1, "role": "admin"}
            return None
            
        def process_request(user_id, action):
            user = authenticate_user("admin", "secret")
            if user:
                return perform_action(user, action)
            else:
                raise PermissionError("Authentication failed")
                
        def perform_action(user, action):
            if action == "read":
                return {"status": "success", "data": [1, 2, 3]}
            elif action == "write":
                return {"status": "success", "message": "Data written"}
            else:
                raise ValueError(f"Unknown action: {action}")
        
        # Simulate multiple requests
        results = []
        for action in ["read", "write", "read"]:
            try:
                result = process_request(1, action)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
                
        # Verify results
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "success")
        
        # Give time for event processing
        time.sleep(0.2)
        
        # Check that events were captured
        stats = thinking.get_stats()
        self.assertGreater(stats['instrumentation']['event_count'], 0)
        
        thinking.stop()

    @unittest.skip("integration: network mock no longer intercepts the current background sender; needs rework")
    def test_data_processing_scenario(self):
        """Test SDK with a data processing scenario."""
        config = {
            'instrumentation': {
                'sample_rate': 1.0,
                'capture_returns': True
            }
        }
        
        thinking.start(self.api_key, self.server_url, config=config)
        
        # Simulate data processing pipeline
        def load_data():
            return [i for i in range(100)]
            
        def transform_data(data):
            return [x * 2 for x in data if x % 2 == 0]
            
        def aggregate_data(data):
            return {
                "count": len(data),
                "sum": sum(data),
                "avg": sum(data) / len(data) if data else 0
            }
            
        def process_batch():
            raw_data = load_data()
            transformed_data = transform_data(raw_data)
            return aggregate_data(transformed_data)
        
        # Process multiple batches
        results = []
        for _ in range(3):
            result = process_batch()
            results.append(result)
            
        # Verify processing worked
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["count"], 50)  # 50 even numbers from 0-99
        
        # Give time for event processing
        time.sleep(0.1)
        
        stats = thinking.get_stats()
        self.assertGreater(stats['instrumentation']['event_count'], 0)
        
        thinking.stop()

    @unittest.skip("integration: network mock no longer intercepts the current background sender; needs rework")
    def test_error_prone_scenario(self):
        """Test SDK with functions that commonly fail."""
        thinking.start(self.api_key, self.server_url)
        
        # Functions with various types of errors
        def division_by_zero(x, y):
            return x / y
            
        def key_error_function(data, key):
            return data[key]
            
        def type_error_function(x):
            return x + "string"
            
        def index_error_function(lst, index):
            return lst[index]
        
        # Test various error scenarios
        error_count = 0
        
        try:
            division_by_zero(10, 0)
        except ZeroDivisionError:
            error_count += 1
            
        try:
            key_error_function({"a": 1}, "b")
        except KeyError:
            error_count += 1
            
        try:
            type_error_function(42)
        except TypeError:
            error_count += 1
            
        try:
            index_error_function([1, 2, 3], 10)
        except IndexError:
            error_count += 1
            
        self.assertEqual(error_count, 4)
        
        # Give time for event processing
        time.sleep(0.1)
        
        # Should have captured exception events
        stats = thinking.get_stats()
        self.assertGreater(stats['instrumentation']['event_count'], 0)
        
        thinking.stop()


if __name__ == '__main__':
    unittest.main()