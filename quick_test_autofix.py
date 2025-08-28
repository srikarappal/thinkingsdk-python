#!/usr/bin/env python3
"""
Quick test for ThinkingSDK Auto-Fix Engine MVP
==============================================

Simple test to verify the auto-fix engine works with basic scenarios.
"""

import asyncio
import sys
from pathlib import Path

# Add the server to Python path
sys.path.insert(0, str(Path(__file__).parent / "thinking_sdk_server"))

from test_auto_fix_engine import AutoFixTester

async def quick_test():
    """Run a quick test with one simple scenario."""
    print("Quick Auto-Fix Engine Test")
    print("=" * 40)
    
    tester = AutoFixTester()
    
    # Test with the simplest scenario - AttributeError
    result = await tester.test_scenario(
        scenario_name="quick_test_attribute_error",
        scenario_file_path="dummy_path.py",  # Will create a test file
        exception_type="AttributeError",
        message="'NoneType' object has no attribute 'upper'",
        line_number=3
    )
    
    print("\n" + "=" * 40)
    print("Quick Test Complete!")
    
    if result.get('success', False):
        print("Auto-Fix Engine is working!")
    else:
        print("Auto-Fix Engine has issues:")
        if 'error' in result:
            print(f"   Error: {result['error']}")
    
    return result

if __name__ == "__main__":
    asyncio.run(quick_test())
