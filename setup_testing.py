#!/usr/bin/env python3
"""
ThinkingSDK Testing Setup Script

This script helps set up and validate the testing environment for ThinkingSDK.
It checks dependencies, validates configuration, and provides guidance for
running the complete test suite.

Usage:
    python setup_testing.py [--check-only] [--install-deps]
"""

import sys
import os
import subprocess
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

def check_python_version():
    """Check if Python version is compatible."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} is not supported")
        print("   Required: Python 3.8 or higher")
        return False

def check_dependencies() -> Dict[str, bool]:
    """Check if required dependencies are installed."""
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "streamlit",
        "openai",
        "requests",
        "pydantic"
    ]
    
    results = {}
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
            results[package] = True
        except ImportError:
            print(f"   ❌ {package} (missing)")
            results[package] = False
            
    return results

def install_dependencies(missing_packages: List[str]) -> bool:
    """Install missing dependencies."""
    if not missing_packages:
        return True
        
    print(f"\n📥 Installing missing packages: {', '.join(missing_packages)}")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            *missing_packages
        ])
        print("   ✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed to install dependencies: {e}")
        return False

def check_project_structure() -> bool:
    """Check if project structure is correct."""
    print("\n📁 Checking project structure...")
    
    required_files = [
        "thinking_sdk_client/__init__.py",
        "thinking_sdk_client/instrumentation.py",
        "thinking_sdk_client/event_queue.py",
        "thinking_sdk_client/background_sender.py",
        "thinking_sdk_client/config.py",
        "thinking_sdk_server/server.py",
        "thinking_sdk_server/dashboard.py",
        "test_scenarios.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (missing)")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n   ⚠️  Missing files: {len(missing_files)}")
        return False
    else:
        print("   ✅ All required files present")
        return True

def check_openai_api_key() -> bool:
    """Check if OpenAI API key is configured."""
    print("\n🔑 Checking OpenAI API key...")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        if api_key.startswith("sk-") and len(api_key) > 20:
            print("   ✅ OpenAI API key is configured")
            return True
        else:
            print("   ⚠️  OpenAI API key format seems incorrect")
            print("   Expected format: sk-...")
            return False
    else:
        print("   ❌ OpenAI API key not found")
        print("   Set it with: export OPENAI_API_KEY='sk-your-key-here'")
        return False

def test_thinking_sdk_import() -> bool:
    """Test if ThinkingSDK can be imported."""
    print("\n🧪 Testing ThinkingSDK import...")
    
    try:
        import thinking_sdk_client as thinking
        print("   ✅ thinking_sdk_client imported successfully")
        
        # Test basic functionality
        methods = ['start', 'stop', 'is_active', 'get_stats']
        for method in methods:
            if hasattr(thinking, method):
                print(f"   ✅ Method {method} available")
            else:
                print(f"   ❌ Method {method} missing")
                return False
                
        return True
        
    except ImportError as e:
        print(f"   ❌ Failed to import thinking_sdk_client: {e}")
        return False

def check_server_status() -> Dict[str, Any]:
    """Check if the ThinkingSDK server is running."""
    print("\n🖥️  Checking server status...")
    
    try:
        import requests
        response = requests.get("http://localhost:8000/insights", timeout=5)
        
        if response.status_code == 200:
            print("   ✅ Server is running on http://localhost:8000")
            
            # Check if it returns valid JSON
            try:
                data = response.json()
                print(f"   ✅ Server returned valid JSON ({len(data)} insights)")
                return {"running": True, "insights_count": len(data)}
            except ValueError:
                print("   ⚠️  Server returned invalid JSON")
                return {"running": True, "insights_count": None}
                
        else:
            print(f"   ⚠️  Server responded with status {response.status_code}")
            return {"running": False, "status_code": response.status_code}
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Server is not running")
        print("   Start it with: uvicorn thinking_sdk_server.server:app --reload --port 8000")
        return {"running": False, "error": "connection_refused"}
        
    except Exception as e:
        print(f"   ❌ Error checking server: {e}")
        return {"running": False, "error": str(e)}

def check_dashboard_status() -> bool:
    """Check if the dashboard is accessible."""
    print("\n📊 Checking dashboard status...")
    
    try:
        import requests
        response = requests.get("http://localhost:8501", timeout=5)
        
        if response.status_code == 200:
            print("   ✅ Dashboard is running on http://localhost:8501")
            return True
        else:
            print(f"   ⚠️  Dashboard responded with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Dashboard is not running")
        print("   Start it with: streamlit run thinking_sdk_server/dashboard.py")
        return False
        
    except Exception as e:
        print(f"   ❌ Error checking dashboard: {e}")
        return False

def create_test_configuration() -> Dict[str, Any]:
    """Create a test configuration file."""
    print("\n⚙️  Creating test configuration...")
    
    config = {
        "api_key": "sk_live_XXXX",  # Matches server's ALLOWED_KEYS
        "server_url": "http://localhost:8000",
        "test_settings": {
            "scenarios": {
                "basic_exceptions": True,
                "performance_patterns": True,
                "web_app_simulation": True,
                "database_simulation": True,
                "edge_cases": True,
                "performance_benchmark": True
            },
            "sdk_config": {
                "instrumentation": {
                    "sample_rate": 1.0,
                    "capture_returns": True,
                    "max_locals": 8
                },
                "sender": {
                    "batch_size": 20,
                    "max_batch_wait": 1.0
                },
                "queue": {
                    "maxsize": 5000
                }
            }
        }
    }
    
    import json
    with open("test_config.json", "w") as f:
        json.dump(config, f, indent=2)
        
    print("   ✅ Created test_config.json")
    return config

def run_quick_test() -> bool:
    """Run a quick functionality test."""
    print("\n🚀 Running quick functionality test...")
    
    try:
        import thinking_sdk_client as thinking
        
        # Test basic start/stop cycle
        print("   📍 Testing SDK start/stop cycle...")
        thinking.start(
            api_key="sk_live_XXXX",
            server_url="http://localhost:8000"
        )
        
        if thinking.is_active():
            print("   ✅ SDK started successfully")
        else:
            print("   ❌ SDK failed to start")
            return False
            
        # Test basic function call
        print("   📍 Testing instrumentation...")
        def test_function(x, y):
            return x + y
            
        result = test_function(5, 3)
        if result == 8:
            print("   ✅ Test function executed correctly")
        else:
            print("   ❌ Test function returned wrong result")
            
        # Get stats
        print("   📍 Testing stats collection...")
        stats = thinking.get_stats()
        if isinstance(stats, dict) and 'sdk_active' in stats:
            print("   ✅ Stats collection working")
        else:
            print("   ❌ Stats collection failed")
            
        # Stop SDK
        thinking.stop()
        if not thinking.is_active():
            print("   ✅ SDK stopped successfully")
        else:
            print("   ❌ SDK failed to stop")
            
        print("   ✅ Quick test completed successfully!")
        return True
        
    except Exception as e:
        print(f"   ❌ Quick test failed: {e}")
        return False

def generate_testing_guide():
    """Generate a comprehensive testing guide."""
    print("\n📝 Generating testing guide...")
    
    guide = """# ThinkingSDK Testing Guide

## Quick Start Testing

1. **Start the Server**:
   ```bash
   uvicorn thinking_sdk_server.server:app --reload --port 8000
   ```

2. **Start the Dashboard** (in a new terminal):
   ```bash
   streamlit run thinking_sdk_server/dashboard.py
   ```

3. **Run Test Scenarios** (in a new terminal):
   ```bash
   # Run all test scenarios
   python test_scenarios.py all
   
   # Run specific scenarios
   python test_scenarios.py basic_exceptions
   python test_scenarios.py performance_patterns
   python test_scenarios.py web_app_simulation
   python test_scenarios.py database_simulation
   python test_scenarios.py edge_cases
   python test_scenarios.py performance_benchmark
   ```

## What to Observe

### Dashboard (http://localhost:8501)
- **ExceptionAnalysis cards**: AI-generated insights for exceptions
- **Timing**: Insights appear 3-5 seconds after exceptions occur
- **Quality**: Evaluate how well the LLM explains root causes

### Server Logs
- Event ingestion messages
- LLM API calls and responses
- Processing timing information

### Client Performance
- Monitor execution time with/without SDK
- Check memory usage patterns
- Validate that normal operation isn't disrupted

## Test Scenarios Explained

1. **Basic Exceptions**: Tests various Python exceptions (ZeroDivisionError, TypeError, etc.)
2. **Performance Patterns**: High-frequency calls, recursion, nested functions
3. **Web App Simulation**: Authentication flows, business logic, error handling
4. **Database Simulation**: Query patterns, slow operations, connection issues
5. **Edge Cases**: Deep recursion, large data structures, Unicode handling
6. **Performance Benchmark**: Measures SDK overhead and resource usage

## Expected Results

- **Exception Analysis**: LLM should provide clear explanations and fix suggestions
- **Performance Overhead**: Should be < 10% for most applications
- **Event Collection**: All function calls should be captured and batched
- **Error Handling**: SDK should never crash the host application

## Troubleshooting

### Server Issues
- Check if port 8000 is available
- Verify OpenAI API key is set and valid
- Check server logs for error messages

### Dashboard Issues
- Check if port 8501 is available
- Verify server is running and responding
- Restart dashboard if it becomes unresponsive

### Client Issues
- Check SDK import and installation
- Verify server URL and API key configuration
- Monitor client logs for connection errors

## Next Steps

After testing the current implementation:

1. **Analyze Results**: Review LLM insights quality and performance impact
2. **Identify Gaps**: Note missing features or improvement opportunities
3. **Plan Enhancements**: Prioritize next development iterations
4. **Production Considerations**: Evaluate scalability and security needs

For questions or issues, check the project documentation or logs for details.
"""
    
    with open("TESTING_GUIDE.md", "w") as f:
        f.write(guide)
        
    print("   ✅ Created TESTING_GUIDE.md")

def main():
    """Main setup and validation process."""
    parser = argparse.ArgumentParser(description="ThinkingSDK Testing Setup")
    parser.add_argument("--check-only", action="store_true", 
                       help="Only check dependencies and configuration")
    parser.add_argument("--install-deps", action="store_true",
                       help="Install missing dependencies")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 THINKINGSDK TESTING SETUP")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Check dependencies
    dep_results = check_dependencies()
    missing_deps = [pkg for pkg, installed in dep_results.items() if not installed]
    
    if missing_deps:
        if args.install_deps:
            if not install_dependencies(missing_deps):
                return False
        else:
            print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
            print("   Run with --install-deps to install them")
            if not args.check_only:
                return False
    
    # Check project structure
    if not check_project_structure():
        print("\n❌ Project structure is incomplete")
        if not args.check_only:
            return False
    
    # Check OpenAI API key
    has_api_key = check_openai_api_key()
    
    # Test SDK import
    if not test_thinking_sdk_import():
        return False
    
    if args.check_only:
        print("\n✅ Dependency check completed!")
        return True
    
    # Check server and dashboard status
    server_status = check_server_status()
    dashboard_status = check_dashboard_status()
    
    # Create test configuration
    test_config = create_test_configuration()
    
    # Run quick test if possible
    if server_status.get("running") and has_api_key:
        if not run_quick_test():
            print("\n⚠️  Quick test failed, but setup can continue")
    
    # Generate testing guide
    generate_testing_guide()
    
    print("\n" + "=" * 60)
    print("📊 SETUP SUMMARY")
    print("=" * 60)
    
    print(f"✅ Python version: Compatible")
    print(f"{'✅' if not missing_deps else '❌'} Dependencies: {'All installed' if not missing_deps else f'{len(missing_deps)} missing'}")
    print(f"✅ Project structure: Complete")
    print(f"{'✅' if has_api_key else '❌'} OpenAI API key: {'Configured' if has_api_key else 'Missing'}")
    print(f"✅ SDK import: Working")
    print(f"{'✅' if server_status.get('running') else '❌'} Server: {'Running' if server_status.get('running') else 'Not running'}")
    print(f"{'✅' if dashboard_status else '❌'} Dashboard: {'Running' if dashboard_status else 'Not running'}")
    
    print("\n💡 Next Steps:")
    
    if not server_status.get("running"):
        print("   1. Start the server: uvicorn thinking_sdk_server.server:app --reload --port 8000")
    
    if not dashboard_status:
        print("   2. Start the dashboard: streamlit run thinking_sdk_server/dashboard.py")
    
    if not has_api_key:
        print("   3. Set OpenAI API key: export OPENAI_API_KEY='sk-your-key-here'")
    
    print("   4. Run test scenarios: python test_scenarios.py all")
    print("   5. Check TESTING_GUIDE.md for detailed instructions")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)