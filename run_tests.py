#!/usr/bin/env python3
"""Test runner for ThinkingSDK client tests."""

import unittest
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_all_tests():
    """Run all tests in the test suite."""
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = project_root / 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
            
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
            
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOverall result: {'PASSED' if success else 'FAILED'}")
    
    return success

def run_specific_test(test_module):
    """Run tests from a specific module."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f'tests.{test_module}')
    
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    return len(result.failures) == 0 and len(result.errors) == 0

def run_sample_data_demo():
    """Run the sample data generation demo."""
    print("Running sample data generation demo...")
    try:
        from tests.test_sample_data import SampleDataGenerator, SampleScenarios, validate_event_structure
        
        # Generate some sample events
        print("\n=== Generated Call Event ===")
        call_event = SampleDataGenerator.create_call_event("demo_function")
        print(f"Valid: {validate_event_structure(call_event)}")
        print(call_event)
        
        print("\n=== Generated Exception Event ===")
        exc_event = SampleDataGenerator.create_exception_event("DemoError", "This is a demo error")
        print(f"Valid: {validate_event_structure(exc_event)}")
        print(exc_event)
        
        print("\n=== Web Application Scenario ===")
        web_events = SampleScenarios.web_application_trace()
        print(f"Generated {len(web_events)} events:")
        for i, event in enumerate(web_events):
            print(f"  {i+1}. {event['event']}: {event.get('func', 'N/A')}")
            
        print("\nSample data generation: PASSED")
        return True
        
    except Exception as e:
        print(f"Sample data generation: FAILED - {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "all":
            success = run_all_tests()
        elif command == "sample":
            success = run_sample_data_demo()
        elif command.startswith("test_"):
            success = run_specific_test(command)
        else:
            print(f"Unknown command: {command}")
            print("Usage: python run_tests.py [all|sample|test_module_name]")
            sys.exit(1)
    else:
        # Default: run all tests
        success = run_all_tests()
    
    sys.exit(0 if success else 1)