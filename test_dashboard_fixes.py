#!/usr/bin/env python3
"""
Test script to verify dashboard fixes are working correctly.

This script creates sample insights with markdown content to test the rendering.
"""

import requests
import json
import time
import sys

def create_sample_insight():
    """Create a sample insight with markdown content."""
    sample_markdown = """The runtime exceptions you've posted indicate a couple of underlying issues related to environment variables and missing configuration files in your Python application. Let's break down each of the exceptions to understand the root causes:

### Root Causes:

1. **KeyError for 'NETRC':**
   - This error occurs when the code is attempting to access an environment variable named `NETRC`, but it doesn't exist in the current environment.
   - The NETRC file typically contains login information for FTP or similar services, and its absence can lead to issues if the application relies on it for authentication.

2. **FileNotFoundError for '/Users/srikar/.netrc':**
   - This error indicates that the program tried to check for the existence of a `.netrc` file in the specified directory but couldn't find it.
   - The absence of this file leads to the first KeyError, as the program may be expecting to read credentials from it.

### Suggested Fixes:

1. **Create and Configure the .netrc File:**
   ```bash
   touch ~/.netrc
   chmod 600 ~/.netrc
   ```

2. **Set Environment Variables:**
   - Set the `NETRC` environment variable if your application requires it
   - Configure `no_proxy` and `NO_PROXY` variables as needed

3. **Code Modification:**
   ```python
   import os
   
   # Safe environment variable access
   netrc_path = os.environ.get('NETRC', '~/.netrc')
   no_proxy = os.environ.get('no_proxy', '')
   ```

> **Important:** Always use `os.environ.get()` with default values instead of direct dictionary access to avoid KeyError exceptions.

This should resolve the configuration-related issues in your application and prevent similar errors in the future."""

    return {
        "ts": time.time(),
        "pid": 12345,
        "thread": "MainThread",
        "event": "exception",
        "func": "check_netrc_config",
        "file": "config_manager.py",
        "line": 127,
        "locals": {"config_path": "/Users/srikar/.netrc", "env_var": "NETRC"},
        "exception": {
            "type": "KeyError",
            "msg": "'NETRC'",
            "traceback": [
                "  File \"config_manager.py\", line 127, in check_netrc_config",
                "    netrc_path = os.environ['NETRC']",
                "KeyError: 'NETRC'"
            ]
        }
    }

def send_sample_insight():
    """Send a sample insight to the server."""
    print("📤 Sending sample insight with markdown content...")
    
    sample_event = create_sample_insight()
    
    try:
        response = requests.post(
            "http://localhost:8000/ingest",
            json=sample_event,
            headers={"X-THINKINGSDK-KEY": "sk_live_XXXX"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Sample insight sent successfully!")
            return True
        else:
            print(f"❌ Failed to send insight: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending insight: {e}")
        return False

def check_server_status():
    """Check if the server is running."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✅ Server is healthy!")
            print(f"   OpenAI configured: {health.get('openai_configured', False)}")
            return True
        else:
            print(f"⚠️  Server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running!")
        print("   Start it with: uvicorn thinking_sdk_server.server:app --reload --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        return False

def wait_for_insights():
    """Wait for insights to be generated and check them."""
    print("\n⏳ Waiting 8 seconds for AI analysis...")
    time.sleep(8)
    
    try:
        response = requests.get("http://localhost:8000/insights", timeout=5)
        if response.status_code == 200:
            insights = response.json()
            
            if insights:
                print(f"🧠 Found {len(insights)} insights!")
                
                # Show the latest insight
                latest = insights[-1]
                print(f"\n📝 Latest insight:")
                print(f"   Type: {latest.get('kind', 'Unknown')}")
                print(f"   Time: {time.strftime('%H:%M:%S', time.localtime(latest.get('ts', 0)))}")
                
                # Show first 200 characters of content
                content = latest.get('body', 'No content')
                print(f"   Content preview: {content[:200]}...")
                
                return True
            else:
                print("ℹ️  No insights generated yet")
                return False
        else:
            print(f"❌ Failed to get insights: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting insights: {e}")
        return False

def main():
    """Main test process."""
    print("🧪 TESTING DASHBOARD FIXES")
    print("=" * 40)
    
    # Check server status
    if not check_server_status():
        return
    
    # Send sample insight
    if not send_sample_insight():
        return
    
    # Wait and check for insights
    insights_generated = wait_for_insights()
    
    print("\n" + "=" * 40)
    print("📊 TEST SUMMARY")
    print("=" * 40)
    
    if insights_generated:
        print("✅ Test completed successfully!")
        print("\n💡 Dashboard improvements to check:")
        print("   1. 🎨 Open dashboard: http://localhost:8501")
        print("   2. ✅ Check markdown rendering (headers, lists, code blocks)")
        print("   3. ✅ Verify text is readable (no dark text on dark background)")
        print("   4. ✅ Test the light theme toggle in sidebar")
        print("   5. ✅ Check text wrapping and layout")
        print("   6. ✅ Try the feedback buttons (👍👎📋)")
        print("   7. 📊 View the timeline chart")
        
        print("\n🔧 If text is still hard to read:")
        print("   - Use the '☀️ Force light theme' checkbox in sidebar")
        print("   - This will override any dark theme settings")
        
    else:
        print("⚠️  Insights not generated yet")
        print("   This might be due to:")
        print("   - OpenAI API key not configured")
        print("   - LLM processing taking longer than expected")
        print("   - Server processing issues")
        
        print("\n💡 You can still test the dashboard:")
        print("   1. Open: http://localhost:8501")
        print("   2. Check the empty state message")
        print("   3. Test the sidebar controls")

if __name__ == "__main__":
    main()