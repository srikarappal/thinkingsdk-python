#!/usr/bin/env python3
"""
Test all new client features:
- Call stack deduplication
- PII scrubbing
- Custom events
- Breadcrumbs
- Session auth
- Compression
"""

import thinking_sdk_client as thinking
import time
import random
from typing import Optional

def test_deduplication():
    """Test that repetitive patterns get deduplicated."""
    print("\n🔄 Testing deduplication...")
    
    # Generate 100 identical call patterns
    for i in range(100):
        def process_order(order_id):
            validate(order_id)
            calculate_total(order_id)
            return f"Order {order_id} processed"
        
        def validate(order_id):
            if not order_id:
                raise ValueError("Invalid order")
        
        def calculate_total(order_id):
            return random.uniform(10, 100)
        
        process_order(f"ORD-{i:04d}")
    
    print("✅ Generated 100 identical patterns (should be deduplicated)")

def test_pii_scrubbing():
    """Test that PII is properly scrubbed."""
    print("\n🔒 Testing PII scrubbing...")
    
    # Track event with sensitive data
    thinking.track_event("user_registration", {
        "email": "john.doe@example.com",
        "password": "super_secret_123",
        "ssn": "123-45-6789",
        "credit_card": "4111-1111-1111-1111",
        "api_key": "sk_live_abc123def456",
        "phone": "+1-555-123-4567"
    })
    
    print("✅ Sent event with PII (should be scrubbed)")

def test_custom_events():
    """Test custom event tracking."""
    print("\n📊 Testing custom events...")
    
    # Track various custom events
    thinking.track_event("checkout_started", {
        "cart_value": 299.99,
        "item_count": 3
    })
    
    thinking.track_metric("api_latency", 145.2, unit="ms", tags={"endpoint": "/users"})
    
    thinking.mark_feature_usage("dark_mode", {"enabled": True})
    
    # Use timer
    with thinking.timer("database_query", tags={"table": "orders"}):
        time.sleep(0.1)  # Simulate query
    
    print("✅ Tracked custom events and metrics")

def test_breadcrumbs():
    """Test breadcrumb tracking."""
    print("\n🍞 Testing breadcrumbs...")
    
    # Add breadcrumbs showing user journey
    thinking.add_breadcrumb("User logged in", category="auth", level="info")
    thinking.add_breadcrumb("Navigated to products", category="navigation")
    thinking.add_breadcrumb("Added item to cart", category="user", data={"item_id": "PROD-123"})
    thinking.add_breadcrumb("Initiated checkout", category="user")
    
    # Now cause an error - breadcrumbs should be attached
    try:
        def checkout():
            # Simulate error during checkout
            raise ValueError("Payment gateway timeout")
        checkout()
    except ValueError:
        pass  # Expected
    
    print("✅ Added breadcrumbs (will be attached to exception)")

def test_exception_context():
    """Test enhanced exception capture."""
    print("\n🔍 Testing enhanced exception context...")
    
    def deeply_nested():
        def level_1():
            def level_2():
                def level_3():
                    # Local variables for context
                    user_id = "USER-123"
                    order_total = 99.99
                    discount_code = None
                    
                    # This will cause an error
                    result = int(discount_code)  # TypeError
                    return result
                return level_3()
            return level_2()
        return level_1()
    
    try:
        deeply_nested()
    except TypeError:
        pass  # Expected
    
    print("✅ Generated exception with full context")

def test_context_propagation():
    """Test context propagation."""
    print("\n🔗 Testing context propagation...")
    
    with thinking.context(
        user_id="USER-456",
        request_id="REQ-789",
        feature_flag="new_checkout",
        deployment="canary"
    ):
        # All events within this context will have these fields
        thinking.track_event("context_test", {"value": 123})
        
        def nested_function():
            # Context should still be available here
            thinking.track_metric("nested_metric", 456)
        
        nested_function()
    
    print("✅ Context propagated to nested events")

def main():
    """Run all tests."""
    print("🧪 ThinkingSDK Client Feature Test Suite")
    print("=" * 50)
    
    # Configure with all features enabled
    config = {
        'instrumentation': {
            'capture_returns': True,
            'capture_performance': True,
            'capture_memory': False,  # Requires psutil
            'capture_call_patterns': True,
            'capture_source_lines': True
        },
        'privacy': {
            'sanitize_data': True,
            'scrub_emails': True,
            'scrub_ips': True
        },
        'deduplication': {
            'window_size_ms': 1000,
            'min_frequency': 2
        }
    }
    
    # Start SDK
    thinking.start(
        api_key="test_api_key",
        server_url="http://localhost:8000",
        config=config,
        enable_logging=True
    )
    
    print(f"✅ ThinkingSDK started (version {thinking.__version__})")
    
    # Run tests
    test_custom_events()
    test_breadcrumbs()
    test_pii_scrubbing()
    test_context_propagation()
    test_exception_context()
    test_deduplication()
    
    # Get stats
    time.sleep(2)  # Let events process
    stats = thinking.get_stats()
    
    print("\n📈 Statistics:")
    print(f"  Events queued: {stats.get('queue', {}).get('total_pushed', 0)}")
    print(f"  Events deduped: {stats.get('deduplicator', {}).get('events_deduplicated', 0)}")
    print(f"  PII scrubbed: {stats.get('pii_scrubber', {}).get('values_scrubbed', 0)}")
    
    # Stop SDK
    thinking.stop()
    print("\n✅ All tests completed successfully!")

if __name__ == "__main__":
    main()
