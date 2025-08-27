# Testing ThinkingSDK Auto-Fix Engine MVP

## 🧪 Testing Strategy

The Auto-Fix Engine MVP has multiple fallback layers. Here's how to test each one:

### **Prerequisites**

1. **Set up API keys** (optional but recommended for full testing):
```bash
export OPENAI_API_KEY=sk-...           # For OpenAI GPT-4 fallback
export ANTHROPIC_API_KEY=sk-ant-...    # For Anthropic Claude fallback
```

2. **Install dependencies**:
```bash
pip install openai anthropic  # For LLM fallbacks
```

### **Test Hierarchy**

The Auto-Fix Engine tries fixes in this order:
1. **Claude Code SDK** (primary) - Direct file editing
2. **OpenAI GPT-4** (fallback 1) - If Claude SDK unavailable  
3. **Anthropic Claude** (fallback 2) - If OpenAI fails
4. **Generic templates** (last resort) - If all LLMs fail

## 🚀 How to Run Tests

### **Option 1: Quick Test (Recommended First)**

```bash
cd /Users/srikar/Library/CloudStorage/Box-Box/myprogramming/Srikara/trials/thinkingSDK

# Quick single scenario test
python3 quick_test_autofix.py
```

**Expected output:**
- Stream updates showing fix progress
- Test result (success/failure)  
- Time taken and analysis summary

### **Option 2: Full Test Suite**

```bash
# Full test with multiple scenarios
python3 test_auto_fix_engine.py
```

**Expected output:**
- Tests 3 scenarios: AttributeError, UnboundLocalError, IndexError
- Detailed results for each scenario
- Success rate summary
- Results saved to `auto_fix_test_results.json`

### **Option 3: Manual Testing**

Create a simple test case manually:

```python
# test_manual.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "thinking_sdk_server"))

from test_auto_fix_engine import AutoFixTester

async def test_custom_scenario():
    tester = AutoFixTester()
    
    # Test your own scenario
    result = await tester.test_scenario(
        scenario_name="my_test",
        scenario_file_path="/path/to/your/buggy/file.py",
        exception_type="YourExceptionType", 
        message="Your exception message",
        line_number=10
    )
    
    print(f"Result: {result}")

asyncio.run(test_custom_scenario())
```

## 🔍 What to Look For

### **Success Indicators**
- ✅ Stream updates appear (showing fix progress)
- ✅ Final status starts with "completed" 
- ✅ No Python exceptions thrown
- ✅ Temporary workspace cleaned up

### **Expected Behaviors**

#### **With API Keys Available:**
```
🔑 Available LLM APIs: OpenAI, Anthropic
📡 Stream Update: initializing - Starting MVP auto-fix...
📡 Stream Update: creating_workspace - Creating workspace...
📡 Stream Update: cloning_repo - Preparing repository...
📡 Stream Update: analyzing_code - Analyzing exception...
📡 Stream Update: applying_fix - Using LLM fallback for AttributeError...
📡 Stream Update: validating_fix - Validating fix...
✅ Scenario quick_test: completed_partial
```

#### **Without API Keys:**
```
⚠️ No LLM API keys found - will test generic fallback only
📡 Stream Update: applying_fix - Using generic fallback...
✅ Scenario quick_test: completed_partial
```

## 🐛 Troubleshooting

### **Common Issues**

1. **"Module not found" errors:**
```bash
# Make sure you're in the right directory
cd /Users/srikar/Library/CloudStorage/Box-Box/myprogramming/Srikara/trials/thinkingSDK

# Check Python path
python3 -c "import sys; print(sys.path)"
```

2. **Virtual environment creation fails:**
```bash
# Check Python venv module
python3 -m venv test_venv
# If fails, install python3-venv (Linux) or update Python
```

3. **API key errors:**
```bash
# Test your API keys work
python3 -c "import openai; print('OpenAI OK')"
python3 -c "import anthropic; print('Anthropic OK')"
```

4. **Permission errors on temp directories:**
```bash
# Check temp directory permissions
ls -la /tmp/
# Clean up old temp directories if needed
rm -rf /tmp/thinkingsdk_*
rm -rf /tmp/test_repo_*
```

### **Debug Mode**

For more detailed output, modify the test scripts:

```python
# In test_auto_fix_engine.py, change logging level:
logging.basicConfig(level=logging.DEBUG)

# Or add more verbose output:
print(f"🔍 Debug: {update}")  # In stream_update_handler
```

## 📊 Understanding Test Results

### **Test Result Structure**
```json
{
  "scenario": "scenario_name",
  "final_status": "completed_partial|completed_with_validation|failed",
  "tests_passed": true|false,
  "stream_updates_count": 6,
  "completion_time": 45,
  "claude_analysis": "Fix analysis text...",
  "success": true|false
}
```

### **Status Meanings**
- **`completed_with_validation`**: Fix applied and validated successfully
- **`completed_partial`**: Fix applied but validation inconclusive  
- **`failed`**: Fix process failed completely

### **Success Criteria**
- ✅ `success: true` - Fix process completed without errors
- ✅ `stream_updates_count > 0` - Progress updates were sent
- ✅ `completion_time < 300` - Finished within timeout
- ✅ `claude_analysis` contains meaningful text

## 🎯 Next Steps

### **If Tests Pass:**
1. Try with real exception scenarios from your test suite
2. Test with different exception types
3. Integrate into ThinkingSDK server for live testing

### **If Tests Fail:**
1. Check the error messages in test results
2. Verify API keys and dependencies
3. Run individual components manually
4. Check logs for detailed error information

### **Performance Testing**
```bash
# Test with multiple concurrent fixes
python3 -c "
import asyncio
from test_auto_fix_engine import AutoFixTester

async def load_test():
    tester = AutoFixTester()
    tasks = []
    for i in range(5):
        task = tester.test_scenario(f'load_test_{i}', 'dummy.py', 'AttributeError', 'test', 1)
        tasks.append(task)
    results = await asyncio.gather(*tasks)
    print(f'Completed {len(results)} concurrent tests')

asyncio.run(load_test())
"
```

This testing guide provides multiple ways to validate the Auto-Fix Engine MVP at different levels of complexity!