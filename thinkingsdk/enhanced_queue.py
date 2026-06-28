"""
Enhanced event queue that integrates deduplication and PII scrubbing.
"""

from typing import Dict, Any, List, Optional


class EnhancedEventQueue:
    """
    Wrapper around EventQueue that adds deduplication and PII scrubbing.
    """
    
    def __init__(self, base_queue, deduplicator=None, pii_scrubber=None):
        """
        Args:
            base_queue: The underlying EventQueue
            deduplicator: Optional EventDeduplicator
            pii_scrubber: Optional PIIScrubber
        """
        self.base_queue = base_queue
        self.deduplicator = deduplicator
        self.pii_scrubber = pii_scrubber
        
    def push(self, event: Dict[str, Any]) -> bool:
        """
        Push event through processing pipeline.
        
        1. PII scrubbing
        2. Deduplication
        3. Queue
        """
        # Scrub PII first
        if self.pii_scrubber:
            event = self.pii_scrubber.scrub_event(event)
        
        # Try to deduplicate
        if self.deduplicator:
            processed = self.deduplicator.process_event(event)
            if processed:
                # Event should be sent immediately
                return self.base_queue.push(processed)
            else:
                # Event was deduplicated, will be sent later
                return True
        else:
            # No deduplication, just queue
            return self.base_queue.push(event)
    
    def pop_batch(self, max_items: int) -> List[Dict[str, Any]]:
        """
        Pop batch from queue, including any deduplicated patterns.
        """
        batch = []
        
        # Get regular events
        regular_events = self.base_queue.pop_batch(max_items)
        if regular_events:
            batch.extend(regular_events)
        
        # Get deduplicated patterns if we have room
        if self.deduplicator and len(batch) < max_items:
            dedup_events = self.deduplicator.flush_ready()
            if dedup_events:
                # Add as many deduplicated events as we can
                remaining = max_items - len(batch)
                batch.extend(dedup_events[:remaining])
        
        return batch
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        stats = self.base_queue.get_stats()
        
        if self.deduplicator:
            stats['deduplicator'] = self.deduplicator.get_stats()
            
        if self.pii_scrubber:
            stats['pii_scrubber'] = self.pii_scrubber.get_stats()
            
        return stats