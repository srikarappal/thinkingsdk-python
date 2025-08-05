# tests/test_event_queue.py
"""Tests for EventQueue component."""

import unittest
import threading
import time
from thinking_sdk_client.event_queue import EventQueue


class TestEventQueue(unittest.TestCase):
    """Test cases for EventQueue class."""

    def setUp(self):
        """Set up test fixtures."""
        self.queue = EventQueue(maxsize=100)

    def test_basic_push_pop(self):
        """Test basic push and pop operations."""
        event = {"ts": time.time(), "event": "test", "data": "sample"}
        
        # Test push
        result = self.queue.push(event)
        self.assertTrue(result)
        self.assertEqual(self.queue.size(), 1)
        
        # Test pop
        popped = self.queue.pop()
        self.assertEqual(popped, event)
        self.assertEqual(self.queue.size(), 0)
        
        # Test pop from empty queue
        empty_pop = self.queue.pop()
        self.assertIsNone(empty_pop)

    def test_fifo_ordering(self):
        """Test that events are returned in FIFO order."""
        events = [
            {"id": 1, "data": "first"},
            {"id": 2, "data": "second"},
            {"id": 3, "data": "third"}
        ]
        
        # Push events
        for event in events:
            self.queue.push(event)
            
        # Pop events and verify order
        for expected_event in events:
            popped = self.queue.pop()
            self.assertEqual(popped["id"], expected_event["id"])

    def test_drop_strategy_oldest(self):
        """Test oldest drop strategy when queue is full."""
        small_queue = EventQueue(maxsize=3, drop_strategy="oldest")
        
        # Fill queue to capacity
        for i in range(3):
            small_queue.push({"id": i})
            
        self.assertEqual(small_queue.size(), 3)
        
        # Add one more - should drop oldest
        result = small_queue.push({"id": 3})
        self.assertTrue(result)  # Should succeed
        self.assertEqual(small_queue.size(), 3)
        
        # Verify oldest was dropped (id=0 should be gone)
        first_pop = small_queue.pop()
        self.assertEqual(first_pop["id"], 1)  # Should be id=1, not id=0

    def test_drop_strategy_newest(self):
        """Test newest drop strategy when queue is full."""
        small_queue = EventQueue(maxsize=3, drop_strategy="newest")
        
        # Fill queue to capacity
        for i in range(3):
            small_queue.push({"id": i})
            
        # Try to add one more - should be dropped
        result = small_queue.push({"id": 3})
        self.assertFalse(result)  # Should fail
        self.assertEqual(small_queue.size(), 3)
        
        # Verify newest was dropped (original events still there)
        first_pop = small_queue.pop()
        self.assertEqual(first_pop["id"], 0)

    def test_batch_operations(self):
        """Test batch pop functionality."""
        # Add multiple events
        events = [{"id": i} for i in range(10)]
        for event in events:
            self.queue.push(event)
            
        # Test batch pop
        batch = self.queue.pop_batch(max_size=5)
        self.assertEqual(len(batch), 5)
        self.assertEqual(self.queue.size(), 5)
        
        # Verify order
        for i, event in enumerate(batch):
            self.assertEqual(event["id"], i)
            
        # Test batch pop larger than remaining
        remaining_batch = self.queue.pop_batch(max_size=10)
        self.assertEqual(len(remaining_batch), 5)
        self.assertEqual(self.queue.size(), 0)

    def test_thread_safety(self):
        """Test thread safety of queue operations."""
        num_threads = 10
        events_per_thread = 100
        results = []
        
        def producer():
            """Producer thread function."""
            for i in range(events_per_thread):
                event = {"thread": threading.current_thread().name, "id": i}
                self.queue.push(event)
                
        def consumer():
            """Consumer thread function."""
            thread_results = []
            while len(thread_results) < events_per_thread:
                event = self.queue.pop()
                if event:
                    thread_results.append(event)
                else:
                    time.sleep(0.001)  # Brief sleep to avoid busy waiting
            results.extend(thread_results)
        
        # Start producer and consumer threads
        threads = []
        for _ in range(num_threads):
            producer_thread = threading.Thread(target=producer)
            consumer_thread = threading.Thread(target=consumer)
            threads.extend([producer_thread, consumer_thread])
            
        # Start all threads
        for thread in threads:
            thread.start()
            
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
            
        # Verify results
        self.assertEqual(len(results), num_threads * events_per_thread)
        self.assertEqual(self.queue.size(), 0)

    def test_clear_operation(self):
        """Test queue clear functionality."""
        # Add some events
        for i in range(10):
            self.queue.push({"id": i})
            
        self.assertEqual(self.queue.size(), 10)
        
        # Clear queue
        cleared_count = self.queue.clear()
        self.assertEqual(cleared_count, 10)
        self.assertEqual(self.queue.size(), 0)
        self.assertTrue(self.queue.is_empty())

    def test_statistics(self):
        """Test queue statistics functionality."""
        small_queue = EventQueue(maxsize=5, drop_strategy="oldest")
        
        # Initial stats
        stats = small_queue.get_stats()
        self.assertEqual(stats["current_size"], 0)
        self.assertEqual(stats["max_size"], 5)
        self.assertEqual(stats["total_pushed"], 0)
        self.assertEqual(stats["dropped_count"], 0)
        
        # Add events to trigger drops
        for i in range(10):
            small_queue.push({"id": i})
            
        stats = small_queue.get_stats()
        self.assertEqual(stats["current_size"], 5)
        self.assertEqual(stats["total_pushed"], 10)
        self.assertEqual(stats["dropped_count"], 5)
        self.assertEqual(stats["drop_rate"], 0.5)

    def test_empty_queue_operations(self):
        """Test operations on empty queue."""
        empty_queue = EventQueue()
        
        self.assertTrue(empty_queue.is_empty())
        self.assertEqual(empty_queue.size(), 0)
        self.assertIsNone(empty_queue.pop())
        self.assertEqual(len(empty_queue.pop_batch(10)), 0)
        self.assertEqual(empty_queue.clear(), 0)


if __name__ == '__main__':
    unittest.main()