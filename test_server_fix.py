#!/usr/bin/env python3
"""
Quick test to verify server fixes are working.
Run this after starting the fixed server.
"""

import requests
import time
import json

def test_server_health():
    """Test the health endpoint."""
    print("🏥 Testing server health...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            print("   ✅ Server is healthy!")
            print(f"   📊 OpenAI configured: {health_data.get('openai_configured', False)}")
            print(f"   📊 Events in buffer: {health_data.get('events_in_buffer', 0)}")
            print(f"   📊 Total insights: {health_data.get('total_insights', 0)}")
            return True
        else:
            print(f"   ❌ Health check failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False

def test_insights_endpoint():
    """Test the insights endpoint."""
    print("\n🧠 Testing insights endpoint...")
    
    try:
        response = requests.get("http://localhost:8000/insights", timeout=5)
        
        if response.status_code == 200:
            insights = response.json()
            print(f"   ✅ Insights endpoint working! ({len(insights)} insights)")
            
            if insights:
                latest = insights[-1]
                print(f"   📝 Latest insight: {latest.get('kind', 'unknown')} at {latest.get('ts', 'unknown')}")
            else:
                print("   📝 No insights yet (this is normal for a fresh start)")
            return True
        else:
            print(f"   ❌ Insights endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Insights endpoint failed: {e}")
        return False

def test_basic_ingestion():
    """Test basic event ingestion."""
    print("\n📥 Testing event ingestion...")
    
    test_event = {
        "ts": time.time(),
        "pid": 12345,
        "thread": "MainThread",
        "event": "exception",
        "func": "test_function",
        "file": "test.py",
        "line": 42,
        "locals": {"x": "10", "y": "0"},
        "exception": {
            "type": "ZeroDivisionError",
            "msg": "division by zero",
            "traceback": ["  File \"test.py\", line 42, in test_function", "    return x / y", "ZeroDivisionError: division by zero"]
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/ingest",
            json=test_event,
            headers={"X-THINKINGSDK-KEY": "sk_live_XXXX"},
            timeout=5
        )
        
        if response.status_code == 200:
            print("   ✅ Event ingestion working!")
            
            # Wait a bit and check if insight was generated
            print("   ⏳ Waiting 5 seconds for insight generation...")
            time.sleep(5)
            
            # Check insights again
            insights_response = requests.get("http://localhost:8000/insights", timeout=5)
            if insights_response.status_code == 200:
                insights = insights_response.json()
                if len(insights) > 0:
                    latest = insights[-1]
                    print(f"   🎉 New insight generated!")
                    print(f"   📝 Type: {latest.get('kind', 'unknown')}")
                    print(f"   💬 Content: {latest.get('body', 'no content')[:100]}...")
                else:
                    print("   ⚠️  No insight generated yet (may take longer)")
            
            return True
        else:
            print(f"   ❌ Event ingestion failed with status {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Event ingestion failed: {e}")
        return False

def main():
    """Run all server tests."""
    print("🔧 TESTING SERVER FIXES")
    print("=" * 40)
    
    # Test health
    health_ok = test_server_health()
    
    # Test insights endpoint
    insights_ok = test_insights_endpoint()
    
    # Test ingestion (only if basic endpoints work)
    if health_ok and insights_ok:
        ingestion_ok = test_basic_ingestion()
    else:
        print("\n⚠️  Skipping ingestion test due to basic endpoint failures")
        ingestion_ok = False
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 TEST SUMMARY")
    print("=" * 40)
    
    print(f"✅ Health endpoint: {'PASS' if health_ok else 'FAIL'}")
    print(f"✅ Insights endpoint: {'PASS' if insights_ok else 'FAIL'}")
    print(f"✅ Event ingestion: {'PASS' if ingestion_ok else 'FAIL'}")
    
    if health_ok and insights_ok and ingestion_ok:
        print("\n🎉 ALL TESTS PASSED!")
        print("The server fixes are working correctly.")
        print("You can now run: python validate_setup.py --verbose")
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("Check the server logs for error messages.")
        
        if not health_ok:
            print("- Health endpoint issue: Server may not be running properly")
        if not insights_ok:
            print("- Insights endpoint issue: API routing problem")
        if not ingestion_ok:
            print("- Ingestion issue: Event processing or OpenAI integration problem")

if __name__ == "__main__":
    main()