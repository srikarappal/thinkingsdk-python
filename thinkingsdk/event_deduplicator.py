"""Aggregate repeated events with one bounded sample and an occurrence counter."""

import hashlib
import json
import threading
import time
from collections import OrderedDict

from .safety import encode_event, OversizedEvent


class EventDeduplicator:
    def __init__(self, config=None):
        config = config or {}
        self.window_size_ms = config.get('window_size_ms', 900000)
        self.flush_interval_ms = config.get('flush_interval_ms', 900000)
        self.max_patterns = config.get('max_patterns', 1000)
        self.min_frequency = config.get('min_frequency', 2)
        self.max_bytes = config.get('max_bytes', 2 * 1024 * 1024)
        self.max_sample_bytes = config.get('max_sample_bytes', 64 * 1024)
        if min(self.window_size_ms, self.flush_interval_ms, self.max_patterns,
               self.max_bytes, self.max_sample_bytes) <= 0:
            raise ValueError('Deduplication limits must be positive')
        self.patterns = OrderedDict()
        self.lock = threading.RLock()
        self.queued_bytes = 0
        self.last_flush = time.time()
        self.stats = {'events_processed': 0, 'events_deduplicated': 0,
                      'patterns_created': 0, 'bytes_saved': 0, 'dropped_patterns': 0}

    def _compute_pattern_hash(self, event):
        exception = event.get('exception') or {}
        frames = exception.get('structured_traceback', event.get('call_stack', []))
        signature = [event.get('event'), event.get('func'),
                     event.get('file_path', event.get('file')), event.get('line'),
                     exception.get('type'),
                     [(frame.get('file'), frame.get('func'), frame.get('line'))
                      for frame in frames[:32] if isinstance(frame, dict)]]
        return hashlib.sha256(encode_event(signature)).hexdigest()[:32]

    def process_event(self, event):
        if event.get('event') == 'custom':
            return event
        try:
            payload = encode_event(event, max_bytes=min(self.max_sample_bytes, self.max_bytes))
        except OversizedEvent:
            return event
        if len(payload) > min(self.max_sample_bytes, self.max_bytes):
            return event
        event = json.loads(payload)
        pattern_hash = self._compute_pattern_hash(event)
        now = time.time()
        with self.lock:
            self.stats['events_processed'] += 1
            pattern = self.patterns.get(pattern_hash)
            if pattern is not None:
                pattern['count'] += 1
                pattern['last'] = now
                self.stats['events_deduplicated'] += 1
                self.stats['bytes_saved'] += len(payload)
                if self._ready(pattern, now):
                    return self._flush_pattern(pattern_hash)
                return None
            while (len(self.patterns) >= self.max_patterns or
                   self.queued_bytes + len(payload) > self.max_bytes):
                oldest = next(iter(self.patterns))
                self._remove_pattern(oldest)
                self.stats['dropped_patterns'] += 1
            self.patterns[pattern_hash] = {'sample': payload, 'count': 0,
                                          'first': now, 'last': now}
            self.queued_bytes += len(payload)
            self.stats['patterns_created'] += 1
            # The first event is sent now; only subsequent occurrences enter the count.
            return event

    def _ready(self, pattern, now):
        return now - pattern['first'] >= min(self.window_size_ms, self.flush_interval_ms) / 1000

    def _remove_pattern(self, pattern_hash):
        pattern = self.patterns.pop(pattern_hash)
        self.queued_bytes -= len(pattern['sample'])
        return pattern

    def _flush_pattern(self, pattern_hash):
        pattern = self._remove_pattern(pattern_hash)
        if not pattern['count']:
            return None
        sample = json.loads(pattern['sample'])
        call_stack = sample.get('call_stack') or [{
            'func': sample.get('func'), 'file': sample.get('file_path', sample.get('file')),
            'line': sample.get('line')}]
        return {'type': 'deduplicated_pattern', 'ts': time.time(), 'data': {
            'pattern_hash': pattern_hash, 'call_stack': call_stack,
            'frequency': pattern['count'], 'sample': sample,
            'time_range': {'first': pattern['first'], 'last': pattern['last']}}}

    def flush_ready(self, max_items=None):
        with self.lock:
            result = []
            now = time.time()
            for pattern_hash in list(self.patterns):
                if max_items is not None and len(result) >= max_items:
                    break
                if self._ready(self.patterns[pattern_hash], now):
                    event = self._flush_pattern(pattern_hash)
                    if event:
                        result.append(event)
            return result

    def flush_all(self):
        with self.lock:
            result = []
            for pattern_hash in list(self.patterns):
                event = self._flush_pattern(pattern_hash)
                if event:
                    result.append(event)
            return result

    def get_stats(self):
        with self.lock:
            return dict(self.stats, active_patterns=len(self.patterns),
                        queued_bytes=self.queued_bytes, max_bytes=self.max_bytes,
                        dedup_ratio=self.stats['events_deduplicated'] /
                        max(1, self.stats['events_processed']))
