#!/usr/bin/env python3
"""
Example: Using ThinkingSDK with YAML configuration
"""

import os
import thinkingsdk as thinking


def main():
    """Demonstrate YAML config-based usage."""
    
    # Method 1: Auto-discover thinkingsdk.yaml in project root
    # Set API key via environment variable for security
    os.environ["THINKINGSDK_API_KEY"] = "demo_key_yaml_test"
    
    # Start with YAML config (searches for thinkingsdk.yaml automatically)
    thinking.start()
    
    # Your application code
    demo_function()
    
    # Stop when done
    thinking.stop()
    
    print("\n" + "="*50)
    
    # Method 2: Override specific settings
    thinking.start(
        server_url="http://localhost:8001",  # Override server URL
        config={
            "tracking": {
                "capture_memory": True  # Enable memory tracking
            }
        }
    )
    
    demo_with_memory()
    
    stats = thinking.get_stats()
    print(f"\nStats: {stats['instrumentation']['event_count']} events captured")
    
    thinking.stop()
    
    print("\n" + "="*50)
    
    # Method 3: Specify custom config file
    thinking.start(
        config_file="custom-config.yaml",  # Use different config file
        enable_logging=True  # Override logging
    )
    
    demo_custom_config()
    
    thinking.stop()


def demo_function():
    """Simple function to demonstrate tracking."""
    print("Running demo with YAML config...")
    
    def calculate_sum(numbers):
        total = sum(numbers)
        return total
    
    result = calculate_sum([1, 2, 3, 4, 5])
    print(f"Sum: {result}")
    
    # Intentional error for testing
    try:
        value = int("not_a_number")
    except ValueError as e:
        print(f"Caught expected error: {e}")


def demo_with_memory():
    """Demo with memory tracking enabled."""
    print("\nRunning demo with memory tracking...")
    
    # Create some memory usage
    large_list = list(range(100000))
    large_dict = {i: f"value_{i}" for i in range(10000)}
    
    print(f"Created {len(large_list)} list items and {len(large_dict)} dict items")


def demo_custom_config():
    """Demo with custom configuration."""
    print("\nRunning demo with custom config...")
    
    # This would use settings from custom-config.yaml
    for i in range(5):
        process_item(i)


def process_item(item_id):
    """Process an item."""
    print(f"Processing item {item_id}")
    return f"processed_{item_id}"


if __name__ == "__main__":
    # Create a sample thinkingsdk.yaml for this demo
    yaml_content = """
# Demo ThinkingSDK Configuration
api_key_source: "env:THINKINGSDK_API_KEY"
server_url: "http://localhost:8000"
environment: "demo"

enabled: true
sampling_rate: 1.0

tracking:
  mode: "selective"
  include_functions: ["demo_*", "calculate_*", "process_*"]
  capture_locals: true
  capture_exceptions: true
  capture_performance: true
  capture_memory: false  # Will be overridden in Method 2

performance:
  slow_function_threshold_ms: 50

privacy:
  redact_keys: ["password", "secret"]
"""
    
    with open("thinkingsdk.yaml", "w") as f:
        f.write(yaml_content)
    
    print("Created thinkingsdk.yaml for demo")
    print("="*50)
    
    try:
        main()
    finally:
        # Clean up demo file
        import os
        if os.path.exists("thinkingsdk.yaml"):
            os.remove("thinkingsdk.yaml")
            print("\nCleaned up demo config file")