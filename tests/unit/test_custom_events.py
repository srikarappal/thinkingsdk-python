"""
Tests for custom events and breadcrumbs tracking.
"""

import pytest
import time
import threading
import json
from unittest.mock import Mock, MagicMock, patch
from thinkingsdk.custom_events import BreadcrumbTracker, CustomEventTracker, Timer


class TestBreadcrumbTracker:
    """Test breadcrumb tracking functionality."""
    
    def test_init(self):
        """Test breadcrumb tracker initialization."""
        tracker = BreadcrumbTracker(max_breadcrumbs=50)
        assert tracker.max_breadcrumbs == 50
        assert len(tracker.breadcrumbs) == 0
        
    def test_add_breadcrumb_basic(self):
        """Test adding basic breadcrumb."""
        tracker = BreadcrumbTracker()
        
        tracker.add_breadcrumb(
            message="User clicked button",
            category="user",
            level="info"
        )
        
        breadcrumbs = tracker.get_breadcrumbs()
        assert len(breadcrumbs) == 1
        assert breadcrumbs[0]["message"] == "User clicked button"
        assert breadcrumbs[0]["category"] == "user"
        assert breadcrumbs[0]["level"] == "info"
        assert "timestamp" in breadcrumbs[0]
        
    def test_add_breadcrumb_with_data(self):
        """Test adding breadcrumb with additional data."""
        tracker = BreadcrumbTracker()
        
        data = {"button_id": "submit", "form": "login"}
        tracker.add_breadcrumb(
            message="Form submitted",
            category="user",
            level="info",
            data=data
        )
        
        breadcrumbs = tracker.get_breadcrumbs()
        assert breadcrumbs[0]["data"] == data
        
    def test_max_breadcrumbs_limit(self):
        """Test that breadcrumbs respect max limit."""
        tracker = BreadcrumbTracker(max_breadcrumbs=3)
        
        # Add 5 breadcrumbs
        for i in range(5):
            tracker.add_breadcrumb(f"Breadcrumb {i}")
            
        breadcrumbs = tracker.get_breadcrumbs()
        assert len(breadcrumbs) == 3
        # Should keep the most recent ones
        assert breadcrumbs[0]["message"] == "Breadcrumb 2"
        assert breadcrumbs[1]["message"] == "Breadcrumb 3"
        assert breadcrumbs[2]["message"] == "Breadcrumb 4"
        
    def test_get_breadcrumbs_with_count(self):
        """Test getting specific number of breadcrumbs."""
        tracker = BreadcrumbTracker()
        
        for i in range(10):
            tracker.add_breadcrumb(f"Breadcrumb {i}")
            
        # Get last 3
        recent = tracker.get_breadcrumbs(count=3)
        assert len(recent) == 3
        assert recent[0]["message"] == "Breadcrumb 7"
        assert recent[2]["message"] == "Breadcrumb 9"
        
    def test_clear_breadcrumbs(self):
        """Test clearing all breadcrumbs."""
        tracker = BreadcrumbTracker()
        
        for i in range(5):
            tracker.add_breadcrumb(f"Breadcrumb {i}")
            
        tracker.clear()
        assert len(tracker.get_breadcrumbs()) == 0
        
    def test_attach_to_event(self):
        """Test attaching breadcrumbs to an event."""
        tracker = BreadcrumbTracker()
        
        for i in range(5):
            tracker.add_breadcrumb(f"Breadcrumb {i}")
            
        event = {"type": "error"}
        tracker.attach_to_event(event, count=3)
        
        assert "breadcrumbs" in event
        assert len(event["breadcrumbs"]) == 3
        assert event["breadcrumbs"][0]["message"] == "Breadcrumb 2"
        
    def test_thread_safety(self):
        """Test thread-safe operations."""
        tracker = BreadcrumbTracker(max_breadcrumbs=100)
        
        def add_breadcrumbs(start):
            for i in range(10):
                tracker.add_breadcrumb(f"Thread {start}-{i}")
                
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_breadcrumbs, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        breadcrumbs = tracker.get_breadcrumbs()
        assert len(breadcrumbs) == 50  # 5 threads * 10 breadcrumbs


class TestCustomEventTracker:
    """Test custom event tracking functionality."""
    
    def test_init(self):
        """Test tracker initialization."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        assert tracker.queue == queue
        assert tracker.breadcrumb_tracker == breadcrumb_tracker
        assert tracker.stats["custom_events"] == 0
        assert tracker.stats["metrics"] == 0
        assert tracker.stats["breadcrumbs"] == 0
        
    def test_track_event_basic(self):
        """Test tracking basic custom event."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        tracker.track_event(
            event_name="user_login",
            data={"user_id": "123"},
            level="info"
        )
        
        # Check event was queued
        assert queue.push.called
        event = queue.push.call_args[0][0]
        
        assert event["event"] == "custom"
        assert event["custom_event_name"] == "user_login"
        assert event["custom_level"] == "info"
        assert event["custom_data"] == {"user_id": "123"}
        assert "ts" in event
        assert "pid" in event
        assert "thread" in event
        
        # Check stats
        assert tracker.stats["custom_events"] == 1
        
    def test_track_event_with_breadcrumb(self):
        """Test tracking event that also adds breadcrumb."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        tracker.track_event(
            event_name="button_clicked",
            data={"button": "submit"},
            level="info",
            add_breadcrumb=True
        )
        
        # Check breadcrumb was added
        breadcrumbs = breadcrumb_tracker.get_breadcrumbs()
        assert len(breadcrumbs) == 1
        assert breadcrumbs[0]["message"] == "button_clicked"
        assert breadcrumbs[0]["category"] == "custom"
        assert breadcrumbs[0]["data"] == {"button": "submit"}
        
        assert tracker.stats["custom_events"] == 1
        assert tracker.stats["breadcrumbs"] == 1
        
    def test_track_event_without_breadcrumb(self):
        """Test tracking event without adding breadcrumb."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        tracker.track_event(
            event_name="metric_recorded",
            add_breadcrumb=False
        )
        
        assert len(breadcrumb_tracker.get_breadcrumbs()) == 0
        assert tracker.stats["breadcrumbs"] == 0
        
    def test_track_metric(self):
        """Test tracking metrics."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        tracker.track_metric(
            metric_name="api_latency",
            value=250.5,
            unit="ms",
            tags={"endpoint": "/api/users"}
        )
        
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "metric:api_latency"
        assert event["custom_data"]["value"] == 250.5
        assert event["custom_data"]["unit"] == "ms"
        assert event["custom_data"]["tags"] == {"endpoint": "/api/users"}
        
        assert tracker.stats["metrics"] == 1
        
    def test_increment_counter(self):
        """Test incrementing counter."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        tracker.increment_counter(
            counter_name="requests",
            value=5,
            tags={"service": "auth"}
        )
        
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "metric:counter:requests"
        assert event["custom_data"]["value"] == 5
        assert event["custom_data"]["unit"] == "count"
        assert event["custom_data"]["tags"] == {"service": "auth"}
        
    def test_track_timing(self):
        """Test tracking timing metrics."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        tracker.track_timing(
            operation_name="database_query",
            duration_ms=125.3,
            tags={"query": "SELECT *"}
        )
        
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "metric:timing:database_query"
        assert event["custom_data"]["value"] == 125.3
        assert event["custom_data"]["unit"] == "ms"
        
    def test_add_breadcrumb_only(self):
        """Test adding breadcrumb without event."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        tracker.add_breadcrumb(
            message="Page loaded",
            category="navigation",
            level="info",
            data={"url": "/home"}
        )
        
        # No event should be queued
        assert not queue.push.called
        
        # Breadcrumb should be added
        breadcrumbs = breadcrumb_tracker.get_breadcrumbs()
        assert len(breadcrumbs) == 1
        assert breadcrumbs[0]["message"] == "Page loaded"
        assert tracker.stats["breadcrumbs"] == 1
        
    def test_mark_feature_usage(self):
        """Test tracking feature usage."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        tracker.mark_feature_usage(
            feature_name="dark_mode",
            metadata={"enabled": True}
        )
        
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "feature_usage"
        assert event["custom_data"]["feature"] == "dark_mode"
        assert event["custom_data"]["enabled"] is True
        
    def test_mark_user_action(self):
        """Test tracking user actions."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        tracker.mark_user_action(
            action="click",
            target="submit_button",
            metadata={"form": "checkout"}
        )
        
        # Check event
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "user_action"
        assert event["custom_data"]["action"] == "click"
        assert event["custom_data"]["target"] == "submit_button"
        assert event["custom_data"]["form"] == "checkout"
        
        # Check breadcrumb (mark_user_action creates both an event and a breadcrumb)
        # The event itself is also tracked with add_breadcrumb=True by default
        breadcrumbs = breadcrumb_tracker.get_breadcrumbs()
        assert len(breadcrumbs) == 2  # One from track_event, one explicit
        # Find the user category breadcrumb
        user_breadcrumb = [b for b in breadcrumbs if b["category"] == "user"][0]
        assert user_breadcrumb["message"] == "click on submit_button"
        
    def test_mark_user_action_without_target(self):
        """Test tracking user action without target."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        tracker.mark_user_action(action="logout")
        
        event = queue.push.call_args[0][0]
        assert event["custom_data"]["action"] == "logout"
        assert "target" not in event["custom_data"]
        
        breadcrumbs = breadcrumb_tracker.get_breadcrumbs()
        # Find the user category breadcrumb (there are two breadcrumbs)
        user_breadcrumb = [b for b in breadcrumbs if b["category"] == "user"][0]
        assert user_breadcrumb["message"] == "logout"
        
    def test_get_stats(self):
        """Test getting statistics."""
        queue = Mock()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        # Generate some events
        tracker.track_event("event1")
        tracker.track_metric("metric1", 100)
        tracker.add_breadcrumb("breadcrumb1")
        
        stats = tracker.get_stats()
        assert stats["custom_events"] == 2  # track_event called twice (event1 and metric1)
        assert stats["metrics"] == 1
        assert stats["breadcrumbs"] == 2  # event1 creates a breadcrumb too, plus breadcrumb1
        
        # Ensure it's a copy
        stats["custom_events"] = 999
        assert tracker.stats["custom_events"] == 2
        
    @patch('thinkingsdk.custom_events.inspect.currentframe')
    def test_track_event_caller_info(self, mock_frame):
        """Test that caller information is captured."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        # Mock frame info
        mock_f_back = Mock()
        mock_f_back.f_code.co_name = "test_function"
        mock_f_back.f_code.co_filename = "/path/to/test.py"
        mock_f_back.f_lineno = 42
        
        mock_frame_obj = Mock()
        mock_frame_obj.f_back = mock_f_back
        mock_frame.return_value = mock_frame_obj
        
        tracker.track_event("test_event")
        
        event = queue.push.call_args[0][0]
        assert event["func"] == "test_function"
        assert event["file"] == "test.py"
        assert event["file_path"] == "/path/to/test.py"
        assert event["line"] == 42
        
    @patch('thinkingsdk.custom_events.inspect.currentframe')
    def test_track_event_no_frame(self, mock_frame):
        """Test handling when frame info is not available."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        mock_frame.return_value = None
        
        tracker.track_event("test_event")
        
        event = queue.push.call_args[0][0]
        assert event["func"] == "unknown"
        assert event["file"] == "unknown"
        assert event["file_path"] == "unknown"
        assert event["line"] == 0


class TestTimer:
    """Test Timer context manager."""
    
    def test_timer_basic(self):
        """Test basic timer usage."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        with Timer(tracker, "test_operation"):
            time.sleep(0.01)  # Sleep for 10ms
            
        # Check timing was tracked
        assert queue.push.called
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "metric:timing:test_operation"
        
        # Duration should be at least 10ms
        assert event["custom_data"]["value"] >= 10
        assert event["custom_data"]["unit"] == "ms"
        
    def test_timer_with_tags(self):
        """Test timer with tags."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        tags = {"db": "postgres", "table": "users"}
        with Timer(tracker, "db_query", tags=tags):
            time.sleep(0.001)
            
        event = queue.push.call_args[0][0]
        assert event["custom_data"]["tags"] == tags
        
    def test_timer_exception_handling(self):
        """Test timer tracks time even if exception occurs."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        with pytest.raises(ValueError):
            with Timer(tracker, "failing_operation"):
                time.sleep(0.01)
                raise ValueError("Test error")
                
        # Timer should still track the time
        assert queue.push.called
        event = queue.push.call_args[0][0]
        assert event["custom_event_name"] == "metric:timing:failing_operation"
        assert event["custom_data"]["value"] >= 10
        
    def test_timer_multiple_uses(self):
        """Test using timer multiple times."""
        queue = Mock()
        tracker = CustomEventTracker(queue)
        
        # Use timer twice
        with Timer(tracker, "operation1"):
            time.sleep(0.001)
            
        with Timer(tracker, "operation2"):
            time.sleep(0.001)
            
        # Should have 2 timing events
        assert queue.push.call_count == 2
        
        # Check both operations were tracked
        calls = queue.push.call_args_list
        event1 = calls[0][0][0]
        event2 = calls[1][0][0]
        
        assert event1["custom_event_name"] == "metric:timing:operation1"
        assert event2["custom_event_name"] == "metric:timing:operation2"


class TestIntegration:
    """Integration tests for custom events and breadcrumbs."""
    
    def test_exception_with_breadcrumbs(self):
        """Test that breadcrumbs are attached to exception events."""
        from thinkingsdk.event_queue import EventQueue
        
        queue = EventQueue()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        # Add some breadcrumbs
        tracker.add_breadcrumb("User logged in", category="auth")
        tracker.add_breadcrumb("Navigated to dashboard", category="navigation")
        tracker.add_breadcrumb("Clicked export button", category="user")
        
        # Simulate an exception event
        exception_event = {
            "event": "exception",
            "exception": {
                "type": "ValueError",
                "value": "Invalid data format"
            }
        }
        
        # Attach breadcrumbs
        breadcrumb_tracker.attach_to_event(exception_event)
        
        assert "breadcrumbs" in exception_event
        assert len(exception_event["breadcrumbs"]) == 3
        assert exception_event["breadcrumbs"][0]["message"] == "User logged in"
        assert exception_event["breadcrumbs"][-1]["message"] == "Clicked export button"
        
    def test_full_workflow(self):
        """Test complete workflow with events and breadcrumbs."""
        from thinkingsdk.event_queue import EventQueue
        
        queue = EventQueue()
        breadcrumb_tracker = BreadcrumbTracker(max_breadcrumbs=10)
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        # Simulate user journey
        tracker.mark_user_action("login", metadata={"user_id": "123"})
        tracker.mark_feature_usage("dashboard")
        
        # Track some metrics
        with Timer(tracker, "api_call", tags={"endpoint": "/users"}):
            time.sleep(0.001)
            
        tracker.track_metric("memory_usage", 256.5, unit="MB")
        
        # Add navigation breadcrumb
        tracker.add_breadcrumb("Viewed user profile", category="navigation")
        
        # Increment counter
        tracker.increment_counter("profile_views", tags={"user_id": "123"})
        
        # Check stats
        stats = tracker.get_stats()
        assert stats["custom_events"] >= 2  # user_action, feature_usage
        assert stats["metrics"] >= 3  # timing, metric, counter
        assert stats["breadcrumbs"] >= 2  # user_action adds breadcrumb too
        
        # Check queue has events
        events = []
        while True:
            batch = queue.pop_batch(10)
            if not batch:
                break
            events.extend(batch)
            
        # Verify various event types exist
        event_names = [e.get("custom_event_name", "") for e in events]
        assert "user_action" in event_names
        assert "feature_usage" in event_names
        assert any("timing:" in name for name in event_names)
        assert any("counter:" in name for name in event_names)
        
    def test_thread_safety_integration(self):
        """Test thread-safe operation of custom events."""
        from thinkingsdk.event_queue import EventQueue
        
        queue = EventQueue()
        breadcrumb_tracker = BreadcrumbTracker()
        tracker = CustomEventTracker(queue, breadcrumb_tracker)
        
        def worker(worker_id):
            for i in range(10):
                tracker.track_event(f"worker_{worker_id}_event_{i}")
                tracker.add_breadcrumb(f"Worker {worker_id} step {i}")
                tracker.increment_counter(f"worker_{worker_id}_counter")
                
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # Check all events were tracked
        stats = tracker.get_stats()
        assert stats["custom_events"] == 100  # 5 workers * 10 events + 5 workers * 10 counter events
        assert stats["breadcrumbs"] == 100  # events create breadcrumbs too
        assert stats["metrics"] == 50  # 5 workers * 10 counters