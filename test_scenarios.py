#!/usr/bin/env python3
"""
Comprehensive test scenarios for ThinkingSDK current implementation.

This script provides various testing scenarios to validate:
1. Basic exception handling and LLM analysis
2. Performance patterns and batching behavior
3. Real-world application simulation
4. Performance impact measurement
5. Edge cases and error conditions

Usage:
    python test_scenarios.py [scenario_name]
    
Available scenarios:
    - basic_exceptions: Test various Python exceptions
    - performance_patterns: Test high-frequency calls and batching
    - web_app_simulation: Simulate web application workflow
    - database_simulation: Simulate database operations
    - edge_cases: Test error conditions and edge cases
    - performance_benchmark: Measure SDK performance impact
    - all: Run all test scenarios
"""

import sys
import time
import random
import threading
from typing import Dict, List, Any
from contextlib import contextmanager

# Import ThinkingSDK
try:
    import thinkingsdk as thinking
except ImportError:
    print("ERROR: thinkingsdk not found. Make sure it's installed.")
    sys.exit(1)


class TestScenarios:
    """Comprehensive test scenarios for ThinkingSDK."""
    
    def __init__(self, api_key: str = "sk_live_XXXX", server_url: str = "http://localhost:8000"):
        """Initialize test scenarios with SDK configuration."""
        self.api_key = api_key
        self.server_url = server_url
        self.results = {}
        
    @contextmanager
    def sdk_session(self, config: Dict[str, Any] = None):
        """Context manager for SDK sessions."""
        print(f"🚀 Starting ThinkingSDK session...")
        thinking.start(self.api_key, self.server_url, config=config, enable_logging=True)
        
        try:
            yield
        finally:
            print("🛑 Stopping ThinkingSDK session...")
            thinking.stop()
            time.sleep(1)  # Allow final events to process
            
    def basic_exceptions(self):
        """Test basic exception scenarios that should trigger LLM analysis."""
        print("\n" + "="*60)
        print("🧪 SCENARIO 1: Basic Exception Testing")
        print("="*60)
        
        with self.sdk_session():
            # Division by zero
            print("\n📍 Testing Division by Zero...")
            try:
                def division_error_test():
                    x = 10
                    y = 0
                    return x / y
                
                division_error_test()
            except ZeroDivisionError as e:
                print(f"   ✅ Caught expected error: {e}")
                
            # Type error
            print("\n📍 Testing Type Error...")
            try:
                def type_error_test():
                    greeting = "Hello"
                    number = 42
                    return greeting + number
                
                type_error_test()
            except TypeError as e:
                print(f"   ✅ Caught expected error: {e}")
                
            # Key error
            print("\n📍 Testing Key Error...")
            try:
                def key_error_test():
                    user_data = {"name": "Alice", "email": "alice@example.com"}
                    return user_data["age"]  # Key doesn't exist
                
                key_error_test()
            except KeyError as e:
                print(f"   ✅ Caught expected error: {e}")
                
            # Index error
            print("\n📍 Testing Index Error...")
            try:
                def index_error_test():
                    items = ["apple", "banana", "cherry"]
                    return items[10]  # Index out of range
                
                index_error_test()
            except IndexError as e:
                print(f"   ✅ Caught expected error: {e}")
                
            # Nested exception
            print("\n📍 Testing Nested Exception...")
            try:
                def nested_error_test():
                    def inner_function():
                        def deepest_function():
                            raise ValueError("Deep nested error for testing")
                        deepest_function()
                    inner_function()
                
                nested_error_test()
            except ValueError as e:
                print(f"   ✅ Caught expected error: {e}")
                
            print("\n⏱️  Waiting 5 seconds for LLM analysis...")
            time.sleep(5)
            
        print("✅ Basic exception testing completed!")
        
    def performance_patterns(self):
        """Test performance patterns and high-frequency calls."""
        print("\n" + "="*60)
        print("🏃 SCENARIO 2: Performance Pattern Testing")
        print("="*60)
        
        config = {
            'instrumentation': {'sample_rate': 1.0},  # Capture all events
            'sender': {'batch_size': 20, 'max_batch_wait': 1.0}
        }
        
        with self.sdk_session(config):
            # High-frequency function calls
            print("\n📍 Testing High-Frequency Calls...")
            def fast_computation(n: int) -> int:
                result = 0
                for i in range(n):
                    result += i
                return result
            
            start_time = time.time()
            results = []
            for i in range(50):
                result = fast_computation(100)
                results.append(result)
                if i % 10 == 0:
                    print(f"   📊 Completed {i+1}/50 calls")
                    
            elapsed = time.time() - start_time
            print(f"   ⏱️  50 function calls took {elapsed:.2f} seconds")
            
            # Recursive function calls
            print("\n📍 Testing Recursive Calls...")
            def fibonacci(n: int) -> int:
                if n <= 1:
                    return n
                return fibonacci(n-1) + fibonacci(n-2)
            
            fib_result = fibonacci(8)  # Not too deep to avoid stack overflow
            print(f"   🔢 Fibonacci(8) = {fib_result}")
            
            # Nested function calls
            print("\n📍 Testing Nested Function Calls...")
            def outer_function(data: List[int]) -> Dict[str, Any]:
                def middle_function(items: List[int]) -> List[int]:
                    def inner_function(x: int) -> int:
                        return x * 2 + 1
                    return [inner_function(item) for item in items]
                
                processed = middle_function(data)
                return {
                    "original": data,
                    "processed": processed,
                    "count": len(processed)
                }
            
            nested_result = outer_function([1, 2, 3, 4, 5])
            print(f"   📊 Nested processing result: {nested_result}")
            
            print("\n⏱️  Waiting 5 seconds for event processing...")
            time.sleep(5)
            
        print("✅ Performance pattern testing completed!")
        
    def web_app_simulation(self):
        """Simulate a web application workflow."""
        print("\n" + "="*60)
        print("🌐 SCENARIO 3: Web Application Simulation")
        print("="*60)
        
        config = {
            'instrumentation': {
                'sample_rate': 1.0,
                'capture_returns': True,
                'max_locals': 8
            }
        }
        
        with self.sdk_session(config):
            # Simulate user authentication
            print("\n📍 Simulating User Authentication...")
            
            def authenticate_user(username: str, password: str) -> Dict[str, Any]:
                """Simulate user authentication with database lookup."""
                time.sleep(0.05)  # Simulate database delay
                
                # Simulate user database
                users_db = {
                    "admin": {"id": 1, "password": "admin123", "role": "admin"},
                    "user1": {"id": 2, "password": "user123", "role": "user"},
                    "guest": {"id": 3, "password": "guest123", "role": "guest"}
                }
                
                if username in users_db and users_db[username]["password"] == password:
                    return {
                        "success": True,
                        "user_id": users_db[username]["id"],
                        "role": users_db[username]["role"]
                    }
                else:
                    return {"success": False, "error": "Invalid credentials"}
            
            def fetch_user_profile(user_id: int) -> Dict[str, Any]:
                """Simulate fetching user profile data."""
                time.sleep(0.03)  # Simulate database delay
                
                profiles = {
                    1: {"name": "Admin User", "email": "admin@example.com", "last_login": "2024-01-15"},
                    2: {"name": "Regular User", "email": "user@example.com", "last_login": "2024-01-14"},
                    3: {"name": "Guest User", "email": "guest@example.com", "last_login": "2024-01-10"}
                }
                
                return profiles.get(user_id, {"error": "User not found"})
            
            def process_business_logic(user_data: Dict[str, Any]) -> Dict[str, Any]:
                """Simulate business logic processing."""
                if user_data.get("role") == "admin":
                    permissions = ["read", "write", "delete", "admin"]
                elif user_data.get("role") == "user":
                    permissions = ["read", "write"]
                else:
                    permissions = ["read"]
                    
                return {
                    "user_data": user_data,
                    "permissions": permissions,
                    "session_token": f"token_{random.randint(10000, 99999)}"
                }
            
            def simulate_web_request(username: str, password: str) -> Dict[str, Any]:
                """Simulate complete web request processing."""
                # Authentication
                auth_result = authenticate_user(username, password)
                if not auth_result["success"]:
                    raise PermissionError(f"Authentication failed for user: {username}")
                
                # Fetch user profile
                profile = fetch_user_profile(auth_result["user_id"])
                if "error" in profile:
                    raise ValueError(f"User profile error: {profile['error']}")
                
                # Process business logic
                combined_data = {**auth_result, **profile}
                final_result = process_business_logic(combined_data)
                
                return final_result
            
            # Test successful requests
            print("   🔐 Testing successful authentication...")
            successful_requests = 0
            for username in ["admin", "user1", "guest"]:
                try:
                    if username == "admin":
                        password = "admin123"
                    elif username == "user1":
                        password = "user123"
                    else:
                        password = "guest123"
                        
                    result = simulate_web_request(username, password)
                    successful_requests += 1
                    print(f"     ✅ {username}: {result['permissions']}")
                except Exception as e:
                    print(f"     ❌ {username}: {e}")
            
            # Test failed requests
            print("\n   🚫 Testing failed authentication...")
            failed_requests = 0
            for username, password in [("admin", "wrong"), ("nonuser", "test"), ("user1", "invalid")]:
                try:
                    simulate_web_request(username, password)
                except Exception as e:
                    failed_requests += 1
                    print(f"     ❌ {username}: {e}")
            
            print(f"\n   📊 Summary: {successful_requests} successful, {failed_requests} failed requests")
            
            print("\n⏱️  Waiting 5 seconds for event processing...")
            time.sleep(5)
            
        print("✅ Web application simulation completed!")
        
    def database_simulation(self):
        """Simulate database operations and common issues."""
        print("\n" + "="*60)
        print("🗄️  SCENARIO 4: Database Operation Simulation")
        print("="*60)
        
        with self.sdk_session():
            print("\n📍 Simulating Database Operations...")
            
            def create_connection() -> Dict[str, Any]:
                """Simulate database connection creation."""
                time.sleep(0.02)  # Connection delay
                return {
                    "host": "localhost",
                    "database": "testdb",
                    "connected": True,
                    "connection_id": random.randint(1000, 9999)
                }
            
            def execute_query(connection: Dict[str, Any], query: str, slow: bool = False) -> List[Dict[str, Any]]:
                """Simulate query execution."""
                if not connection.get("connected"):
                    raise ConnectionError("Database connection is closed")
                
                # Simulate query processing time
                if slow:
                    time.sleep(0.2)  # Slow query
                else:
                    time.sleep(0.01)  # Fast query
                
                # Simulate results based on query type
                if "SELECT" in query.upper():
                    return [
                        {"id": i, "name": f"Record {i}", "value": random.randint(1, 100)}
                        for i in range(1, 6)
                    ]
                elif "INSERT" in query.upper():
                    return [{"affected_rows": 1}]
                elif "UPDATE" in query.upper():
                    return [{"affected_rows": random.randint(1, 5)}]
                else:
                    return []
            
            def close_connection(connection: Dict[str, Any]) -> None:
                """Simulate connection cleanup."""
                connection["connected"] = False
                time.sleep(0.01)
            
            # Normal database operations
            print("   📊 Testing normal database operations...")
            connection = create_connection()
            print(f"     🔗 Created connection: {connection['connection_id']}")
            
            # Fast queries
            for i, query in enumerate([
                "SELECT * FROM users WHERE active = 1",
                "SELECT COUNT(*) FROM orders",
                "INSERT INTO logs (message) VALUES ('Test message')"
            ], 1):
                try:
                    results = execute_query(connection, query)
                    print(f"     ✅ Query {i}: {len(results)} results")
                except Exception as e:
                    print(f"     ❌ Query {i}: {e}")
            
            # Slow query simulation
            print("\n   🐌 Testing slow query...")
            try:
                slow_results = execute_query(
                    connection, 
                    "SELECT * FROM large_table JOIN another_table ON complex_condition", 
                    slow=True
                )
                print(f"     ⏱️  Slow query completed: {len(slow_results)} results")
            except Exception as e:
                print(f"     ❌ Slow query failed: {e}")
            
            # Connection failure simulation
            print("\n   💥 Testing connection failure...")
            close_connection(connection)
            try:
                execute_query(connection, "SELECT * FROM users")
            except ConnectionError as e:
                print(f"     ✅ Expected connection error: {e}")
            
            # N+1 query problem simulation
            print("\n   🔄 Simulating N+1 query problem...")
            def get_user_with_orders_n_plus_1(user_ids: List[int]) -> List[Dict[str, Any]]:
                """Inefficient N+1 query pattern."""
                new_connection = create_connection()
                
                # Get all users (1 query)
                users = execute_query(new_connection, f"SELECT * FROM users WHERE id IN ({','.join(map(str, user_ids))})")
                
                # Get orders for each user (N queries - inefficient!)
                for user in users:
                    orders = execute_query(new_connection, f"SELECT * FROM orders WHERE user_id = {user['id']}")
                    user["orders"] = orders
                
                close_connection(new_connection)
                return users
            
            users_with_orders = get_user_with_orders_n_plus_1([1, 2, 3, 4, 5])
            print(f"     📊 Processed {len(users_with_orders)} users with orders (N+1 pattern)")
            
            print("\n⏱️  Waiting 5 seconds for event processing...")
            time.sleep(5)
            
        print("✅ Database simulation completed!")
        
    def edge_cases(self):
        """Test edge cases and error conditions."""
        print("\n" + "="*60)
        print("🎯 SCENARIO 5: Edge Cases and Error Conditions")
        print("="*60)
        
        with self.sdk_session():
            print("\n📍 Testing Edge Cases...")
            
            # Very deep recursion (but not stack overflow)
            print("   🔄 Testing deep recursion...")
            def countdown(n: int) -> int:
                if n <= 0:
                    return 0
                return n + countdown(n - 1)
            
            try:
                result = countdown(50)  # Moderate depth
                print(f"     ✅ Deep recursion result: {result}")
            except RecursionError as e:
                print(f"     ❌ Recursion error: {e}")
            
            # Large data structures
            print("\n   📚 Testing large data structures...")
            def process_large_data() -> Dict[str, Any]:
                large_list = list(range(10000))
                large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}
                
                # Process data
                filtered_list = [x for x in large_list if x % 100 == 0]
                dict_keys = list(large_dict.keys())[:10]  # First 10 keys
                
                return {
                    "original_size": len(large_list),
                    "filtered_size": len(filtered_list),
                    "dict_sample": dict_keys
                }
            
            large_result = process_large_data()
            print(f"     📊 Large data processing: {large_result}")
            
            # Unicode and special characters
            print("\n   🌍 Testing Unicode handling...")
            def unicode_processing() -> Dict[str, str]:
                unicode_data = {
                    "emoji": "🚀🎯🌟",
                    "chinese": "你好世界",
                    "arabic": "مرحبا بالعالم", 
                    "japanese": "こんにちは世界",
                    "special": "\"quotes\" & <tags> & symbols: @#$%^&*()"
                }
                
                processed = {}
                for key, value in unicode_data.items():
                    processed[f"processed_{key}"] = f"[{len(value)}] {value}"
                
                return processed
            
            unicode_result = unicode_processing()
            print(f"     🌍 Unicode processing completed: {len(unicode_result)} items")
            
            # Multiple exception types in sequence
            print("\n   💥 Testing multiple exception types...")
            exception_count = 0
            for i, test_func in enumerate([
                lambda: [][10],  # IndexError
                lambda: {}["missing"],  # KeyError  
                lambda: int("not_a_number"),  # ValueError
                lambda: 1 / 0,  # ZeroDivisionError
                lambda: "string" + 123,  # TypeError
            ], 1):
                try:
                    test_func()
                except Exception as e:
                    exception_count += 1
                    print(f"     ✅ Exception {i}: {type(e).__name__}")
            
            print(f"     📊 Caught {exception_count} different exception types")
            
            print("\n⏱️  Waiting 5 seconds for event processing...")
            time.sleep(5)
            
        print("✅ Edge cases testing completed!")
        
    def performance_benchmark(self):
        """Measure SDK performance impact."""
        print("\n" + "="*60)
        print("⚡ SCENARIO 6: Performance Impact Benchmark")
        print("="*60)
        
        def benchmark_function() -> float:
            """Function to benchmark - does some computation."""
            result = 0
            for i in range(1000):
                result += i * i + i / 2 if i > 0 else 0
            return result
        
        # Benchmark without SDK
        print("\n📍 Benchmarking without SDK...")
        times_without_sdk = []
        for i in range(10):
            start = time.time()
            benchmark_function()
            elapsed = time.time() - start
            times_without_sdk.append(elapsed)
            
        avg_without_sdk = sum(times_without_sdk) / len(times_without_sdk)
        print(f"   ⏱️  Average time without SDK: {avg_without_sdk:.6f} seconds")
        
        # Benchmark with SDK
        print("\n📍 Benchmarking with SDK...")
        times_with_sdk = []
        
        with self.sdk_session():
            for i in range(10):
                start = time.time()
                benchmark_function()
                elapsed = time.time() - start
                times_with_sdk.append(elapsed)
                
        avg_with_sdk = sum(times_with_sdk) / len(times_with_sdk)
        overhead = ((avg_with_sdk - avg_without_sdk) / avg_without_sdk) * 100
        
        print(f"   ⏱️  Average time with SDK: {avg_with_sdk:.6f} seconds")
        print(f"   📊 Performance overhead: {overhead:.2f}%")
        
        # Memory usage simulation
        print("\n📍 Testing memory usage patterns...")
        with self.sdk_session():
            def memory_intensive_function():
                # Create and process some data structures
                data = [{"id": i, "value": random.random()} for i in range(1000)]
                processed = [item for item in data if item["value"] > 0.5]
                return len(processed)
            
            memory_results = []
            for i in range(5):
                result = memory_intensive_function()
                memory_results.append(result)
                print(f"     📊 Iteration {i+1}: {result} items processed")
        
        # Store results
        self.results["performance_benchmark"] = {
            "avg_without_sdk": avg_without_sdk,
            "avg_with_sdk": avg_with_sdk,
            "overhead_percent": overhead,
            "memory_test_results": memory_results
        }
        
        print("✅ Performance benchmark completed!")
        
    def run_all_scenarios(self):
        """Run all test scenarios in sequence."""
        print("\n" + "="*80)
        print("🚀 RUNNING ALL THINKINGSDK TEST SCENARIOS")
        print("="*80)
        
        scenarios = [
            ("Basic Exceptions", self.basic_exceptions),
            ("Performance Patterns", self.performance_patterns),
            ("Web App Simulation", self.web_app_simulation),
            ("Database Simulation", self.database_simulation),
            ("Edge Cases", self.edge_cases),
            ("Performance Benchmark", self.performance_benchmark)
        ]
        
        start_time = time.time()
        
        for i, (name, func) in enumerate(scenarios, 1):
            print(f"\n🎯 Starting scenario {i}/{len(scenarios)}: {name}")
            try:
                func()
                print(f"✅ Scenario {i} completed successfully!")
            except Exception as e:
                print(f"❌ Scenario {i} failed: {e}")
                
        total_time = time.time() - start_time
        
        print("\n" + "="*80)
        print("📊 FINAL SUMMARY")
        print("="*80)
        print(f"⏱️  Total testing time: {total_time:.2f} seconds")
        print(f"🧪 Scenarios completed: {len(scenarios)}")
        
        if "performance_benchmark" in self.results:
            perf = self.results["performance_benchmark"]
            print(f"⚡ SDK overhead: {perf['overhead_percent']:.2f}%")
            
        print("\n💡 Next steps:")
        print("   1. Check the dashboard at http://localhost:8501 for LLM insights")
        print("   2. Review server logs for event processing")
        print("   3. Analyze the quality of AI-generated explanations")
        
        print("\n🎉 All test scenarios completed!")


def main():
    """Main entry point for test scenarios."""
    if len(sys.argv) > 1:
        scenario = sys.argv[1].lower()
    else:
        scenario = "all"
    
    # Check if server is running
    import requests
    try:
        response = requests.get("http://localhost:8000/insights", timeout=2)
        if response.status_code == 200:
            print("✅ ThinkingSDK server is running!")
        else:
            print("⚠️  Server responded but with unexpected status")
    except requests.exceptions.RequestException:
        print("❌ ERROR: ThinkingSDK server is not running!")
        print("   Please start the server first:")
        print("   uvicorn thinking_sdk_server.server:app --reload --port 8000")
        return
    
    # Initialize test scenarios
    tester = TestScenarios()
    
    # Run requested scenario
    scenario_map = {
        "basic_exceptions": tester.basic_exceptions,
        "performance_patterns": tester.performance_patterns,
        "web_app_simulation": tester.web_app_simulation,
        "database_simulation": tester.database_simulation,
        "edge_cases": tester.edge_cases,
        "performance_benchmark": tester.performance_benchmark,
        "all": tester.run_all_scenarios
    }
    
    if scenario in scenario_map:
        scenario_map[scenario]()
    else:
        print(f"❌ Unknown scenario: {scenario}")
        print(f"Available scenarios: {', '.join(scenario_map.keys())}")


if __name__ == "__main__":
    main()