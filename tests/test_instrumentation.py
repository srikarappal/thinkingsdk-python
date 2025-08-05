# tests/test_instrumentation.py
"""Tests for RuntimeInstrumentation component."""

import unittest
import sys
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from types import FrameType
from thinking_sdk_client.instrumentation import RuntimeInstrumentation
from thinking_sdk_client.event_queue import EventQueue


class TestRuntimeInstrumentation(unittest.TestCase):
    """Test cases for RuntimeInstrumentation class."""

    def setUp(self):
        """Set up test fixtures."""
        self.queue = EventQueue(maxsize=1000)
        self.instrumentation = RuntimeInstrumentation(self.queue)

    def tearDown(self):
        """Clean up after tests."""
        self.instrumentation.cleanup_hooks()

    def test_initialization_default_config(self):
        """Test initialization with default configuration."""
        instr = RuntimeInstrumentation(self.queue)
        
        self.assertEqual(instr.max_locals, 5)
        self.assertEqual(instr.max_local_length, 120)
        self.assertFalse(instr.capture_returns)
        self.assertEqual(instr.sample_rate, 1.0)
        self.assertFalse(instr._active)

    def test_initialization_custom_config(self):
        """Test initialization with custom configuration."""
        config = {
            'max_locals': 10,
            'max_local_length': 200,
            'capture_returns': True,
            'sample_rate': 0.5,
            'ignore_patterns': [r'/test/'],
            'ignore_functions': ['test_func']
        }
        
        instr = RuntimeInstrumentation(self.queue, config)
        
        self.assertEqual(instr.max_locals, 10)
        self.assertEqual(instr.max_local_length, 200)
        self.assertTrue(instr.capture_returns)
        self.assertEqual(instr.sample_rate, 0.5)
        self.assertIn('test_func', instr.ignore_functions)

    def test_hook_setup_and_cleanup(self):
        """Test setting up and cleaning up hooks."""
        original_trace = sys.gettrace()
        original_excepthook = threading.excepthook
        
        # Setup hooks
        self.instrumentation.setup_hooks()
        self.assertTrue(self.instrumentation._active)
        
        # Verify hooks are changed
        self.assertNotEqual(sys.gettrace(), original_trace)
        self.assertNotEqual(threading.excepthook, original_excepthook)
        
        # Cleanup hooks
        self.instrumentation.cleanup_hooks()
        self.assertFalse(self.instrumentation._active)
        
        # Verify hooks are restored
        self.assertEqual(sys.gettrace(), original_trace)
        self.assertEqual(threading.excepthook, original_excepthook)

    def test_should_ignore_frame(self):
        """Test frame filtering logic."""
        # Create mock frame
        mock_frame = Mock()
        mock_frame.f_code.co_filename = '/usr/lib/python3.9/site-packages/requests/api.py'
        mock_frame.f_code.co_name = 'get'
        
        # Should ignore site-packages
        self.assertTrue(self.instrumentation._should_ignore_frame(mock_frame))
        
        # Test function name filtering
        mock_frame.f_code.co_filename = '/app/mycode.py'
        mock_frame.f_code.co_name = '__init__'
        
        self.assertTrue(self.instrumentation._should_ignore_frame(mock_frame))
        
        # Should not ignore regular user code
        mock_frame.f_code.co_name = 'my_function'
        self.assertFalse(self.instrumentation._should_ignore_frame(mock_frame))

    def test_safe_repr(self):
        """Test safe representation of values."""
        # Test normal values
        self.assertEqual(self.instrumentation._safe_repr(42), '42')
        self.assertEqual(self.instrumentation._safe_repr('hello'), "'hello'")
        
        # Test length limiting
        long_string = 'x' * 200
        result = self.instrumentation._safe_repr(long_string, max_length=50)
        self.assertEqual(len(result), 50)
        self.assertTrue(result.endswith('...'))
        
        # Test problematic objects
        class ProblematicClass:
            def __repr__(self):
                raise Exception("Repr failed")
                
        obj = ProblematicClass()
        result = self.instrumentation._safe_repr(obj)
        self.assertIn('ProblematicClass', result)
        self.assertIn('repr failed', result)

    def test_capture_locals(self):
        """Test local variable capture."""
        # Create mock frame with locals
        mock_frame = Mock()
        test_locals = {
            'var1': 'value1',
            'var2': 42,
            '_private': 'should_be_ignored',
            'var3': 'value3'
        }
        mock_frame.f_locals = test_locals
        
        captured = self.instrumentation._capture_locals(mock_frame)
        
        # Should capture non-private variables
        self.assertIn('var1', captured)
        self.assertIn('var2', captured)
        self.assertNotIn('_private', captured)
        
        # Should limit number of variables
        self.instrumentation.max_locals = 2
        captured = self.instrumentation._capture_locals(mock_frame)
        self.assertEqual(len(captured), 2)

    def test_sampling_logic(self):
        """Test event sampling logic."""
        # Test 100% sampling
        instr = RuntimeInstrumentation(self.queue, {'sample_rate': 1.0})
        for _ in range(10):
            self.assertTrue(instr._should_sample())
            
        # Test 0% sampling
        instr = RuntimeInstrumentation(self.queue, {'sample_rate': 0.0})
        for _ in range(10):
            self.assertFalse(instr._should_sample())
            
        # Test 50% sampling (should have some true and some false)
        instr = RuntimeInstrumentation(self.queue, {'sample_rate': 0.5})
        results = [instr._should_sample() for _ in range(100)]
        true_count = sum(results)
        # Should be roughly 50% (allowing for some variance)
        self.assertGreater(true_count, 30)
        self.assertLess(true_count, 70)

    def test_trace_call_event(self):
        """Test tracing of call events."""
        # Don't setup hooks, just test the trace function directly
        initial_size = self.queue.size()
        
        # Create mock frame for call event
        mock_frame = Mock()
        mock_frame.f_code.co_name = 'test_function'
        mock_frame.f_code.co_filename = '/app/test.py'
        mock_frame.f_lineno = 42
        mock_frame.f_locals = {'arg1': 'value1', 'arg2': 123}
        
        # Set instrumentation as active manually
        self.instrumentation._active = True
        
        # Call trace function directly
        result = self.instrumentation._trace_calls(mock_frame, 'call', None)
        
        # Should return the trace function
        self.assertEqual(result, self.instrumentation._trace_calls)
        
        # Should have queued exactly one new event
        self.assertEqual(self.queue.size(), initial_size + 1)
        
        # Find our test event (skip any existing events)
        events = []
        while self.queue.size() > initial_size:
            event = self.queue.pop()
            if event and event.get('func') == 'test_function':
                events.append(event)
                break
                
        self.assertEqual(len(events), 1)
        event = events[0]
        
        # Check event content
        self.assertEqual(event['event'], 'call')
        self.assertEqual(event['func'], 'test_function')
        self.assertEqual(event['file'], 'test.py')
        self.assertEqual(event['line'], 42)
        self.assertIn('locals', event)
        self.assertIn('ts', event)
        self.assertIn('pid', event)
        self.assertIn('thread', event)

    def test_trace_exception_event(self):
        """Test tracing of exception events."""
        initial_size = self.queue.size()
        
        # Create mock frame and exception
        mock_frame = Mock()
        mock_frame.f_code.co_name = 'test_function'
        mock_frame.f_code.co_filename = '/app/test.py'
        mock_frame.f_lineno = 42
        
        # Create a real exception for testing
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            exc_info = (type(e), e, e.__traceback__)
            
        # Set instrumentation as active manually
        self.instrumentation._active = True
            
        # Call trace function directly
        self.instrumentation._trace_calls(mock_frame, 'exception', exc_info)
        
        # Should have queued exactly one new event
        self.assertEqual(self.queue.size(), initial_size + 1)
        
        # Get the event we just added
        event = None
        for _ in range(self.queue.size()):
            candidate = self.queue.pop()
            if candidate and candidate.get('event') == 'exception' and candidate.get('func') == 'test_function':
                event = candidate
                break
                
        self.assertIsNotNone(event, "Exception event not found")
        self.assertEqual(event['event'], 'exception')
        self.assertIn('exception', event)
        self.assertEqual(event['exception']['type'], 'ValueError')
        self.assertIn('Test exception', event['exception']['msg'])
        self.assertIsInstance(event['exception']['traceback'], list)

    def test_thread_exception_handler(self):
        """Test thread exception handling."""
        initial_size = self.queue.size()
        
        # Set instrumentation as active manually
        self.instrumentation._active = True
        
        # Create mock thread exception args
        mock_args = Mock()
        mock_args.thread.name = 'TestThread'
        mock_args.exc_type = ValueError
        mock_args.exc_value = ValueError("Thread exception")
        mock_args.exc_traceback = None
        
        # Call exception handler directly
        self.instrumentation._thread_exception_handler(mock_args)
        
        # Should have queued exactly one new event
        self.assertEqual(self.queue.size(), initial_size + 1)
        
        # Get the event we just added
        event = None
        for _ in range(self.queue.size()):
            candidate = self.queue.pop()
            if candidate and candidate.get('event') == 'thread_exception':
                event = candidate
                break
                
        self.assertIsNotNone(event, "Thread exception event not found")
        self.assertEqual(event['event'], 'thread_exception')
        self.assertEqual(event['thread'], 'TestThread')
        self.assertIn('exception', event)

    def test_ignored_events_not_queued(self):
        """Test that ignored events are not queued."""
        self.instrumentation.setup_hooks()
        
        # Create frame that should be ignored
        mock_frame = Mock()
        mock_frame.f_code.co_name = '__init__'  # Should be ignored
        mock_frame.f_code.co_filename = '/app/test.py'
        mock_frame.f_lineno = 42
        
        initial_size = self.queue.size()
        self.instrumentation._trace_calls(mock_frame, 'call', None)
        
        # Queue size should not change
        self.assertEqual(self.queue.size(), initial_size)

    def test_inactive_instrumentation(self):
        """Test that inactive instrumentation doesn't process events."""
        # Don't call setup_hooks(), so instrumentation is inactive
        mock_frame = Mock()
        mock_frame.f_code.co_name = 'test_function'
        mock_frame.f_code.co_filename = '/app/test.py'
        mock_frame.f_lineno = 42
        
        result = self.instrumentation._trace_calls(mock_frame, 'call', None)
        
        # Should return None when inactive
        self.assertIsNone(result)
        self.assertEqual(self.queue.size(), 0)

    def test_return_event_capture(self):
        """Test capturing return events when enabled."""
        config = {'capture_returns': True}
        instr = RuntimeInstrumentation(self.queue, config)
        
        initial_size = self.queue.size()
        
        # Set instrumentation as active manually
        instr._active = True
        
        mock_frame = Mock()
        mock_frame.f_code.co_name = 'test_function'
        mock_frame.f_code.co_filename = '/app/test.py'
        mock_frame.f_lineno = 42
        
        return_value = {'result': 'success'}
        instr._trace_calls(mock_frame, 'return', return_value)
        
        # Should have queued exactly one new event
        self.assertEqual(self.queue.size(), initial_size + 1)
        
        # Get the event we just added
        event = None
        for _ in range(self.queue.size()):
            candidate = self.queue.pop()
            if candidate and candidate.get('event') == 'return' and candidate.get('func') == 'test_function':
                event = candidate
                break
                
        self.assertIsNotNone(event, "Return event not found")
        self.assertEqual(event['event'], 'return')
        self.assertIn('return_value', event)

    def test_stats_collection(self):
        """Test statistics collection."""
        stats = self.instrumentation.get_stats()
        
        self.assertIn('active', stats)
        self.assertIn('event_count', stats)
        self.assertIn('sample_rate', stats)
        self.assertIn('config', stats)
        
        self.assertFalse(stats['active'])
        self.assertEqual(stats['event_count'], 0)

    def test_real_function_tracing(self):
        """Test tracing real function calls."""
        self.instrumentation = RuntimeInstrumentation(self.queue, {'sample_rate': 1.0})
        self.instrumentation.setup_hooks()
        
        def test_function(x, y):
            return x + y
        
        # Call function - should generate events
        result = test_function(1, 2)
        
        # Give some time for events to be processed
        time.sleep(0.01)
        
        # Should have at least one event
        self.assertGreater(self.queue.size(), 0)
        
        # Find call event
        events = []
        while not self.queue.is_empty():
            event = self.queue.pop()
            if event:
                events.append(event)
                
        call_events = [e for e in events if e['event'] == 'call' and e['func'] == 'test_function']
        self.assertGreater(len(call_events), 0)
        
        call_event = call_events[0]
        self.assertEqual(call_event['func'], 'test_function')
        self.assertIn('locals', call_event)


if __name__ == '__main__':
    unittest.main()