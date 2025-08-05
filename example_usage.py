#!/usr/bin/env python3
"""Example usage of the ThinkingSDK client."""

import time
import thinking_sdk_client as thinking


def demo_basic_usage():
    """Demonstrate basic SDK usage."""
    print("=== ThinkingSDK Basic Usage Demo ===\n")
    
    # Start the SDK
    print("1. Starting ThinkingSDK...")
    thinking.start(
        api_key="demo_key_12345", 
        server_url="http://localhost:8001",
        enable_logging=True
    )
    print("   ✓ SDK started successfully")
    
    # Check if SDK is active
    print(f"   ✓ SDK active: {thinking.is_active()}")
    
    # Get initial stats
    print(f"   ✓ Initial stats: {thinking.get_stats()['instrumentation']['event_count']} events captured")
    
    print("\n2. Executing sample functions...")
    
    # Define some sample functions that will be instrumented
    def calculate_fibonacci(n):
        """Calculate fibonacci number (will generate call/return events)."""
        if n <= 1:
            return n
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
    
    def process_data(data_list):
        """Process a list of data (will generate call/return events)."""
        results = []
        for item in data_list:
            processed = item * 2 + 1
            results.append(processed)
        return results
    
    def function_with_error():
        """Function that will raise an exception."""
        raise ValueError("This is a demo exception for testing")
    
    # Execute functions to generate events
    print("   • Calculating fibonacci(5)...")
    fib_result = calculate_fibonacci(5)
    print(f"     Result: {fib_result}")
    
    print("   • Processing data list...")
    data = [1, 2, 3, 4, 5]
    processed = process_data(data)
    print(f"     Input: {data}")
    print(f"     Output: {processed}")
    
    print("   • Testing exception handling...")
    try:
        function_with_error()
    except ValueError as e:
        print(f"     Caught exception: {e}")
    
    # Wait a moment for events to be processed
    print("\n3. Waiting for event processing...")
    time.sleep(0.5)
    
    # Get final stats
    print("\n4. Final statistics:")
    stats = thinking.get_stats()
    print(f"   • Events captured: {stats['instrumentation']['event_count']}")
    print(f"   • Queue size: {stats['queue']['current_size']}")
    print(f"   • Queue stats: pushed={stats['queue']['total_pushed']}, dropped={stats['queue']['dropped_count']}")
    print(f"   • Sender thread alive: {stats['sender']['thread_alive']}")
    
    # Stop the SDK
    print("\n5. Stopping ThinkingSDK...")
    thinking.stop()
    print("   ✓ SDK stopped successfully")
    print(f"   ✓ SDK active: {thinking.is_active()}")


def demo_advanced_configuration():
    """Demonstrate advanced configuration options."""
    print("\n\n=== ThinkingSDK Advanced Configuration Demo ===\n")
    
    # Custom configuration
    config = {
        'instrumentation': {
            'sample_rate': 0.8,  # Sample 80% of events
            'capture_returns': True,  # Capture function return values
            'max_locals': 3,  # Limit local variables captured
            'ignore_functions': ['helper_function']  # Ignore specific functions
        },
        'sender': {
            'batch_size': 10,  # Send events in batches of 10
            'max_batch_wait': 1.0,  # Max 1 second wait for batching
            'retry_attempts': 2  # Retry failed requests twice
        },
        'queue': {
            'maxsize': 500,  # Smaller queue size
            'drop_strategy': 'newest'  # Drop newest events when full
        }
    }
    
    print("1. Starting SDK with custom configuration...")
    thinking.start(
        api_key="demo_key_advanced", 
        server_url="http://localhost:8001",
        config=config
    )
    
    # Show configuration
    stats = thinking.get_stats()
    print("   ✓ Configuration applied:")
    print(f"     - Sample rate: {stats['config']['instrumentation']['sample_rate']}")
    print(f"     - Capture returns: {stats['config']['instrumentation']['capture_returns']}")
    print(f"     - Batch size: {stats['config']['sender']['batch_size']}")
    print(f"     - Queue max size: {stats['config']['queue']['maxsize']}")
    
    print("\n2. Testing with configured behavior...")
    
    def main_function(x, y):
        """Main function that calls helper."""
        local_var = "main_variable"
        result = helper_function(x) + helper_function(y)
        return result
    
    def helper_function(value):
        """Helper function that should be ignored."""
        return value * 2
    
    # Execute functions
    result = main_function(10, 20)
    print(f"   • Function result: {result}")
    
    # Wait and show stats
    time.sleep(0.3)
    final_stats = thinking.get_stats()
    print(f"\n3. Events captured: {final_stats['instrumentation']['event_count']}")
    
    thinking.stop()
    print("   ✓ Advanced demo completed")


def demo_error_scenarios():
    """Demonstrate error handling scenarios."""
    print("\n\n=== ThinkingSDK Error Handling Demo ===\n")
    
    print("1. Testing various error conditions...")
    
    thinking.start("demo_key_errors", "http://localhost:8001")
    
    # Different types of errors
    def division_error():
        return 10 / 0
    
    def key_error():
        d = {"a": 1, "b": 2}
        return d["nonexistent_key"]
    
    def type_error():
        return "string" + 42
    
    def nested_error():
        def inner_function():
            raise RuntimeError("Inner function error")
        inner_function()
    
    errors_caught = 0
    
    # Test division by zero
    try:
        division_error()
    except ZeroDivisionError:
        errors_caught += 1
        print("   ✓ Division by zero handled")
    
    # Test key error
    try:
        key_error()
    except KeyError:
        errors_caught += 1
        print("   ✓ Key error handled")
    
    # Test type error
    try:
        type_error()
    except TypeError:
        errors_caught += 1
        print("   ✓ Type error handled")
    
    # Test nested error
    try:
        nested_error()
    except RuntimeError:
        errors_caught += 1
        print("   ✓ Nested error handled")
    
    time.sleep(0.2)
    
    stats = thinking.get_stats()
    print(f"\n2. Results:")
    print(f"   • Errors processed: {errors_caught}")
    print(f"   • Total events captured: {stats['instrumentation']['event_count']}")
    
    thinking.stop()
    print("   ✓ Error handling demo completed")


if __name__ == "__main__":
    try:
        demo_basic_usage()
        import pdb; pdb.set_trace()
        demo_advanced_configuration()
        demo_error_scenarios()
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        try:
            thinking.stop()
        except:
            pass
