# ThinkingSDK

**AI-powered runtime debugging that actually understands your code**

[![PyPI version](https://badge.fury.io/py/thinking-sdk-client.svg)](https://badge.fury.io/py/thinking-sdk-client)
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

ThinkingSDK is a real-time debugging assistant that captures Python application runtime events and streams them to an AI-powered analysis service for intelligent debugging insights and automated fix suggestions.

## ✨ What ThinkingSDK Does

- **Automated Root Cause Analysis** - AI explains why exceptions occurred with contextual understanding
- **Instant Fix Suggestions** - Generates concrete code fixes for common error patterns  
- **No-Repo Mode** - Works without GitHub integration for immediate debugging assistance
- **Live Insights Dashboard** - Real-time visualization of application behavior and issues
- **Zero Code Changes** - Just add `thinking.start()` to begin capturing insights
- **Production-Safe** - Lightweight instrumentation with configurable sampling

## Architecture

```
Your Python App → ThinkingSDK Client → Analysis Server → Insights Dashboard
                ↓                    ↓                 ↓
           Thin Client          AI Processing      Real-time View
         (sys.settrace)         (LLM Analysis)    (Streamlit)
```

**Thin Client**: Non-intrusive Python library that hooks into your application using `sys.settrace`
**Fat Server**: AI analysis engine with FastAPI backend and Streamlit dashboard
**Real-time Processing**: Captures events → streams to server → LLM analysis → actionable insights

## Quick Start

### 1. Start the Server

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=sk-your-openai-key

# Start the analysis server
uvicorn thinking_sdk_server.server:app --reload --port 8000

# Start the dashboard (separate terminal)
streamlit run thinking_sdk_server/dashboard.py
```

### 2. Instrument Your Code

```python
import thinking_sdk_client as thinking

# Start capturing runtime events
thinking.start(
    api_key="sk_live_your_key", 
    server_url="http://localhost:8000"
)

# Your application code runs normally
def process_data(data):
    # Any exceptions are automatically analyzed
    result = int(data)  # ValueError if data is "abc"
    return result / 0   # ZeroDivisionError

process_data("abc")  # This error gets AI analysis!
```

### 3. View AI Insights

Within ~5 seconds, check your dashboard at http://localhost:8501 to see:

- **Root Cause Analysis**: "ValueError occurred because int() cannot convert string 'abc' to integer"
- **Fix Suggestions**: "Add input validation: `if data.isdigit(): result = int(data)`"
- **Context**: Full stack trace with local variables and execution flow

## Example: Real Error Analysis

```python
import thinking_sdk_client as thinking
thinking.start(api_key="sk_live_your_key", server_url="http://localhost:8000")

def calculate_average(numbers):
    # Bug: doesn't handle empty list
    total = sum(numbers)
    return total / len(numbers)  # ZeroDivisionError when numbers is []

# ThinkingSDK automatically captures and analyzes:
calculate_average([])

# AI Analysis Result:
# 🔴 ZeroDivisionError in calculate_average at line 4
# 
# Root Cause: Division by zero occurs when len(numbers) returns 0
# The function doesn't validate that the input list is non-empty
# 
# Suggested Fix:
# if not numbers:
#     return 0  # or raise ValueError("Cannot calculate average of empty list")
# return sum(numbers) / len(numbers)
```

## Why ThinkingSDK is Needed

**Problem**: Debugging production issues is time-consuming and often requires extensive manual analysis of logs, stack traces, and code context.

**Solution**: ThinkingSDK provides:
- **Faster Debug Cycles** - Reduces time from error discovery to resolution
- **Context-Aware Analysis** - Understands your specific code patterns and variables  
- **Production-Safe** - Lightweight instrumentation with configurable sampling
- **Developer Productivity** - Turns cryptic errors into actionable explanations
- **Learning Tool** - Helps developers understand common pitfalls and best practices

## Configuration Options

### Basic Configuration

```python
thinking.start(
    api_key="sk_live_your_key",
    server_url="http://localhost:8000",
    config={
        'capture_exceptions': True,
        'capture_performance': False,
        'sample_rate': 1.0  # Capture all events
    }
)
```

### Environment Variables

```bash
export THINKINGSDK_API_KEY=sk_live_your_key
export THINKINGSDK_SERVER_URL=http://localhost:8000
export OPENAI_API_KEY=sk-your-openai-key
```

## Use Cases

### Development Debugging
```python
import thinking_sdk_client as thinking
thinking.start()

# Debug complex data processing
def process_user_data(user_input):
    # All exceptions get instant AI analysis
    cleaned = clean_data(user_input)
    validated = validate_schema(cleaned) 
    return transform_data(validated)
```

### Testing & QA
```python
# Automatically analyze test failures
def test_payment_processing():
    with thinking.context(test="payment_flow"):
        process_payment(invalid_card_data)  # AI explains why this fails
```

### Production Monitoring
```python
# Sample 10% of production traffic for analysis
thinking.start(config={'sample_rate': 0.1})

@app.route('/api/orders')
def create_order():
    # Critical path exceptions get AI analysis
    return process_order_safely()
```

## Event Flow Viewer

Access detailed event analysis at `http://localhost:8000/event-flow/{event_id}`:

- **Event Details**: Full stack trace and local variables
- **Exception Analysis**: AI-powered root cause explanation  
- **Fix Suggestions**: Concrete code improvements
- **State Transitions**: Processing workflow status

## Performance Impact

- **CPU Overhead**: <2% for typical applications
- **Memory Usage**: <10MB additional memory  
- **Network**: Batched async sending, no blocking I/O
- **Instrumentation**: Uses Python's built-in `sys.settrace` efficiently

## Security & Privacy

- **Local Processing**: Events processed on your infrastructure
- **API Key Security**: Secure token-based authentication
- **Data Control**: You control what data is captured and analyzed
- **No Code Upload**: Only runtime events are sent, never source code

## Getting Started in 30 Seconds

```bash
# Clone and set up
git clone https://github.com/your-org/thinkingsdk
cd thinkingsdk

# Set API keys  
export OPENAI_API_KEY=sk-your-openai-key

# Start server
uvicorn thinking_sdk_server.server:app --reload &
streamlit run thinking_sdk_server/dashboard.py &

# Test it
python -c "
import thinking_sdk_client as thinking
thinking.start(api_key='sk_live_test', server_url='http://localhost:8000')
int('abc')  # This error gets AI analysis!
"
```

## Target Applications

- **Web Applications** - Debug API endpoints and business logic
- **Data Pipelines** - Analyze ETL failures and data quality issues  
- **Machine Learning** - Understand model training and inference errors
- **Developer Tools** - Build smarter debugging experiences
- **Educational Code** - Help developers learn from their mistakes

---

**Built with ❤️ to make debugging intelligent**

Transform runtime errors into learning opportunities with AI-powered analysis that actually understands your code context.