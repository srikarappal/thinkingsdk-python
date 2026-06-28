#!/usr/bin/env python3
"""
Demo Project: How to Use ThinkingSDK in Your Own Code

This demonstrates exactly how to integrate ThinkingSDK into a real Python application.
Run this after starting the ThinkingSDK server and dashboard.

Usage:
    python demo_project.py
"""

import time
import random
import sys
import os

# Add ThinkingSDK to path (for local development)
# In production, you'd install with: pip install -e .
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    import thinkingsdk as thinking
except ImportError:
    print("❌ ERROR: Cannot import thinkingsdk")
    print("   Make sure you're running from the ThinkingSDK directory")
    print("   Or install with: pip install -e .")
    sys.exit(1)

class UserService:
    """Example service class that will be instrumented."""
    
    def __init__(self):
        self.users_db = {
            1: {"name": "Alice Johnson", "email": "alice@example.com", "role": "admin"},
            2: {"name": "Bob Smith", "email": "bob@example.com", "role": "user"},
            3: {"name": "Carol Davis", "email": "carol@example.com", "role": "user"},
        }
        
    def get_user(self, user_id: int) -> dict:
        """Get user by ID - may raise exceptions."""
        if not isinstance(user_id, int):
            raise TypeError(f"user_id must be int, got {type(user_id)}")
            
        if user_id <= 0:
            raise ValueError("user_id must be positive")
            
        if user_id not in self.users_db:
            raise KeyError(f"User {user_id} not found")
            
        return self.users_db[user_id].copy()
    
    def create_user(self, name: str, email: str, role: str = "user") -> dict:
        """Create a new user."""
        if not name or not email:
            raise ValueError("Name and email are required")
            
        if "@" not in email:
            raise ValueError("Invalid email format")
            
        # Generate new user ID
        new_id = max(self.users_db.keys()) + 1
        
        new_user = {
            "name": name,
            "email": email,
            "role": role
        }
        
        self.users_db[new_id] = new_user
        return {"id": new_id, **new_user}
    
    def update_user(self, user_id: int, **updates) -> dict:
        """Update user information."""
        user = self.get_user(user_id)  # This may raise KeyError
        
        # Validate updates
        if "email" in updates and "@" not in updates["email"]:
            raise ValueError("Invalid email format")
            
        # Apply updates
        user.update(updates)
        self.users_db[user_id] = user
        
        return user
    
    def calculate_user_stats(self) -> dict:
        """Calculate statistics about users."""
        total_users = len(self.users_db)
        admins = sum(1 for user in self.users_db.values() if user["role"] == "admin")
        regular_users = total_users - admins
        
        return {
            "total_users": total_users,
            "admins": admins,
            "regular_users": regular_users,
            "admin_percentage": (admins / total_users * 100) if total_users > 0 else 0
        }

class OrderService:
    """Another example service to show multiple classes being instrumented."""
    
    def __init__(self, user_service: UserService):
        self.user_service = user_service
        self.orders_db = {}
        self.next_order_id = 1000
    
    def create_order(self, user_id: int, items: list, total: float) -> dict:
        """Create a new order."""
        # Verify user exists (this call is instrumented)
        user = self.user_service.get_user(user_id)
        
        if not items:
            raise ValueError("Order must have at least one item")
            
        if total <= 0:
            raise ValueError("Order total must be positive")
        
        order = {
            "id": self.next_order_id,
            "user_id": user_id,
            "user_name": user["name"],
            "items": items,
            "total": total,
            "status": "pending",
            "created_at": time.time()
        }
        
        self.orders_db[self.next_order_id] = order
        self.next_order_id += 1
        
        return order
    
    def process_payment(self, order_id: int) -> dict:
        """Process payment for an order."""
        if order_id not in self.orders_db:
            raise KeyError(f"Order {order_id} not found")
            
        order = self.orders_db[order_id]
        
        # Simulate payment processing
        if random.random() < 0.1:  # 10% chance of payment failure
            raise RuntimeError("Payment processing failed - card declined")
        
        # Simulate processing delay
        time.sleep(0.1)
        
        order["status"] = "paid"
        order["paid_at"] = time.time()
        
        return order

def simulate_web_requests():
    """Simulate a series of web requests that might occur in a real application."""
    print("🌐 Simulating web application requests...")
    
    user_service = UserService()
    order_service = OrderService(user_service)
    
    requests = [
        # Successful requests
        ("GET /users/1", lambda: user_service.get_user(1)),
        ("GET /users/2", lambda: user_service.get_user(2)),
        ("POST /users", lambda: user_service.create_user("Dave Wilson", "dave@example.com")),
        ("GET /stats", lambda: user_service.calculate_user_stats()),
        
        # Requests that will cause exceptions
        ("GET /users/999", lambda: user_service.get_user(999)),  # KeyError
        ("GET /users/abc", lambda: user_service.get_user("abc")),  # TypeError
        ("POST /users", lambda: user_service.create_user("", "invalid")),  # ValueError
        ("PUT /users/1", lambda: user_service.update_user(1, email="invalid-email")),  # ValueError
        
        # Order operations
        ("POST /orders", lambda: order_service.create_order(1, ["item1", "item2"], 29.99)),
        ("POST /orders", lambda: order_service.create_order(2, [], 0)),  # ValueError
        ("POST /payment/1000", lambda: order_service.process_payment(1000)),
        ("POST /payment/9999", lambda: order_service.process_payment(9999)),  # KeyError
    ]
    
    success_count = 0
    error_count = 0
    
    for i, (request_desc, request_func) in enumerate(requests, 1):
        print(f"   📡 Request {i:2d}: {request_desc}")
        
        try:
            result = request_func()
            success_count += 1
            print(f"        ✅ Success")
            
            # Add small delay between requests
            time.sleep(0.1)
            
        except Exception as e:
            error_count += 1
            print(f"        ❌ Error: {type(e).__name__}: {e}")
            
            # ThinkingSDK automatically captures these exceptions
            # and will send them for AI analysis
            
    print(f"\n   📊 Summary: {success_count} successful, {error_count} failed requests")
    return success_count, error_count

def simulate_data_processing():
    """Simulate data processing operations."""
    print("\n📊 Simulating data processing operations...")
    
    def process_batch(batch_data: list) -> dict:
        """Process a batch of data."""
        if not batch_data:
            raise ValueError("Batch cannot be empty")
        
        results = []
        errors = []
        
        for item in batch_data:
            try:
                # Simulate processing each item
                if item.get("value", 0) < 0:
                    raise ValueError(f"Negative value not allowed: {item['value']}")
                
                processed = {
                    "id": item["id"],
                    "processed_value": item["value"] * 2.5,
                    "status": "success"
                }
                results.append(processed)
                
            except Exception as e:
                errors.append({"id": item.get("id", "unknown"), "error": str(e)})
        
        return {
            "total_items": len(batch_data),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }
    
    # Test data batches
    batches = [
        # Good batch
        [{"id": 1, "value": 10}, {"id": 2, "value": 20}, {"id": 3, "value": 30}],
        
        # Batch with problems
        [{"id": 4, "value": -5}, {"id": 5, "value": 15}, {"id": 6, "value": -10}],
        
        # Empty batch (will cause exception)
        [],
        
        # Batch with missing data
        [{"id": 7}, {"id": 8, "value": 25}],
    ]
    
    for i, batch in enumerate(batches, 1):
        print(f"   🔄 Processing batch {i} ({len(batch)} items)")
        
        try:
            result = process_batch(batch)
            print(f"        ✅ Processed: {result['successful']} success, {result['failed']} failed")
        except Exception as e:
            print(f"        ❌ Batch failed: {type(e).__name__}: {e}")

def run_performance_test():
    """Run a performance test to generate many events."""
    print("\n⚡ Running performance test...")
    
    def fibonacci(n: int) -> int:
        """Calculate Fibonacci number (recursive for more function calls)."""
        if n <= 1:
            return n
        return fibonacci(n - 1) + fibonacci(n - 2)
    
    def matrix_multiply(a: list, b: list) -> list:
        """Simple matrix multiplication."""
        rows_a, cols_a = len(a), len(a[0])
        rows_b, cols_b = len(b), len(b[0])
        
        if cols_a != rows_b:
            raise ValueError("Incompatible matrix dimensions")
        
        result = [[0 for _ in range(cols_b)] for _ in range(rows_a)]
        
        for i in range(rows_a):
            for j in range(cols_b):
                for k in range(cols_a):
                    result[i][j] += a[i][k] * b[k][j]
        
        return result
    
    # Generate multiple function calls
    operations = [
        ("Fibonacci(8)", lambda: fibonacci(8)),
        ("Fibonacci(9)", lambda: fibonacci(9)),
        ("Matrix Multiply", lambda: matrix_multiply([[1, 2], [3, 4]], [[5, 6], [7, 8]])),
        ("Large List Processing", lambda: [x**2 for x in range(100) if x % 3 == 0]),
        ("Dictionary Operations", lambda: {f"key_{i}": i**2 for i in range(50)}),
    ]
    
    for desc, operation in operations:
        print(f"   🔢 {desc}")
        start_time = time.time()
        try:
            result = operation()
            elapsed = time.time() - start_time
            print(f"        ✅ Completed in {elapsed:.3f}s")
        except Exception as e:
            print(f"        ❌ Failed: {e}")

def main():
    """Main demo application."""
    print("🚀 THINKINGSDK DEMO PROJECT")
    print("=" * 50)
    
    # Check if server is running
    import requests
    try:
        response = requests.get("http://localhost:8001/health", timeout=2)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ ThinkingSDK server is running")
            print(f"   OpenAI configured: {health.get('openai_configured', False)}")
        else:
            print("⚠️  Server responded but may have issues")
    except:
        print("❌ ERROR: ThinkingSDK server is not running!")
        print("   Start it with: uvicorn thinking_sdk_server.server:app --reload --port 8001")
        return
    
    # Start ThinkingSDK
    print("\n🔧 Starting ThinkingSDK instrumentation...")
    
    config = {
        'instrumentation': {
            'sample_rate': 1.0,        # Capture all events for demo
            'capture_returns': True,   # Capture return values
            'max_locals': 5,          # Capture up to 5 local variables
        },
        'sender': {
            'batch_size': 10,         # Send in small batches for demo
            'max_batch_wait': 2.0,    # Wait max 2 seconds
        }
    }
    
    thinking.start(
        api_key="sk_live_XXXX",           # ThinkingSDK auth key (not OpenAI!)
        server_url="http://localhost:8001", # Your local ThinkingSDK server
        config=config
    )
    
    if not thinking.is_active():
        print("❌ Failed to start ThinkingSDK")
        return
    
    print("✅ ThinkingSDK started successfully!")
    print("\n💡 Now generating events - watch the dashboard at http://localhost:8501")
    print("   AI insights will appear within 5-10 seconds of exceptions")
    
    try:
        # Run different scenarios
        simulate_web_requests()
        simulate_data_processing()
        run_performance_test()
        
        # Show SDK statistics
        print("\n📊 ThinkingSDK Statistics:")
        stats = thinking.get_stats()
        print(f"   Events captured: {stats.get('instrumentation', {}).get('event_count', 0)}")
        print(f"   Queue size: {stats.get('queue', {}).get('current_size', 0)}")
        print(f"   Events sent: {stats.get('sender', {}).get('total_sent', 0)}")
        
        # Wait for processing
        print("\n⏳ Waiting 10 seconds for AI analysis...")
        time.sleep(10)
        
        # Check insights
        try:
            response = requests.get("http://localhost:8001/insights", timeout=5)
            if response.status_code == 200:
                insights = response.json()
                print(f"\n🧠 Generated {len(insights)} insights!")
                
                if insights:
                    latest = insights[-1]
                    print(f"   📝 Latest insight type: {latest.get('kind', 'unknown')}")
                    print(f"   💬 Content preview: {latest.get('body', 'no content')[:150]}...")
                else:
                    print("   ℹ️  No insights generated yet (may need more time)")
        except Exception as e:
            print(f"   ⚠️  Could not check insights: {e}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    
    finally:
        # Always stop ThinkingSDK
        print("\n🛑 Stopping ThinkingSDK...")
        thinking.stop()
        print("✅ ThinkingSDK stopped")
    
    print("\n🎉 Demo completed!")
    print("\n💡 Next steps:")
    print("   1. Check the dashboard for AI-generated insights")
    print("   2. Review the server logs for processing details")
    print("   3. Try integrating ThinkingSDK into your own projects")
    print("   4. Read INTEGRATION_GUIDE.md for detailed instructions")

if __name__ == "__main__":
    main()
