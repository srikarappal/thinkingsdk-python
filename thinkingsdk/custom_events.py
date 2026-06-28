"""
Custom events and breadcrumbs API for ThinkingSDK.

Allows users to track custom business events and user journeys.
"""

import time
import os
import threading
import inspect
from typing import Any, Dict, Optional, List
from collections import deque
from pathlib import Path


class BreadcrumbTracker:
    """
    Tracks breadcrumbs - a trail of events leading to errors.
    
    Different from stack traces: breadcrumbs show user journey/timeline,
    not code execution path.
    """
    
    def __init__(self, max_breadcrumbs: int = 100):
        """
        Args:
            max_breadcrumbs: Maximum breadcrumbs to keep in memory
        """
        self.max_breadcrumbs = max_breadcrumbs
        self.breadcrumbs = deque(maxlen=max_breadcrumbs)
        self.lock = threading.Lock()
        
    def add_breadcrumb(
        self, 
        message: str,
        category: str = "default",
        level: str = "info",
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Add a breadcrumb to the trail.
        
        Args:
            message: Breadcrumb message
            category: Category (navigation, http, console, user, etc.)
            level: Severity level (debug, info, warning, error)
            data: Additional data
        """
        with self.lock:
            breadcrumb = {
                "timestamp": time.time(),
                "message": message,
                "category": category,
                "level": level
            }
            
            if data:
                breadcrumb["data"] = data
                
            self.breadcrumbs.append(breadcrumb)
    
    def get_breadcrumbs(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent breadcrumbs.
        
        Args:
            count: Number of breadcrumbs to return (default: all)
        """
        with self.lock:
            if count:
                return list(self.breadcrumbs)[-count:]
            return list(self.breadcrumbs)
    
    def clear(self):
        """Clear all breadcrumbs."""
        with self.lock:
            self.breadcrumbs.clear()
    
    def attach_to_event(self, event: Dict[str, Any], count: int = 20):
        """
        Attach recent breadcrumbs to an event.
        
        Args:
            event: Event to attach breadcrumbs to
            count: Number of breadcrumbs to attach
        """
        breadcrumbs = self.get_breadcrumbs(count)
        if breadcrumbs:
            event["breadcrumbs"] = breadcrumbs


class CustomEventTracker:
    """
    Tracks custom business events separate from code execution events.
    """
    
    def __init__(self, queue, breadcrumb_tracker: Optional[BreadcrumbTracker] = None):
        """
        Args:
            queue: Event queue for sending events
            breadcrumb_tracker: Optional breadcrumb tracker
        """
        self.queue = queue
        self.breadcrumb_tracker = breadcrumb_tracker
        
        # Statistics
        self.stats = {
            "custom_events": 0,
            "metrics": 0,
            "breadcrumbs": 0
        }
        
    def track_event(
        self,
        event_name: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = "info",
        add_breadcrumb: bool = True
    ) -> None:
        """
        Track a custom business event.
        
        Args:
            event_name: Name of the event (e.g., "payment_processed")
            data: Event data/metadata
            level: Event level (debug, info, warning, error, critical)
            add_breadcrumb: Whether to also add as breadcrumb
        """
        # Get caller information
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_frame = frame.f_back
            func_name = caller_frame.f_code.co_name
            file_path = caller_frame.f_code.co_filename
            line_no = caller_frame.f_lineno
        else:
            func_name = "unknown"
            file_path = "unknown"
            line_no = 0
        
        # Build custom event
        event = {
            "ts": time.time(),
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
            "event": "custom",
            "func": func_name,
            "file": str(Path(file_path).name),
            "file_path": file_path,
            "line": line_no,
            
            # Custom event specific fields
            "custom_event_name": event_name,
            "custom_level": level,
            "custom_data": data or {}
        }
        
        # Add context if available
        try:
            from .context import Context
            current_context = Context.get_current()
            if current_context:
                event["context"] = current_context
        except ImportError:
            pass
        
        # Queue the event
        self.queue.push(event)
        self.stats["custom_events"] += 1
        
        # Also add as breadcrumb if requested
        if add_breadcrumb and self.breadcrumb_tracker:
            self.breadcrumb_tracker.add_breadcrumb(
                message=event_name,
                category="custom",
                level=level,
                data=data
            )
            self.stats["breadcrumbs"] += 1
    
    def track_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "none",
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Track a numeric metric.
        
        Args:
            metric_name: Name of the metric (e.g., "api_latency")
            value: Numeric value
            unit: Unit of measurement (ms, bytes, percent, etc.)
            tags: Additional tags for categorization
        """
        data = {
            "value": value,
            "unit": unit
        }
        
        if tags:
            data["tags"] = tags
            
        self.track_event(
            event_name=f"metric:{metric_name}",
            data=data,
            level="info",
            add_breadcrumb=False  # Metrics don't need breadcrumbs
        )
        self.stats["metrics"] += 1
    
    def increment_counter(
        self,
        counter_name: str,
        value: int = 1,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric.
        
        Args:
            counter_name: Name of the counter
            value: Increment value (default: 1)
            tags: Additional tags
        """
        self.track_metric(
            metric_name=f"counter:{counter_name}",
            value=value,
            unit="count",
            tags=tags
        )
    
    def track_timing(
        self,
        operation_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Track operation timing.
        
        Args:
            operation_name: Name of the operation
            duration_ms: Duration in milliseconds
            tags: Additional tags
        """
        self.track_metric(
            metric_name=f"timing:{operation_name}",
            value=duration_ms,
            unit="ms",
            tags=tags
        )
    
    def add_breadcrumb(
        self,
        message: str,
        category: str = "default",
        level: str = "info",
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a breadcrumb without creating an event.
        
        Args:
            message: Breadcrumb message
            category: Category
            level: Level
            data: Additional data
        """
        if self.breadcrumb_tracker:
            self.breadcrumb_tracker.add_breadcrumb(
                message=message,
                category=category,
                level=level,
                data=data
            )
            self.stats["breadcrumbs"] += 1
    
    def mark_feature_usage(
        self,
        feature_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track feature usage for product analytics.
        
        Args:
            feature_name: Name of the feature
            metadata: Additional metadata
        """
        self.track_event(
            event_name="feature_usage",
            data={
                "feature": feature_name,
                **(metadata or {})
            },
            level="info"
        )
    
    def mark_user_action(
        self,
        action: str,
        target: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track user actions for UX analytics.
        
        Args:
            action: Action performed (click, submit, navigate, etc.)
            target: Target of the action
            metadata: Additional metadata
        """
        data = {"action": action}
        if target:
            data["target"] = target
        if metadata:
            data.update(metadata)
            
        self.track_event(
            event_name="user_action",
            data=data,
            level="info"
        )
        
        # Also add as breadcrumb for user journey tracking
        if self.breadcrumb_tracker:
            breadcrumb_msg = f"{action} on {target}" if target else action
            self.breadcrumb_tracker.add_breadcrumb(
                message=breadcrumb_msg,
                category="user",
                level="info",
                data=metadata
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get custom event statistics."""
        return self.stats.copy()


# Timer context manager for easy timing
class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, tracker: CustomEventTracker, operation_name: str, tags: Optional[Dict[str, str]] = None):
        self.tracker = tracker
        self.operation_name = operation_name
        self.tags = tags
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            self.tracker.track_timing(
                operation_name=self.operation_name,
                duration_ms=duration_ms,
                tags=self.tags
            )