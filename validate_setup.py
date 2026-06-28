#!/usr/bin/env python3
"""
ThinkingSDK Setup Validation Script

This script validates that the complete ThinkingSDK system is working correctly
by running a simple end-to-end test and checking all components.

Usage:
    python validate_setup.py [--wait-for-server] [--verbose]
"""

import sys
import time
import argparse
import json
from typing import Dict, Any, List

def check_imports() -> bool:
    """Check that all required modules can be imported."""
    print("🔍 Checking imports...")
    
    required_modules = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"), 
        ("streamlit", "Streamlit"),
        ("openai", "OpenAI"),
        ("requests", "Requests"),
        ("pydantic", "Pydantic"),
        ("thinkingsdk", "ThinkingSDK Client")
    ]
    
    failed_imports = []
    
    for module, name in required_modules:
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError as e:
            print(f"   ❌ {name}: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n❌ Failed to import: {', '.join(failed_imports)}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    return True

def check_server_connection(wait: bool = False, max_wait: int = 30) -> Dict[str, Any]:
    """Check connection to ThinkingSDK server."""
    print("\n🖥️  Checking server connection...")
    
    import requests
    
    if wait:
        print(f"   ⏳ Waiting up to {max_wait} seconds for server...")
        
    for attempt in range(max_wait if wait else 1):
        try:
            response = requests.get("http://localhost:8000/insights", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Server is running (port 8000)")
                print(f"   📊 Current insights: {len(data)}")
                return {"status": "running", "insights": len(data)}
            else:
                print(f"   ⚠️  Server responded with status {response.status_code}")
                return {"status": "error", "status_code": response.status_code}
                
        except requests.exceptions.ConnectionError:
            if wait and attempt < max_wait - 1:
                print(f"   ⏳ Attempt {attempt + 1}/{max_wait}: Server not ready, waiting...")
                time.sleep(1)
                continue
            else:
                print("   ❌ Server not running on port 8000")
                print("   Start with: uvicorn thinking_sdk_server.server:app --reload --port 8000")
                return {"status": "not_running"}
                
        except Exception as e:
            print(f"   ❌ Error connecting to server: {e}")
            return {"status": "error", "error": str(e)}
    
    return {"status": "timeout"}

def check_dashboard_connection() -> bool:
    """Check connection to Streamlit dashboard."""
    print("\n📊 Checking dashboard connection...")
    
    import requests
    
    try:
        response = requests.get("http://localhost:8501", timeout=5)
        
        if response.status_code == 200:
            print("   ✅ Dashboard is running (port 8501)")
            return True
        else:
            print(f"   ⚠️  Dashboard responded with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Dashboard not running on port 8501")
        print("   Start with: streamlit run thinking_sdk_server/dashboard.py")
        return False
        
    except Exception as e:
        print(f"   ❌ Error connecting to dashboard: {e}")
        return False

def run_end_to_end_test(verbose: bool = False) -> Dict[str, Any]:
    """Run a complete end-to-end test of ThinkingSDK."""
    print("\n🧪 Running end-to-end test...")
    
    try:
        import thinkingsdk as thinking
        
        # Start SDK
        print("   📍 Starting SDK...")
        thinking.start(
            api_key="sk_live_XXXX",
            server_url="http://localhost:8000",
            config={
                'instrumentation': {'sample_rate': 1.0, 'capture_returns': True},
                'sender': {'batch_size': 5, 'max_batch_wait': 1.0}
            }
        )
        
        if not thinking.is_active():
            print("   ❌ SDK failed to start")
            return {"success": False, "error": "SDK start failed"}
        
        print("   ✅ SDK started successfully")
        
        # Test normal function execution
        print("   📍 Testing normal function execution...")
        
        def test_calculation(a: int, b: int) -> int:
            """Test function for validation."""
            result = a * b + (a - b)
            return result
        
        def test_string_processing(text: str) -> str:
            """Test string processing function."""
            return f"Processed: {text.upper().strip()}"
        
        # Execute test functions
        calc_result = test_calculation(10, 5)
        string_result = test_string_processing("  hello world  ")
        
        if verbose:
            print(f"     🔢 Calculation result: {calc_result}")
            print(f"     🔤 String result: {string_result}")
        
        print("   ✅ Normal functions executed successfully")
        
        # Test exception handling
        print("   📍 Testing exception handling...")
        
        def test_exception_function():
            """Function that raises an exception for testing."""
            raise ValueError("Test exception for validation")
        
        exception_caught = False
        try:
            test_exception_function()
        except ValueError:
            exception_caught = True
            print("   ✅ Exception caught and should be processed by server")
        
        if not exception_caught:
            print("   ⚠️  Expected exception was not raised")
        
        # Get SDK stats
        print("   📍 Checking SDK statistics...")
        stats = thinking.get_stats()
        
        if not isinstance(stats, dict):
            print("   ❌ Stats returned invalid format")
            return {"success": False, "error": "Invalid stats format"}
        
        required_stat_keys = ['sdk_active', 'instrumentation', 'queue', 'sender']
        missing_keys = [key for key in required_stat_keys if key not in stats]
        
        if missing_keys:
            print(f"   ⚠️  Missing stats keys: {missing_keys}")
        else:
            print("   ✅ Stats collection working correctly")
        
        if verbose:
            print(f"     📊 Event count: {stats.get('instrumentation', {}).get('event_count', 'N/A')}")
            print(f"     📊 Queue size: {stats.get('queue', {}).get('current_size', 'N/A')}")
            print(f"     📊 Sender alive: {stats.get('sender', {}).get('thread_alive', 'N/A')}")
        
        # Wait for event processing
        print("   📍 Waiting for event processing...")
        time.sleep(3)  # Allow time for events to be sent and processed
        
        # Stop SDK
        print("   📍 Stopping SDK...")
        thinking.stop()
        
        if thinking.is_active():
            print("   ⚠️  SDK still active after stop")
        else:
            print("   ✅ SDK stopped successfully")
        
        return {
            "success": True,
            "calc_result": calc_result,
            "string_result": string_result,
            "exception_caught": exception_caught,
            "stats": stats
        }
        
    except Exception as e:
        print(f"   ❌ End-to-end test failed: {e}")
        
        # Try to stop SDK if it was started
        try:
            thinking.stop()
        except:
            pass
            
        return {"success": False, "error": str(e)}

def check_insights_generation(wait_time: int = 10) -> Dict[str, Any]:
    """Check if insights are being generated by the server."""
    print(f"\n🤖 Checking insight generation (waiting {wait_time}s)...")
    
    import requests
    
    try:
        # Get initial insight count
        response = requests.get("http://localhost:8000/insights", timeout=5)
        initial_insights = response.json()
        initial_count = len(initial_insights)
        
        print(f"   📊 Initial insights count: {initial_count}")
        
        # Wait for processing
        print(f"   ⏳ Waiting {wait_time} seconds for new insights...")
        time.sleep(wait_time)
        
        # Check for new insights
        response = requests.get("http://localhost:8000/insights", timeout=5)
        final_insights = response.json()
        final_count = len(final_insights)
        
        new_insights = final_count - initial_count
        
        if new_insights > 0:
            print(f"   ✅ Generated {new_insights} new insights!")
            
            # Show latest insight
            if final_insights:
                latest = final_insights[-1]
                print(f"   🧠 Latest insight type: {latest.get('kind', 'unknown')}")
                
                if 'body' in latest:
                    body_preview = latest['body'][:100] + "..." if len(latest['body']) > 100 else latest['body']
                    print(f"   💬 Preview: {body_preview}")
                    
        else:
            print("   ⚠️  No new insights generated")
            print("   This might indicate the LLM is not being called or exceptions aren't being processed")
        
        return {
            "initial_count": initial_count,
            "final_count": final_count,
            "new_insights": new_insights,
            "latest_insights": final_insights[-3:] if final_insights else []
        }
        
    except Exception as e:
        print(f"   ❌ Error checking insights: {e}")
        return {"error": str(e)}

def print_final_summary(results: Dict[str, Any]):
    """Print a final summary of all validation results."""
    print("\n" + "=" * 60)
    print("📋 VALIDATION SUMMARY")
    print("=" * 60)
    
    # Component status
    components = {
        "Imports": results.get("imports", False),
        "Server": results.get("server", {}).get("status") == "running",
        "Dashboard": results.get("dashboard", False),
        "End-to-End Test": results.get("e2e_test", {}).get("success", False),
        "Insight Generation": results.get("insights", {}).get("new_insights", 0) > 0
    }
    
    print("\n🔧 Component Status:")
    for component, status in components.items():
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {component}")
    
    # Overall status
    all_working = all(components.values())
    core_working = components["Imports"] and components["Server"] and components["End-to-End Test"]
    
    print("\n🎯 Overall Status:")
    if all_working:
        print("   ✅ ALL SYSTEMS OPERATIONAL")
        print("   🚀 ThinkingSDK is ready for comprehensive testing!")
    elif core_working:
        print("   ⚠️  CORE FUNCTIONALITY WORKING")
        print("   💡 Some components may need attention but basic functionality is available")
    else:
        print("   ❌ SYSTEM NOT READY")
        print("   🔧 Please address the failed components before proceeding")
    
    # Next steps
    print("\n💡 Next Steps:")
    
    if not components["Server"]:
        print("   1. Start the server: uvicorn thinking_sdk_server.server:app --reload --port 8000")
    
    if not components["Dashboard"]:
        print("   2. Start the dashboard: streamlit run thinking_sdk_server/dashboard.py")
    
    if not components["Insight Generation"]:
        print("   3. Check OpenAI API key: export OPENAI_API_KEY='sk-your-key-here'")
        print("   4. Review server logs for LLM processing errors")
    
    if all_working:
        print("   🧪 Run comprehensive tests: python test_scenarios.py all")
        print("   ⚡ Run performance benchmark: python benchmark.py")
        print("   📊 Monitor dashboard: http://localhost:8501")
    
    # Performance info
    if "e2e_test" in results and "stats" in results["e2e_test"]:
        stats = results["e2e_test"]["stats"]
        event_count = stats.get("instrumentation", {}).get("event_count", 0)
        if event_count > 0:
            print(f"\n📊 Test Results:")
            print(f"   Events captured: {event_count}")
            print(f"   Queue current size: {stats.get('queue', {}).get('current_size', 'N/A')}")

def main():
    """Main validation process."""
    parser = argparse.ArgumentParser(description="ThinkingSDK Setup Validation")
    parser.add_argument("--wait-for-server", action="store_true",
                       help="Wait for server to start if not running")
    parser.add_argument("--verbose", action="store_true",
                       help="Show detailed output")
    
    args = parser.parse_args()
    
    print("🔍 THINKINGSDK SETUP VALIDATION")
    print("=" * 60)
    
    results = {}
    
    # Check imports
    results["imports"] = check_imports()
    if not results["imports"]:
        print("\n❌ Cannot continue without required dependencies")
        return False
    
    # Check server
    results["server"] = check_server_connection(wait=args.wait_for_server)
    server_running = results["server"].get("status") == "running"
    
    # Check dashboard
    results["dashboard"] = check_dashboard_connection()
    
    # Run end-to-end test only if server is running
    if server_running:
        results["e2e_test"] = run_end_to_end_test(verbose=args.verbose)
        
        # Check insight generation if e2e test passed
        if results["e2e_test"].get("success"):
            results["insights"] = check_insights_generation()
    else:
        print("\n⚠️  Skipping end-to-end test (server not running)")
        results["e2e_test"] = {"success": False, "error": "server not running"}
    
    # Print final summary
    print_final_summary(results)
    
    # Return success status
    return results["imports"] and server_running and results["e2e_test"].get("success", False)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)