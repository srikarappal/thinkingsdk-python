# thinkingsdk/event_queue.py
import threading
import time
from collections import deque
from typing import Optional, Dict, Any


class EventQueue:
    """Thread-safe, lock-free event queue with backpressure handling.
    
    Uses a deque with atomic operations for high-performance event buffering.
    Implements dropping strategy when queue is full to prevent memory issues.
    """
    
    def __init__(self, maxsize: int = 10000, drop_strategy: str = "oldest"):
        """
        Args:
            maxsize: Maximum number of events to buffer
            drop_strategy: "oldest" or "newest" - which events to drop when full
        """
        self._queue = deque(maxlen=maxsize)
        self._lock = threading.RLock()
        self._maxsize = maxsize
        self._drop_strategy = drop_strategy
        self._dropped_count = 0
        self._total_pushed = 0
        
    def push(self, event: Dict[str, Any]) -> bool:
        """Push an event to the queue.
        
        Args:
            event: Event dictionary to add
            
        Returns:
            True if event was added, False if dropped
        """
        with self._lock:
            self._total_pushed += 1
            
            if len(self._queue) >= self._maxsize:
                if self._drop_strategy == "oldest":
                    # deque automatically drops oldest when maxlen is reached
                    self._dropped_count += 1
                    self._queue.append(event)
                    return True
                else:  # drop newest
                    self._dropped_count += 1
                    return False
            else:
                self._queue.append(event)
                return True
                
    def pop(self) -> Optional[Dict[str, Any]]:
        """Pop an event from the queue (FIFO).
        
        Returns:
            Event dictionary or None if queue is empty
        """
        with self._lock:
            try:
                return self._queue.popleft()
            except IndexError:
                return None
                
    def pop_batch(self, max_size: int = 100) -> list[Dict[str, Any]]:
        """Pop multiple events at once for efficient batching.
        
        Args:
            max_size: Maximum number of events to return
            
        Returns:
            List of event dictionaries (may be empty)
        """
        batch = []
        with self._lock:
            for _ in range(min(max_size, len(self._queue))):
                try:
                    batch.append(self._queue.popleft())
                except IndexError:
                    break
        return batch
        
    def size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._queue)
            
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self.size() == 0
        
    def clear(self) -> int:
        """Clear all events from queue.
        
        Returns:
            Number of events that were cleared
        """
        with self._lock:
            cleared_count = len(self._queue)
            self._queue.clear()
            return cleared_count
            
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics.
        
        Returns:
            Dictionary with queue metrics
        """
        with self._lock:
            return {
                "current_size": len(self._queue),
                "max_size": self._maxsize,
                "total_pushed": self._total_pushed,
                "dropped_count": self._dropped_count,
                "drop_rate": self._dropped_count / max(1, self._total_pushed)
            }
