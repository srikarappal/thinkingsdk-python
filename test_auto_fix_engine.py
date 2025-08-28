#!/usr/bin/env python3
"""
Test suite for ThinkingSDK Auto-Fix Engine MVP
==============================================

This script tests the auto-fix engine with real exception scenarios.
It uses the existing test scenarios from thinkingsdk_testing directory.
"""

import os
import sys
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Add the server to Python path
sys.path.insert(0, str(Path(__file__).parent / "thinking_sdk_server"))

from thinking_sdk_server.auto_fix_engine import AutoFixEngine, FixStage
# Note: Using mock database for testing, not importing DatabaseOperations

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autofix_test")

class MockDatabase:
    """Mock database for testing purposes."""
    
    def __init__(self):
        self.fix_attempts = {}
        self.debug_steps = {}
        
    async def create_fix_attempt(self, org_id, event_id, exception_data, repository_url):
        fix_id = f"fix_{len(self.fix_attempts) + 1}"
        fix_attempt = {
            'id': fix_id,
            'org_id': org_id,
            'event_id': event_id,
            'exception_data': exception_data,
            'repository_url': repository_url,
            'status': 'initializing',
            'created_at': datetime.utcnow()
        }
        self.fix_attempts[fix_id] = fix_attempt
        return fix_attempt
    
    async def update_fix_attempt_status(self, fix_attempt_id, status, claude_analysis=None, tests_passed=False, debug_results=None):
        if fix_attempt_id in self.fix_attempts:
            self.fix_attempts[fix_attempt_id].update({
                'status': status,
                'claude_analysis': claude_analysis,
                'tests_passed': tests_passed,
                'debug_results': debug_results,
                'updated_at': datetime.utcnow()
            })
    
    async def create_debug_step(self, fix_attempt_id, description, step_number):
        step_id = f"step_{fix_attempt_id}_{step_number}"
        self.debug_steps[step_id] = {
            'id': step_id,
            'fix_attempt_id': fix_attempt_id,
            'description': description,
            'step_number': step_number,
            'status': 'pending'
        }
        return step_id
    
    async def update_debug_step(self, step_id, status, metadata=None):
        if step_id in self.debug_steps:
            self.debug_steps[step_id].update({
                'status': status,
                'metadata': metadata
            })

class AutoFixTester:
    """Test harness for the Auto-Fix Engine."""
    
    def __init__(self):
        self.db = MockDatabase()
        self.stream_updates = []
        self.test_results = {}
        
        # Set up auto-fix engine with stream handler
        self.engine = AutoFixEngine(db=self.db, stream_handler=self.stream_update_handler)
    
    async def stream_update_handler(self, update):
        """Handle streaming updates from auto-fix engine."""
        self.stream_updates.append(update)
        print(f"Stream Update: {update['stage']} - {update['message']}")
    
    def create_test_exception_event(self, scenario_name, exception_type, message, file_path, line_number):
        """Create a mock exception event for testing."""
        return {
            'id': f'event_{scenario_name}',
            'timestamp': datetime.utcnow().isoformat(),
            'exception': {
                'type': exception_type,
                'message': message,
                'structured_traceback': [
                    {
                        'file_path': file_path,
                        'line': line_number,
                        'function': 'test_function',
                        'locals': {'test_var': 'test_value'}
                    }
                ]
            },
            'scenario': scenario_name
        }
    
    def create_test_repository(self, scenario_file_path):
        """Create a temporary test repository with the scenario file."""
        temp_repo = Path(tempfile.mkdtemp(prefix="test_repo_"))
        
        # Copy the scenario file to the temp repo and return the actual file created
        if Path(scenario_file_path).exists():
            dest_file = temp_repo / Path(scenario_file_path).name
            shutil.copy2(scenario_file_path, dest_file)
            actual_file = dest_file
        else:
            # Create a simple test file if scenario doesn't exist
            test_file = temp_repo / "test_scenario.py"
            test_file.write_text("""
def problematic_function():
    data = None
    return data.upper()  # This will cause AttributeError

if __name__ == "__main__":
    problematic_function()
""")
            actual_file = test_file
        
        return f"file://{temp_repo}", str(actual_file)
    
    async def test_scenario(self, scenario_name, scenario_file_path, exception_type, message, line_number=1):
        """Test auto-fix engine with a specific scenario."""
        print(f"\n Testing scenario: {scenario_name}")
        print(f"   File: {scenario_file_path}")
        print(f"   Exception: {exception_type}: {message}")
        
        # Create test repository and get the actual file path in the temp repo
        repo_url, actual_file_path = self.create_test_repository(scenario_file_path)
        
        # Create exception event with the actual file path in the temp repo
        exception_event = self.create_test_exception_event(
            scenario_name, exception_type, message, actual_file_path, line_number
        )
        
        # Clear previous stream updates
        self.stream_updates = []
        
        try:
            # Trigger auto-fix
            fix_attempt_id = await self.engine.trigger_auto_fix(
                org_id="test_org",
                repo_url=repo_url,
                exception_event=exception_event
            )
            
            # Wait for fix to complete (with timeout)
            max_wait_time = 300  # 5 minutes
            wait_interval = 2    # Check every 2 seconds
            
            elapsed = 0
            while elapsed < max_wait_time:
                fix_attempt = self.db.fix_attempts.get(fix_attempt_id)
                if fix_attempt and fix_attempt['status'] in ['completed_with_pr', 'completed_partial', 'completed_no_pr', 'failed']:
                    break
                    
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval
                print(f"⏳ Waiting for fix completion... ({elapsed}s elapsed)")
            
            # Collect results
            final_fix_attempt = self.db.fix_attempts.get(fix_attempt_id, {})
            
            result = {
                'scenario': scenario_name,
                'fix_attempt_id': fix_attempt_id,
                'final_status': final_fix_attempt.get('status', 'unknown'),
                'tests_passed': final_fix_attempt.get('tests_passed', False),
                'stream_updates_count': len(self.stream_updates),
                'completion_time': elapsed,
                'claude_analysis': final_fix_attempt.get('claude_analysis', ''),
                'debug_results': final_fix_attempt.get('debug_results', {}),
                'success': final_fix_attempt.get('status', '').startswith('completed')
            }
            
            self.test_results[scenario_name] = result
            
            # Print results
            status_emoji = "✅" if result['success'] else "❌"
            print(f"{status_emoji} Scenario {scenario_name}: {result['final_status']}")
            print(f"   Stream updates: {result['stream_updates_count']}")
            print(f"   Completion time: {result['completion_time']}s")
            print(f"   Tests passed: {result['tests_passed']}")
            
            if result['claude_analysis']:
                print(f"   Analysis: {result['claude_analysis'][:100]}...")
            
            return result
            
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            self.test_results[scenario_name] = {
                'scenario': scenario_name,
                'error': str(e),
                'success': False
            }
            return self.test_results[scenario_name]
        
        finally:
            # Cleanup temporary repository
            try:
                repo_path = repo_url.replace('file://', '')
                if Path(repo_path).exists():
                    shutil.rmtree(repo_path)
            except Exception as e:
                print(f"⚠️  Cleanup warning: {e}")
    
    async def run_basic_tests(self):
        """Run basic auto-fix engine tests."""
        print("Starting Auto-Fix Engine MVP Tests")
        print("=" * 50)
        
        # Test scenarios based on existing test cases
        test_cases = [
            {
                'name': 'attribute_error_none',
                'file': '/Users/srikar/Library/CloudStorage/Box-Box/myprogramming/Srikara/trials/py_errors_public/basic_errors/nonetype_attribute_error_scenario.py',
                'exception_type': 'AttributeError', 
                'message': "'NoneType' object has no attribute 'upper'",
                'line': 12
            },
            {
                'name': 'unbound_local_variable',
                'file': '/Users/srikar/Library/CloudStorage/Box-Box/myprogramming/Srikara/trials/py_errors_public/basic_errors/unbound_local_variable_scenario.py',
                'exception_type': 'UnboundLocalError',
                'message': "local variable 'x' referenced before assignment", 
                'line': 16
            },
            {
                'name': 'index_error',
                'file': '/Users/srikar/Library/CloudStorage/Box-Box/myprogramming/Srikara/trials/py_errors_public/basic_errors/array_index_out_of_bounds_scenario.py',
                'exception_type': 'IndexError',
                'message': 'list index out of range',
                'line': 6
            }
        ]
        
        # Run each test case
        for test_case in test_cases:
            await self.test_scenario(
                test_case['name'],
                test_case['file'], 
                test_case['exception_type'],
                test_case['message'],
                test_case['line']
            )
        
        # Print summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "=" * 50)
        print("📊 AUTO-FIX ENGINE TEST SUMMARY")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        print(f"Total tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        print(f"Success rate: {(successful_tests / total_tests * 100):.1f}%" if total_tests > 0 else "N/A")
        
        print("\nDetailed Results:")
        for scenario, result in self.test_results.items():
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            print(f"  {status} {scenario}")
            
            if not result.get('success', False) and 'error' in result:
                print(f"    Error: {result['error']}")
            elif result.get('success', False):
                print(f"    Status: {result.get('final_status', 'unknown')}")
                print(f"    Time: {result.get('completion_time', 0)}s")
        
        # Save results to file
        results_file = Path(__file__).parent / "auto_fix_test_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.utcnow().isoformat(),
                'summary': {
                    'total_tests': total_tests,
                    'successful_tests': successful_tests,
                    'success_rate': (successful_tests / total_tests * 100) if total_tests > 0 else 0
                },
                'results': self.test_results
            }, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: {results_file}")

async def main():
    """Main test execution."""
    print("ThinkingSDK Auto-Fix Engine MVP Test Suite")
    print("==========================================")
    print("Testing with LLM fallback system")
    
    # Check for API keys
    api_keys_available = []
    if os.getenv('OPENAI_API_KEY'):
        api_keys_available.append('OpenAI')
    if os.getenv('ANTHROPIC_API_KEY'):
        api_keys_available.append('Anthropic')
    
    if api_keys_available:
        print(f"🔑 Available LLM APIs: {', '.join(api_keys_available)}")
    else:
        print("⚠️  No LLM API keys found - will test generic fallback only")
        print("   Set OPENAI_API_KEY or ANTHROPIC_API_KEY for full testing")
    
    # Run tests
    tester = AutoFixTester()
    await tester.run_basic_tests()

if __name__ == "__main__":
    asyncio.run(main())
