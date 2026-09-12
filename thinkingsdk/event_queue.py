"""A queue bounded by both report count and serialized payload bytes."""

import json
import threading
from collections import deque

from .safety import capture_suppressed, encode_event, OversizedEvent


class EventQueue:
    def __init__(self, maxsize=10000, drop_strategy='oldest',
                 max_bytes=8 * 1024 * 1024, max_event_bytes=256 * 1024):
        if min(maxsize, max_bytes, max_event_bytes) <= 0:
            raise ValueError('Queue limits must be positive')
        self._queue = deque()
        self._lock = threading.RLock()
        self._maxsize = maxsize
        self._max_bytes = max_bytes
        self._max_event_bytes = min(max_event_bytes, max_bytes)
        self._queued_bytes = 0
        self._drop_strategy = drop_strategy
        self._dropped_count = 0
        self._total_pushed = 0

    def push(self, event):
        if capture_suppressed():
            return False
        try:
            payload = encode_event(event, max_bytes=self._max_event_bytes)
        except OversizedEvent:
            with self._lock:
                self._total_pushed += 1
                self._dropped_count += 1
            return False
        with self._lock:
            self._total_pushed += 1
            if len(payload) > self._max_event_bytes:
                self._dropped_count += 1
                return False
            while (len(self._queue) >= self._maxsize or
                   self._queued_bytes + len(payload) > self._max_bytes):
                self._dropped_count += 1
                if self._drop_strategy != 'oldest':
                    return False
                self._queued_bytes -= len(self._queue.popleft())
            self._queue.append(payload)
            self._queued_bytes += len(payload)
            return True

    def pop(self):
        with self._lock:
            if not self._queue:
                return None
            payload = self._queue.popleft()
            self._queued_bytes -= len(payload)
        return json.loads(payload)

    def pop_batch(self, max_size=100):
        batch = []
        with self._lock:
            for _ in range(min(max_size, len(self._queue))):
                batch.append(self.pop())
        return batch

    def size(self):
        with self._lock:
            return len(self._queue)

    def is_empty(self):
        return self.size() == 0

    def clear(self):
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            self._queued_bytes = 0
            return count

    def get_stats(self):
        with self._lock:
            return {'current_size': len(self._queue), 'max_size': self._maxsize,
                    'queued_bytes': self._queued_bytes, 'max_bytes': self._max_bytes,
                    'total_pushed': self._total_pushed, 'dropped_count': self._dropped_count,
                    'drop_rate': self._dropped_count / max(1, self._total_pushed)}
