# ThinkingSDK Testing Guide

This comprehensive guide walks you through testing the current ThinkingSDK implementation and helps you evaluate its capabilities and performance.

## Quick Start

### 1. Setup and Dependencies

```bash
# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key (required for LLM analysis)
export OPENAI_API_KEY="sk-your-actual-openai-key-here"

# Validate setup
python validate_setup.py --wait-for-server --verbose
```

### 2. Start the System

**Terminal 1 - Server:**
```bash
uvicorn thinking_sdk_server.server:app --reload --port 8000
```

**Terminal 2 - Dashboard:**
```bash
streamlit run thinking_sdk_server/dashboard.py
```

**Terminal 3 - Testing:**
```bash
# Run all test scenarios
python test_scenarios.py all

# Or run specific scenarios
python test_scenarios.py basic_exceptions
```

## Available Testing Scripts

### 1. `setup_testing.py` - Environment Setup
Validates dependencies, project structure, and configuration.

```bash
# Check dependencies only
python setup_testing.py --check-only

# Install missing dependencies
python setup_testing.py --install-deps
```

### 2. `validate_setup.py` - System Validation
Runs end-to-end validation of the complete system.

```bash
# Quick validation
python validate_setup.py

# Wait for server and show detailed output
python validate_setup.py --wait-for-server --verbose
```

### 3. `test_scenarios.py` - Comprehensive Testing
Provides various testing scenarios to validate SDK functionality.

```bash
# Run all scenarios
python test_scenarios.py all

# Available individual scenarios:
python test_scenarios.py basic_exceptions      # Exception handling
python test_scenarios.py performance_patterns  # High-frequency calls
python test_scenarios.py web_app_simulation   # Web application workflow
python test_scenarios.py database_simulation  # Database operations
python test_scenarios.py edge_cases          # Edge cases and error conditions
python test_scenarios.py performance_benchmark # Performance measurement
```

### 4. `benchmark.py` - Performance Analysis
Measures SDK performance impact and overhead.

```bash
# Standard benchmark
python benchmark.py

# Detailed benchmark with memory analysis
python benchmark.py --iterations=100 --detailed --memory

# Save results to file
python benchmark.py --save=my_benchmark.json
```

## Testing Scenarios Explained

### 1. Basic Exceptions (`basic_exceptions`)
Tests various Python exception types to validate LLM analysis:
- **ZeroDivisionError**: Division by zero scenarios
- **TypeError**: Type mismatch operations  
- **KeyError**: Missing dictionary keys
- **IndexError**: List index out of range
- **ValueError**: Invalid value conversions
- **Nested Exceptions**: Multi-level exception propagation

**Expected Results**: Each exception should appear in the dashboard within 5-10 seconds with AI-generated explanations.

### 2. Performance Patterns (`performance_patterns`)
Tests high-frequency operations and batching behavior:
- **High-frequency calls**: 50+ function calls in rapid succession
- **Recursive functions**: Fibonacci calculations with moderate depth
- **Nested functions**: Multi-level function call hierarchies
- **Batch processing**: Tests event queue batching and transmission

**Expected Results**: Should handle high call volumes without significant performance degradation.

### 3. Web Application Simulation (`web_app_simulation`)
Simulates realistic web application workflows:
- **User authentication**: Login flows with success/failure scenarios
- **Database interactions**: User profile fetching with error handling
- **Business logic**: Role-based permission processing
- **Request processing**: Complete request lifecycle simulation

**Expected Results**: Captures complex application flows and provides insights into authentication failures.

### 4. Database Simulation (`database_simulation`)
Simulates common database operation patterns:
- **Connection management**: Connection creation and cleanup
- **Query execution**: Fast and slow query patterns
- **Error scenarios**: Connection failures and timeouts
- **N+1 problems**: Inefficient query pattern detection

**Expected Results**: Identifies database performance issues and connection problems.

### 5. Edge Cases (`edge_cases`)
Tests unusual scenarios and error conditions:
- **Deep recursion**: Moderate recursion depth testing
- **Large data structures**: Processing of large lists and dictionaries
- **Unicode handling**: International character processing
- **Multiple exception types**: Sequential different exception types

**Expected Results**: Handles edge cases gracefully without SDK crashes.

### 6. Performance Benchmark (`performance_benchmark`)
Measures actual SDK performance impact:
- **Baseline measurement**: Code execution without SDK
- **SDK overhead**: Same code with SDK instrumentation
- **Statistical analysis**: Mean, median, standard deviation
- **Throughput analysis**: Function calls per second

**Expected Results**: Should show < 15% overhead for most applications.

## What to Observe

### Dashboard Monitoring (http://localhost:8501)

**ExceptionAnalysis Cards**: Look for AI-generated insights that appear 3-5 seconds after exceptions occur.

**Quality Indicators**:
- ✅ **Good**: Clear root cause explanation with specific fix suggestions
- ⚠️ **Moderate**: Generic explanation without specific context
- ❌ **Poor**: Incorrect analysis or no meaningful insights

**Example Good Insight**:
```
14:32:05 – ExceptionAnalysis
The ValueError occurs in test_key_error() when trying to access 
user_data["age"] but the dictionary only contains "name" and "email" 
keys. To fix this, either add the "age" key to the dictionary or 
use user_data.get("age", default_value) for safe access.
```

### Server Logs

Monitor the server terminal for:
- **Event ingestion**: `POST /ingest` requests from client
- **LLM processing**: OpenAI API calls and responses
- **Error messages**: Connection issues or processing failures
- **Timing information**: Event processing delays

### Client Performance

Watch for:
- **Response times**: Application should remain responsive
- **Memory usage**: No significant memory leaks
- **Error handling**: SDK errors shouldn't crash your application
- **Batch efficiency**: Events should be sent in batches, not individually

## Performance Benchmarking

### Understanding Benchmark Results

```bash
python benchmark.py --iterations=50 --detailed
```

**Key Metrics**:
- **Mean Overhead**: Average performance impact (target: < 10%)
- **Median Overhead**: More robust measure of typical impact
- **Standard Deviation**: Consistency of performance impact
- **Throughput**: Function calls per second comparison

**Performance Assessment**:
- **< 5% overhead**: Excellent - negligible impact
- **5-15% overhead**: Good - acceptable for most applications  
- **15-30% overhead**: Moderate - consider sampling rate reduction
- **> 30% overhead**: High - investigate configuration issues

### Optimization Tips

If performance overhead is high:

1. **Reduce sampling rate**:
   ```python
   config = {'instrumentation': {'sample_rate': 0.1}}  # Sample 10% of events
   ```

2. **Increase batch size**:
   ```python
   config = {'sender': {'batch_size': 100, 'max_batch_wait': 5.0}}
   ```

3. **Disable return value capture**:
   ```python
   config = {'instrumentation': {'capture_returns': False}}
   ```

4. **Add ignore patterns**:
   ```python
   config = {'instrumentation': {'ignore_patterns': [r'/my_heavy_module/']}}
   ```

## Troubleshooting

### Common Issues

**1. Server Connection Refused**
```
❌ Server not running on port 8000
```
**Solution**: Start server with `uvicorn thinking_sdk_server.server:app --reload --port 8000`

**2. OpenAI API Errors**
```
❌ OpenAI API key not found
```
**Solution**: Set environment variable `export OPENAI_API_KEY="sk-your-key-here"`

**3. No Insights Generated**
```
⚠️ No new insights generated
```
**Possible causes**:
- OpenAI API key invalid or out of credits
- Server not processing exceptions (check server logs)
- Events not reaching server (check client configuration)

**4. Import Errors**
```
❌ thinking_sdk_client not found
```
**Solution**: Install dependencies with `pip install -r requirements.txt`

**5. High Performance Overhead**
```
📈 Performance overhead: +45.2%
```
**Solutions**:
- Reduce sampling rate: `{'instrumentation': {'sample_rate': 0.1}}`
- Add ignore patterns for heavy modules
- Increase batch sizes to reduce network overhead

### Debugging Steps

1. **Validate setup**: `python validate_setup.py --verbose`
2. **Check server logs**: Look for error messages in server terminal
3. **Test basic functionality**: `python test_scenarios.py basic_exceptions`
4. **Check dashboard**: Verify insights appear at http://localhost:8501
5. **Review configuration**: Ensure API keys and URLs are correct

## Advanced Testing

### Custom Test Scenarios

Create your own test scenarios by following this pattern:

```python
import thinking_sdk_client as thinking

# Start SDK with custom configuration
thinking.start(
    api_key="sk_live_XXXX",
    server_url="http://localhost:8000",
    config={
        'instrumentation': {
            'sample_rate': 1.0,
            'capture_returns': True,
            'ignore_patterns': [r'/my_vendor_libs/']
        }
    }
)

# Your application code here
def my_test_function():
    # This will be instrumented
    result = complex_business_logic()
    return result

# Generate events
my_test_function()

# Wait for processing
import time
time.sleep(5)

# Stop SDK
thinking.stop()
```

### Integration with Real Applications

To test ThinkingSDK with your actual application:

1. **Add minimal instrumentation**:
   ```python
   import thinking_sdk_client as thinking
   
   # At application startup
   thinking.start(
       api_key="sk_live_XXXX",
       server_url="http://localhost:8000",
       config={'instrumentation': {'sample_rate': 0.1}}  # Sample 10%
   )
   
   # Your existing application code - no changes needed
   
   # At application shutdown
   thinking.stop()
   ```

2. **Monitor carefully**: Start with low sampling rates and increase gradually
3. **Use ignore patterns**: Exclude vendor libraries and framework internals
4. **Test thoroughly**: Validate that your application behavior is unchanged

## Expected Timeline

**Full testing process typically takes**:
- **Setup and validation**: 5-10 minutes
- **Basic scenarios**: 10-15 minutes  
- **Performance benchmarking**: 5-10 minutes
- **Custom integration testing**: 15-30 minutes
- **Analysis and evaluation**: 15-30 minutes

**Total time**: 1-2 hours for comprehensive evaluation

## Success Criteria

**✅ System is working correctly if**:
- All test scenarios complete without errors
- Exceptions generate meaningful AI insights within 10 seconds
- Performance overhead is < 15% for your use case
- Dashboard shows live insights with good explanations
- No application crashes or unexpected behavior

**🎯 Ready for production evaluation if**:
- Performance overhead is < 5% with appropriate sampling
- AI insights provide actionable debugging information
- System handles edge cases gracefully
- Integration doesn't disrupt existing application behavior

## Next Steps

After successful testing:

1. **Evaluate insight quality**: Are the AI explanations helpful for debugging?
2. **Assess performance impact**: Is the overhead acceptable for your use case?
3. **Consider production deployment**: Start with low sampling rates
4. **Plan enhancements**: Identify features needed for your specific requirements
5. **Integration strategy**: Determine how to incorporate into your development workflow

For questions or issues during testing, check the server logs and client configuration first, then refer to this guide's troubleshooting section.