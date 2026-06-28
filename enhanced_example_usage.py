#!/usr/bin/env python3
"""
Enhanced ThinkingSDK Usage Examples - Showcasing Comprehensive Runtime Intelligence
"""

import time
import thinkingsdk as thinking


def demo_comprehensive_tracking():
    """Demonstrate comprehensive runtime tracking capabilities."""
    print("=== COMPREHENSIVE THINKINGSDK TRACKING DEMO ===\n")
    
    # Configuration for maximum intelligence gathering
    enhanced_config = {
        'instrumentation': {
            # Basic settings
            'sample_rate': 1.0,  # Capture everything for demo
            'max_locals': 10,    # Capture more local variables
            'capture_returns': True,  # Capture return values
            
            # Enhanced tracking features
            'capture_performance': True,     # Function timing
            'capture_memory': True,          # Memory usage tracking  
            'capture_call_patterns': True,   # Recursive calls, hot paths
            'capture_data_flow': True,       # Variable changes
            'capture_source_lines': True,    # Source code lines
            
            # Thresholds for pattern detection
            'slow_function_threshold': 0.05,  # 50ms threshold for slow functions
            'hot_path_threshold': 3,          # Functions called >3 times are "hot"
        },
        'sender': {
            'batch_size': 25,
            'max_batch_wait': 1.0,  # Send quickly for demo
        }
    }
    
    print("1. Starting ThinkingSDK with comprehensive tracking...")
    thinking.start(
        api_key="demo_key_comprehensive",
        server_url="http://localhost:8001",
        config=enhanced_config,
        enable_logging=True
    )
    
    print("   ✓ Enhanced instrumentation active")
    print("   ✓ Tracking: Performance, Memory, Call Patterns, Data Flow, Source Lines")
    
    # Demo 1: Performance Tracking
    print("\n2. Performance Tracking Demo:")
    demonstrate_performance_patterns()
    
    # Demo 2: Memory Tracking
    print("\n3. Memory Usage Tracking Demo:")
    demonstrate_memory_patterns()
    
    # Demo 3: Call Pattern Detection
    print("\n4. Call Pattern Detection Demo:")
    demonstrate_call_patterns()
    
    # Demo 4: Data Flow Analysis
    print("\n5. Data Flow Analysis Demo:")
    demonstrate_data_flow()
    
    # Demo 5: Error Context Enhancement
    print("\n6. Enhanced Error Context Demo:")
    demonstrate_enhanced_errors()
    
    # Wait for events to be processed and sent
    time.sleep(2)
    
    # Show comprehensive statistics
    print("\n7. Comprehensive Statistics:")
    stats = thinking.get_stats()
    display_enhanced_stats(stats)
    
    thinking.stop()
    print("\n✓ Enhanced demo completed!")


def demonstrate_performance_patterns():
    """Show performance tracking capabilities."""
    print("   • Testing functions with different performance characteristics...")
    
    def fast_function():
        """A fast function for comparison."""
        return sum(range(10))
    
    def slow_function():
        """A deliberately slow function."""
        time.sleep(0.1)  # 100ms - above our 50ms threshold
        return "slow_result"
    
    def variable_speed_function(delay):
        """Function with variable execution time."""
        time.sleep(delay)
        return f"result_after_{delay}s"
    
    # Call functions multiple times to build performance profiles
    print("     - Calling fast_function() 5 times...")
    for i in range(5):
        result = fast_function()
        
    print("     - Calling slow_function() 3 times...")
    for i in range(3):
        result = slow_function()
        
    print("     - Calling variable_speed_function() with different delays...")
    for delay in [0.02, 0.06, 0.15]:  # Mix of fast and slow calls
        result = variable_speed_function(delay)


def demonstrate_memory_patterns():
    """Show memory usage tracking."""
    print("   • Testing memory allocation patterns...")
    
    def memory_intensive_function():
        """Function that allocates significant memory."""
        # Create large data structures
        large_list = list(range(100000))  # ~800KB
        large_dict = {i: f"value_{i}" for i in range(10000)}  # ~500KB
        return len(large_list) + len(large_dict)
    
    def memory_efficient_function():
        """Function with minimal memory usage."""
        small_data = [1, 2, 3, 4, 5]
        return sum(small_data)
    
    print("     - Baseline memory usage...")
    baseline = memory_efficient_function()
    
    print("     - Memory intensive operations...")
    result = memory_intensive_function()
    
    print("     - Back to efficient operations...")
    final = memory_efficient_function()


def demonstrate_call_patterns():
    """Show call pattern detection (recursion, hot paths)."""
    print("   • Testing call pattern detection...")
    
    def recursive_fibonacci(n):
        """Recursive function to demonstrate recursion detection."""
        if n <= 1:
            return n
        return recursive_fibonacci(n-1) + recursive_fibonacci(n-2)
    
    def hot_path_function():
        """Function called many times to demonstrate hot path detection."""
        return "hot_result"
    
    def call_chain_function():
        """Function that calls other functions."""
        helper_function_a()
        helper_function_b()
        return "chain_result"
    
    def helper_function_a():
        return helper_function_b()
    
    def helper_function_b():
        return "helper_result"
    
    print("     - Testing recursive function (fibonacci(5))...")
    fib_result = recursive_fibonacci(5)
    print(f"       Fibonacci(5) = {fib_result}")
    
    print("     - Creating hot path (calling function 6 times)...")
    for i in range(6):  # Above our hot_path_threshold of 3
        hot_result = hot_path_function()
        
    print("     - Testing call chain patterns...")
    chain_result = call_chain_function()


def demonstrate_data_flow():
    """Show data flow and variable tracking."""  
    print("   • Testing data flow analysis...")
    
    def data_transformation_function(input_data):
        """Function that transforms data through multiple steps."""
        # Step 1: Initial processing
        processed_data = [x * 2 for x in input_data]
        
        # Step 2: Filtering
        filtered_data = [x for x in processed_data if x > 10]
        
        # Step 3: Final transformation
        result_data = {"count": len(filtered_data), "sum": sum(filtered_data)}
        
        return result_data
    
    def variable_mutation_function():
        """Function showing variable changes over time."""
        counter = 0
        results = []
        
        # Multiple mutations of the same variables
        for i in range(3):
            counter += i
            results.append(counter * 2)
            
        final_result = {"counter": counter, "results": results}
        return final_result
    
    print("     - Data transformation pipeline...")
    input_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    transformed = data_transformation_function(input_data)
    print(f"       Input: {input_data}")
    print(f"       Output: {transformed}")
    
    print("     - Variable mutation tracking...")
    mutations = variable_mutation_function()
    print(f"       Final state: {mutations}")


def demonstrate_enhanced_errors():
    """Show enhanced error context capture."""
    print("   • Testing enhanced error context...")
    
    def problematic_function(user_data, config):
        """Function that will cause various types of errors."""
        # Set up local context
        processing_stage = "validation"
        temp_results = []
        error_count = 0
        
        # This will cause an error with rich local context
        if config["strict_mode"]:
            processing_stage = "strict_validation"
            invalid_field = user_data["nonexistent_field"]  # KeyError
            
        return "success"
    
    def nested_error_function():
        """Function with nested calls leading to error."""
        return deep_function_level_1()
    
    def deep_function_level_1():
        return deep_function_level_2()
    
    def deep_function_level_2():
        return deep_function_level_3()
    
    def deep_function_level_3():
        # Error deep in call stack 
        problematic_data = {"key": "value"}
        return problematic_data["missing_key"]  # KeyError
    
    # Test 1: Error with rich local context
    print("     - Error with rich local context...")
    try:
        user_data = {"name": "John", "age": 30}
        config = {"strict_mode": True, "timeout": 5}
        result = problematic_function(user_data, config)
    except KeyError as e:
        print(f"       Caught KeyError: {e}")
    
    # Test 2: Error in deep call stack
    print("     - Error in deep call stack...")
    try:
        result = nested_error_function()
    except KeyError as e:
        print(f"       Caught nested KeyError: {e}")


def display_enhanced_stats(stats):
    """Display comprehensive statistics from enhanced tracking."""
    print("   📊 Enhanced Statistics:")
    print(f"      • Total events captured: {stats['instrumentation']['event_count']}")
    print(f"      • Queue status: {stats['queue']['current_size']} events pending")
    
    # Performance statistics
    if 'performance' in stats['instrumentation']:
        perf = stats['instrumentation']['performance']
        print(f"      • Function calls tracked: {perf['total_function_calls']}")
        print(f"      • Unique functions: {perf['unique_functions']}")
        
        if perf['hot_functions']:
            print("      • Hot path functions:")
            for func, count in perf['hot_functions'].items():
                print(f"        - {func}: {count} calls")
                
        if perf['slow_functions']:
            print("      • Slow functions detected:")
            for func, data in perf['slow_functions'].items():
                print(f"        - {func}: {data['avg_time_ms']:.1f}ms avg ({data['call_count']} calls)")
    
    # Configuration summary
    config = stats['config']['instrumentation']
    enabled_features = []
    if config.get('capture_performance'): enabled_features.append("Performance")
    if config.get('capture_memory'): enabled_features.append("Memory")
    if config.get('capture_call_patterns'): enabled_features.append("Call Patterns") 
    if config.get('capture_data_flow'): enabled_features.append("Data Flow")
    if config.get('capture_source_lines'): enabled_features.append("Source Lines")
    
    print(f"      • Active tracking: {', '.join(enabled_features)}")


if __name__ == "__main__":
    try:
        demo_comprehensive_tracking()
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        try:
            thinking.stop()
        except:
            pass