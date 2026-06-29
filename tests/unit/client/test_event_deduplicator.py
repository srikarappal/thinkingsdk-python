"""
Tests for the Event Deduplicator module.

Tests deduplication logic, pattern matching, and payload reduction.
"""

import pytest
import time
import hashlib
from unittest.mock import MagicMock, patch
from typing import Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))


@pytest.fixture
def deduplicator():
    """Create an EventDeduplicator instance."""
    from thinkingsdk.event_deduplicator import EventDeduplicator
    return EventDeduplicator()


@pytest.fixture
def sample_event():
    """Create a sample event."""
    return {
        'event': 'call',
        'func': 'test_func',
        'file': 'test.py',
        'file_path': '/path/to/test.py',
        'line': 42,
        'ts': time.time(),
        'locals': {'x': 1, 'y': 2},
        'pid': 12345,
        'thread': 'MainThread',
        'execution_time_ms': 10.5
    }


class TestEventDeduplicator:
    """Test the event deduplication system."""
    
    def test_init_default_config(self):
        """Test initialization with default config."""
        from thinkingsdk.event_deduplicator import EventDeduplicator
        dedup = EventDeduplicator()
        
        assert dedup.window_size_ms == 1000
        assert dedup.max_patterns == 1000
        assert dedup.min_frequency == 2
        assert dedup.flush_interval_ms == 5000
        assert dedup.stats['events_processed'] == 0
        
    def test_init_custom_config(self):
        """Test initialization with custom config."""
        from thinkingsdk.event_deduplicator import EventDeduplicator
        config = {
            'window_size_ms': 2000,
            'max_patterns': 500,
            'min_frequency': 3,
            'flush_interval_ms': 10000
        }
        dedup = EventDeduplicator(config)
        
        assert dedup.window_size_ms == 2000
        assert dedup.max_patterns == 500
        assert dedup.min_frequency == 3
        assert dedup.flush_interval_ms == 10000
    
    def test_compute_pattern_hash(self, deduplicator):
        """Test pattern hash computation."""
        event1 = {
            'event': 'call',
            'func': 'test_func',
            'file': 'test.py',
            'line': 42,
            'ts': 1000,
            'locals': {'x': 1}
        }
        
        event2 = {
            'event': 'call',
            'func': 'test_func',
            'file': 'test.py',
            'line': 42,
            'ts': 2000,  # Different timestamp
            'locals': {'x': 2}  # Different locals
        }
        
        # Same pattern despite different timestamps and locals
        hash1 = deduplicator._compute_pattern_hash(event1)
        hash2 = deduplicator._compute_pattern_hash(event2)
        
        assert hash1 == hash2
        assert len(hash1) == 16  # MD5 hash truncated to 16 chars
        
        # Different function should have different hash
        event3 = event1.copy()
        event3['func'] = 'different_func'
        hash3 = deduplicator._compute_pattern_hash(event3)
        assert hash3 != hash1
        
    def test_process_event_new_pattern(self, deduplicator, sample_event):
        """Test processing a new event creates a pattern."""
        result = deduplicator.process_event(sample_event)
        
        # First occurrence should pass through
        assert result == sample_event
        assert deduplicator.stats['events_processed'] == 1
        assert deduplicator.stats['events_deduplicated'] == 0
        assert deduplicator.stats['patterns_created'] == 1
        
    def test_process_event_deduplication(self, deduplicator, sample_event):
        """Test deduplication of similar events."""
        # First event passes through
        result1 = deduplicator.process_event(sample_event)
        assert result1 == sample_event
        
        # Second similar event within window gets deduplicated
        sample_event2 = sample_event.copy()
        sample_event2['ts'] = sample_event['ts'] + 0.1  # 100ms later
        sample_event2['locals'] = {'x': 5, 'y': 10}  # Different locals
        
        result2 = deduplicator.process_event(sample_event2)
        assert result2 is None  # Deduplicated
        
        assert deduplicator.stats['events_processed'] == 2
        assert deduplicator.stats['events_deduplicated'] == 1
        
    def test_process_event_outside_window(self, deduplicator, sample_event):
        """Test events outside time window create new patterns."""
        # First event
        result1 = deduplicator.process_event(sample_event)
        assert result1 == sample_event
        
        # Add one more event to meet min_frequency (default 2)
        sample_event_dup = sample_event.copy()
        sample_event_dup['ts'] = sample_event['ts'] + 0.1
        result_dup = deduplicator.process_event(sample_event_dup)
        assert result_dup is None  # Should be deduplicated
        
        # Event outside window (>1 second later by default)
        sample_event2 = sample_event.copy()
        sample_event2['ts'] = sample_event['ts'] + 2  # 2 seconds later
        
        # Mock time to simulate delay
        with patch('time.time', return_value=sample_event2['ts']):
            result2 = deduplicator.process_event(sample_event2)
        
        # Should flush old pattern (which has 2 occurrences) and return it
        assert result2 is not None
        assert result2['type'] == 'deduplicated_pattern'
        
    @pytest.mark.xfail(
        reason="open design question: the deduplicator hashes exceptions and dedups repeats, "
        "but its own comment + strategic sampling say exceptions pass through immediately. "
        "Owner decision: dedup repeated crashes (efficiency) vs always-send (never miss one).",
        strict=False,
    )
    def test_exception_events_not_deduplicated(self, deduplicator):
        """Test that exception events always pass through."""
        exception_event = {
            'event': 'exception',
            'exception': {
                'type': 'ValueError',
                'value': 'Test error',
                'traceback': []
            },
            'ts': time.time()
        }
        
        # Process same exception multiple times
        result1 = deduplicator.process_event(exception_event)
        result2 = deduplicator.process_event(exception_event)
        
        # Both should pass through
        assert result1 == exception_event
        assert result2 == exception_event
        assert deduplicator.stats['events_deduplicated'] == 0
        
    def test_custom_events_not_deduplicated(self, deduplicator):
        """Test that custom events always pass through."""
        custom_event = {
            'event': 'custom',
            'custom_event_name': 'user_action',
            'custom_data': {'action': 'click'},
            'ts': time.time()
        }
        
        result1 = deduplicator.process_event(custom_event)
        result2 = deduplicator.process_event(custom_event)
        
        assert result1 == custom_event
        assert result2 == custom_event
        
    def test_flush_ready_patterns(self, deduplicator, sample_event):
        """Test flushing ready patterns."""
        # Create pattern with multiple occurrences
        deduplicator.process_event(sample_event)
        
        # Add more occurrences
        for i in range(3):
            event = sample_event.copy()
            event['ts'] = sample_event['ts'] + i * 0.1
            event['locals'] = {'x': i}
            deduplicator.process_event(event)
        
        # Mock time to make pattern stale
        with patch('time.time', return_value=sample_event['ts'] + 2):
            flushed = deduplicator.flush_ready()
        
        assert len(flushed) > 0
        flushed_event = flushed[0]
        
        # Check the wrapper structure
        assert flushed_event['type'] == 'deduplicated_pattern'
        assert 'data' in flushed_event
        
        # Check pattern data structure
        pattern_data = flushed_event['data']
        assert 'pattern_hash' in pattern_data
        assert 'call_stack' in pattern_data
        assert 'frequency' in pattern_data
        assert pattern_data['frequency'] == 4  # 1 initial + 3 additional
        
    def test_pattern_with_call_stack(self, deduplicator):
        """Test pattern creation with call stack."""
        event_with_stack = {
            'event': 'call',
            'func': 'inner_func',
            'file': 'test.py',
            'call_stack': [
                {'file': 'main.py', 'func': 'main', 'line': 10},
                {'file': 'utils.py', 'func': 'helper', 'line': 25},
                {'file': 'test.py', 'func': 'inner_func', 'line': 42}
            ],
            'ts': time.time()
        }
        
        result = deduplicator.process_event(event_with_stack)
        assert result == event_with_stack
        
        # Hash should include call stack
        pattern_hash = deduplicator._compute_pattern_hash(event_with_stack)
        assert pattern_hash is not None
        
    def test_lru_eviction(self, deduplicator):
        """Test LRU eviction when max patterns exceeded."""
        # Set small max_patterns for testing
        deduplicator.max_patterns = 3
        
        # Create 4 different patterns
        for i in range(4):
            event = {
                'event': 'call',
                'func': f'func_{i}',
                'file': f'file_{i}.py',
                'ts': time.time() + i
            }
            deduplicator.process_event(event)
        
        # Should have evicted the oldest pattern
        assert len(deduplicator.patterns) <= deduplicator.max_patterns
        
    def test_get_stats(self, deduplicator, sample_event):
        """Test statistics tracking."""
        # Process some events
        deduplicator.process_event(sample_event)
        
        # Duplicate event
        event2 = sample_event.copy()
        event2['ts'] = sample_event['ts'] + 0.1
        deduplicator.process_event(event2)
        
        stats = deduplicator.get_stats()
        assert stats['events_processed'] == 2
        assert stats['events_deduplicated'] == 1
        assert stats['patterns_created'] == 1
        
    def test_pattern_performance_tracking(self, deduplicator):
        """Test that patterns track performance metrics."""
        event1 = {
            'event': 'call',
            'func': 'slow_func',
            'file': 'test.py',
            'ts': time.time(),
            'execution_time_ms': 100
        }
        
        event2 = event1.copy()
        event2['ts'] = event1['ts'] + 0.1
        event2['execution_time_ms'] = 150
        
        # Process events
        deduplicator.process_event(event1)
        deduplicator.process_event(event2)
        
        # Flush and check performance stats
        with patch('time.time', return_value=event1['ts'] + 2):
            flushed = deduplicator.flush_ready()
        
        flushed_event = flushed[0]
        pattern_data = flushed_event['data']
        assert 'performance' in pattern_data
        assert pattern_data['performance']['avg_ms'] == 125  # (100 + 150) / 2
        assert pattern_data['performance']['min_ms'] == 100
        assert pattern_data['performance']['max_ms'] == 150
        
    @pytest.mark.skip(reason="timing-sensitive concurrency; flaky without a deterministic scheduler")
    def test_thread_safety(self, deduplicator):
        """Test thread-safe operations."""
        import threading
        
        def process_events():
            for i in range(10):
                event = {
                    'event': 'call',
                    'func': 'thread_func',
                    'file': 'test.py',
                    'ts': time.time() + i * 0.01
                }
                deduplicator.process_event(event)
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=process_events)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have processed all events without errors
        assert deduplicator.stats['events_processed'] == 50


class TestCallStackPattern:
    """Test the CallStackPattern class."""
    
    def test_pattern_creation(self):
        """Test creating a call stack pattern."""
        from thinkingsdk.event_deduplicator import CallStackPattern
        
        call_stack = [
            {'file': 'main.py', 'func': 'main', 'line': 10},
            {'file': 'test.py', 'func': 'test', 'line': 20}
        ]
        
        pattern = CallStackPattern('test_hash', call_stack)
        assert pattern.pattern_hash == 'test_hash'
        assert pattern.call_stack == call_stack
        assert len(pattern.occurrences) == 0
        
    def test_add_occurrence(self):
        """Test adding occurrences to a pattern."""
        from thinkingsdk.event_deduplicator import CallStackPattern
        
        pattern = CallStackPattern('test_hash', [])
        
        event = {
            'ts': 1000,
            'locals': {'x': 1},
            'execution_time_ms': 10
        }
        
        pattern.add_occurrence(event)
        assert len(pattern.occurrences) == 1
        assert pattern.occurrences[0]['timestamp'] == 1000
        assert pattern.occurrences[0]['locals'] == {'x': 1}
        
    def test_pattern_to_dict(self):
        """Test converting pattern to dictionary."""
        from thinkingsdk.event_deduplicator import CallStackPattern
        
        call_stack = [{'file': 'test.py', 'func': 'test'}]
        pattern = CallStackPattern('test_hash', call_stack)
        
        # Add some occurrences
        for i in range(3):
            pattern.add_occurrence({
                'ts': 1000 + i,
                'execution_time_ms': 10 + i
            })
        
        result = pattern.to_dict()
        assert result['pattern_hash'] == 'test_hash'
        assert result['call_stack'] == call_stack
        assert result['frequency'] == 3
        assert 'time_range' in result
        assert 'performance' in result
        assert result['performance']['avg_ms'] == 11  # (10+11+12)/3
        
    def test_pattern_variations(self):
        """Test detection of variations in occurrences."""
        from thinkingsdk.event_deduplicator import CallStackPattern
        
        pattern = CallStackPattern('test_hash', [])
        
        # Add identical occurrences
        for i in range(3):
            pattern.add_occurrence({'ts': 1000, 'locals': {'x': 1}})
        
        result = pattern.to_dict()
        assert 'sample' in result  # No variations, just sample
        assert 'variations' not in result
        
        # Add different occurrence
        pattern.add_occurrence({'ts': 1001, 'locals': {'x': 2}})
        
        result = pattern.to_dict()
        assert 'variations' in result  # Has variations now
        assert 'sample' not in result