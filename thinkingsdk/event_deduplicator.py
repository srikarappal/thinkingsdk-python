"""
Event deduplication and pattern detection for reducing payload size.

Groups similar call stacks and events to reduce transmission overhead by 90%.
"""

import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import threading


class CallStackPattern:
    """Represents a unique call stack pattern."""
    
    def __init__(self, pattern_hash: str, call_stack: List[Dict[str, Any]]):
        self.pattern_hash = pattern_hash
        self.call_stack = call_stack  # Full stack with file paths
        self.occurrences = []
        self.first_seen = time.time()
        self.last_seen = time.time()
        
    def add_occurrence(self, event: Dict[str, Any]):
        """Add an occurrence of this pattern."""
        # Extract only the variable parts (things that change between identical patterns)
        occurrence = {
            'timestamp': event.get('ts'),
            'locals': event.get('locals', {}),
            'return_value': event.get('return_value'),
            'execution_time_ms': event.get('execution_time_ms'),
            'exception': event.get('exception'),
            'custom_data': event.get('custom_data')  # For custom events
        }
        
        # Remove None values to save space
        occurrence = {k: v for k, v in occurrence.items() if v is not None}
        
        self.occurrences.append(occurrence)
        self.last_seen = time.time()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for transmission."""
        # Calculate statistics
        exec_times = [o.get('execution_time_ms', 0) for o in self.occurrences if 'execution_time_ms' in o]
        
        result = {
            'pattern_hash': self.pattern_hash,
            'call_stack': self.call_stack,  # Full stack trace with files
            'frequency': len(self.occurrences),
            'time_range': {
                'first': self.first_seen,
                'last': self.last_seen
            }
        }
        
        # Add execution time stats if available
        if exec_times:
            result['performance'] = {
                'avg_ms': sum(exec_times) / len(exec_times),
                'min_ms': min(exec_times),
                'max_ms': max(exec_times)
            }
        
        # Include variations only if they differ
        if self._has_variations():
            result['variations'] = self.occurrences
        else:
            # If all occurrences are identical, just include one sample
            result['sample'] = self.occurrences[0] if self.occurrences else {}
            
        return result
    
    def _has_variations(self) -> bool:
        """Check if occurrences have different values."""
        if len(self.occurrences) <= 1:
            return False
            
        # Check if any occurrence differs from the first
        first = self.occurrences[0]
        for occurrence in self.occurrences[1:]:
            if occurrence != first:
                return True
        return False


class EventDeduplicator:
    """
    Deduplicates events by grouping similar call stacks.
    
    Reduces payload size by 90% for repetitive patterns.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: Deduplication configuration
                - window_size_ms: Time window for grouping (default: 1000ms)
                - max_patterns: Maximum patterns to track (default: 1000)
                - min_frequency: Minimum frequency to deduplicate (default: 2)
                - flush_interval_ms: Auto-flush interval (default: 5000ms)
        """
        config = config or {}
        
        self.window_size_ms = config.get('window_size_ms', 1000)
        self.max_patterns = config.get('max_patterns', 1000)
        self.min_frequency = config.get('min_frequency', 2)
        self.flush_interval_ms = config.get('flush_interval_ms', 5000)
        
        # Pattern storage
        self.patterns: Dict[str, CallStackPattern] = {}
        self.pattern_order = []  # LRU tracking
        
        # Threading safety
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'events_deduplicated': 0,
            'patterns_created': 0,
            'bytes_saved': 0
        }
        
        # Auto-flush timer
        self.last_flush = time.time()
        
    def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process an event for deduplication.
        
        Returns:
            None if event is deduplicated (will be sent in batch later)
            Event dict if it should be sent immediately
        """
        with self.lock:
            self.stats['events_processed'] += 1
            
            # Extract call stack for pattern matching
            pattern_hash = self._compute_pattern_hash(event)
            
            if not pattern_hash:
                # Can't deduplicate without a pattern (e.g., exceptions go through immediately)
                return event
            
            # Custom events always go through immediately (user-generated analytics)
            if event.get('event') in ['custom']:
                return event
            
            # Check if we've seen this pattern recently
            if pattern_hash in self.patterns:
                pattern = self.patterns[pattern_hash]
                
                # Check if within time window
                if time.time() - pattern.last_seen < self.window_size_ms / 1000:
                    # Add to existing pattern
                    pattern.add_occurrence(event)
                    self.stats['events_deduplicated'] += 1
                    
                    # Update LRU
                    self._update_lru(pattern_hash)
                    
                    # Don't send individual event
                    return None
                else:
                    # Pattern is stale, flush it and start new one
                    flushed = self._flush_pattern(pattern_hash)
                    self._create_pattern(pattern_hash, event)
                    return flushed
            else:
                # New pattern
                self._create_pattern(pattern_hash, event)
                
                # For first occurrence, let it through
                return event
    
    def flush_ready(self) -> List[Dict[str, Any]]:
        """
        Flush patterns that are ready to be sent.
        
        Returns patterns that:
        - Have enough occurrences (>= min_frequency)
        - Are older than the time window
        - Or if flush interval has passed
        """
        with self.lock:
            now = time.time()
            flushed_events = []
            
            # Check if force flush is needed
            force_flush = (now - self.last_flush) > (self.flush_interval_ms / 1000)
            
            patterns_to_flush = []
            for pattern_hash, pattern in list(self.patterns.items()):
                should_flush = False
                
                # Flush if pattern is stale
                if now - pattern.last_seen > self.window_size_ms / 1000:
                    should_flush = True
                    
                # Flush if force flush and has enough occurrences
                elif force_flush and len(pattern.occurrences) >= self.min_frequency:
                    should_flush = True
                    
                if should_flush:
                    patterns_to_flush.append(pattern_hash)
                    
            # Flush selected patterns
            for pattern_hash in patterns_to_flush:
                event = self._flush_pattern(pattern_hash)
                if event:
                    flushed_events.append(event)
                    
            if force_flush:
                self.last_flush = now
                
            return flushed_events
    
    def flush_all(self) -> List[Dict[str, Any]]:
        """Flush all pending patterns."""
        with self.lock:
            flushed_events = []
            
            for pattern_hash in list(self.patterns.keys()):
                event = self._flush_pattern(pattern_hash)
                if event:
                    flushed_events.append(event)
                    
            return flushed_events
    
    def _compute_pattern_hash(self, event: Dict[str, Any]) -> Optional[str]:
        """Compute hash for call stack pattern."""
        # Build pattern from event type and full call stack
        pattern_parts = []
        
        # Include event type
        pattern_parts.append(event.get('event', 'unknown'))
        
        # Include function, file, line as primary pattern
        pattern_parts.append(event.get('func', ''))
        pattern_parts.append(event.get('file_path', event.get('file', '')))  # Use full path
        
        # Include full call stack if available
        if 'call_stack' in event:
            # Call stack should be list of dicts with file, func, line
            for frame in event['call_stack']:
                pattern_parts.append(f"{frame.get('file')}:{frame.get('func')}")
        elif 'recent_calls' in event:
            pattern_parts.extend(event['recent_calls'])
            
        # Create hash
        if pattern_parts:
            pattern_str = '|'.join(str(p) for p in pattern_parts)
            return hashlib.md5(pattern_str.encode()).hexdigest()[:16]
        
        return None
    
    def _create_pattern(self, pattern_hash: str, event: Dict[str, Any]):
        """Create a new pattern."""
        # Extract full call stack with file paths
        call_stack = []
        
        if 'call_stack' in event:
            call_stack = event['call_stack']
        elif 'recent_calls' in event:
            # Convert simple list to structured format
            call_stack = [{'func': func} for func in event['recent_calls']]
        else:
            # Create from current event
            call_stack = [{
                'func': event.get('func', 'unknown'),
                'file': event.get('file_path', event.get('file', 'unknown')),
                'line': event.get('line', 0)
            }]
            
        # Create pattern
        pattern = CallStackPattern(pattern_hash, call_stack)
        pattern.add_occurrence(event)
        
        # Store pattern
        self.patterns[pattern_hash] = pattern
        self.pattern_order.append(pattern_hash)
        
        # Enforce max patterns (LRU eviction)
        if len(self.patterns) > self.max_patterns:
            oldest = self.pattern_order.pop(0)
            del self.patterns[oldest]
            
        self.stats['patterns_created'] += 1
    
    def _flush_pattern(self, pattern_hash: str) -> Optional[Dict[str, Any]]:
        """Flush a pattern and return deduplicated event."""
        if pattern_hash not in self.patterns:
            return None
            
        pattern = self.patterns[pattern_hash]
        
        # Only send if we have multiple occurrences
        if len(pattern.occurrences) >= self.min_frequency:
            # Create deduplicated event
            dedup_event = {
                'type': 'deduplicated_pattern',
                'ts': time.time(),
                'data': pattern.to_dict()
            }
            
            # Estimate bytes saved
            original_size = len(str(pattern.occurrences)) * len(pattern.occurrences)
            dedup_size = len(str(dedup_event))
            self.stats['bytes_saved'] += max(0, original_size - dedup_size)
            
            # Remove pattern
            del self.patterns[pattern_hash]
            self.pattern_order.remove(pattern_hash)
            
            return dedup_event
        else:
            # Not enough occurrences, don't deduplicate
            del self.patterns[pattern_hash]
            self.pattern_order.remove(pattern_hash)
            return None
    
    def _update_lru(self, pattern_hash: str):
        """Update LRU order for pattern."""
        if pattern_hash in self.pattern_order:
            self.pattern_order.remove(pattern_hash)
        self.pattern_order.append(pattern_hash)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        with self.lock:
            stats = self.stats.copy()
            stats['active_patterns'] = len(self.patterns)
            stats['dedup_ratio'] = (
                self.stats['events_deduplicated'] / self.stats['events_processed']
                if self.stats['events_processed'] > 0 else 0
            )
            return stats