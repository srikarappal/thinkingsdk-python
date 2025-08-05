# ThinkingSDK Integration Guide

This guide shows you how to integrate ThinkingSDK into your own Python projects.

## Installation Options

### Option 1: Local Development Install (Recommended)

```bash
# From the ThinkingSDK directory
pip install -e .

# Verify installation
python -c "import thinking_sdk_client; print('ThinkingSDK installed successfully!')"
```

### Option 2: Direct Path Import (Quick Testing)

```python
import sys
sys.path.append('/path/to/your/thinkingSDK/directory')
import thinking_sdk_client as thinking
```

### Option 3: Copy Client Files (Simple Projects)

Copy the entire `thinking_sdk_client/` directory into your project and import directly.

## Server Setup

### 1. Start Your ThinkingSDK Server

```bash
# Terminal 1: Start the server
cd /path/to/thinkingSDK
export OPENAI_API_KEY="sk-your-openai-key-here"
uvicorn thinking_sdk_server.server:app --reload --port 8000

# Terminal 2: Start the dashboard (optional)
streamlit run thinking_sdk_server/dashboard.py
```

### 2. Verify Server is Running

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","openai_configured":true,...}
```

## Basic Integration

### Simple Flask App Example

```python
# my_flask_app.py
from flask import Flask, request, jsonify
import thinking_sdk_client as thinking

app = Flask(__name__)

# Start ThinkingSDK when app starts
thinking.start(
    api_key="sk_live_XXXX",           # ThinkingSDK auth key (not OpenAI)
    server_url="http://localhost:8000" # Your ThinkingSDK server
)

@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    try:
        # Your business logic - will be automatically instrumented
        user = fetch_user_from_database(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        return jsonify(user)
    except Exception as e:
        # ThinkingSDK will capture this exception and analyze it
        return jsonify({"error": str(e)}), 404

def fetch_user_from_database(user_id):
    # Simulate database lookup
    if user_id == 999:
        raise ConnectionError("Database connection failed")
    elif user_id > 1000:
        return None
    else:
        return {"id": user_id, "name": f"User {user_id}"}

if __name__ == '__main__':
    try:
        app.run(debug=True)
    finally:
        # Stop ThinkingSDK when app shuts down
        thinking.stop()
```

### Django Integration Example

```python
# settings.py
import thinking_sdk_client as thinking

# Start ThinkingSDK in Django settings
thinking.start(
    api_key="sk_live_XXXX",
    server_url="http://localhost:8000",
    config={
        'instrumentation': {
            'sample_rate': 0.1,  # Sample 10% of requests in production
            'ignore_patterns': [
                r'/django/',
                r'/site-packages/',
            ]
        }
    }
)

# views.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def user_profile(request, user_id):
    try:
        # This will be automatically instrumented
        profile = get_user_profile(user_id)
        return JsonResponse(profile)
    except UserNotFound as e:
        # Exception will be captured and analyzed
        return JsonResponse({"error": str(e)}, status=404)

def get_user_profile(user_id):
    # Simulate complex business logic
    if user_id < 0:
        raise ValueError("Invalid user ID")
    
    # Simulate database operations
    user_data = database_lookup(user_id)
    enriched_data = enrich_user_data(user_data)
    
    return enriched_data

# apps.py
from django.apps import AppConfig
import thinking_sdk_client as thinking

class MyAppConfig(AppConfig):
    def ready(self):
        # Alternative: Start ThinkingSDK when Django app is ready
        pass
    
    def __del__(self):
        # Stop ThinkingSDK when Django shuts down
        thinking.stop()
```

### FastAPI Integration Example

```python
# main.py
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import thinking_sdk_client as thinking

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start ThinkingSDK
    thinking.start(
        api_key="sk_live_XXXX",
        server_url="http://localhost:8000",
        config={
            'instrumentation': {'sample_rate': 0.2}  # 20% sampling
        }
    )
    print("ThinkingSDK started")
    
    yield
    
    # Shutdown: Stop ThinkingSDK
    thinking.stop()
    print("ThinkingSDK stopped")

app = FastAPI(lifespan=lifespan)

@app.get("/api/process/{item_id}")
async def process_item(item_id: int):
    try:
        # Your business logic - automatically instrumented
        result = await complex_processing(item_id)
        return {"result": result}
    except ProcessingError as e:
        # Exception captured and sent for AI analysis
        raise HTTPException(status_code=500, detail=str(e))

async def complex_processing(item_id: int):
    # Simulate complex async operations
    if item_id == 0:
        raise ProcessingError("Cannot process item with ID 0")
    
    # Multiple function calls - all instrumented
    data = await fetch_data(item_id)
    processed = await transform_data(data)
    result = await save_result(processed)
    
    return result

class ProcessingError(Exception):
    pass
```

## Configuration Options

### Basic Configuration

```python
thinking.start(
    api_key="sk_live_XXXX",
    server_url="http://localhost:8000"
)
```

### Advanced Configuration

```python
config = {
    'instrumentation': {
        'sample_rate': 0.1,              # Sample 10% of events
        'capture_returns': False,         # Don't capture return values
        'max_locals': 3,                 # Capture max 3 local variables
        'max_local_length': 50,          # Truncate values to 50 chars
        'ignore_patterns': [             # Ignore these file patterns
            r'/venv/',
            r'/site-packages/',
            r'/my_vendor_lib/',
        ],
        'ignore_functions': [            # Ignore these function names
            '__getattr__',
            '__setattr__',
            'debug_helper',
        ]
    },
    'sender': {
        'batch_size': 50,                # Send events in batches of 50
        'max_batch_wait': 2.0,           # Wait max 2 seconds before sending
    },
    'queue': {
        'maxsize': 10000,                # Event queue size
        'drop_strategy': 'oldest'        # Drop oldest events when full
    }
}

thinking.start(
    api_key="sk_live_XXXX",
    server_url="http://localhost:8000",
    config=config
)
```

## Production Considerations

### 1. Sampling Rate

```python
# Development: Capture everything
config = {'instrumentation': {'sample_rate': 1.0}}

# Staging: Capture 50%
config = {'instrumentation': {'sample_rate': 0.5}}

# Production: Capture 5-10%
config = {'instrumentation': {'sample_rate': 0.05}}
```

### 2. Ignore Patterns

```python
config = {
    'instrumentation': {
        'ignore_patterns': [
            r'/venv/',                   # Virtual environment
            r'/site-packages/',          # Third-party packages
            r'/django/',                 # Django internals
            r'/flask/',                  # Flask internals
            r'/sqlalchemy/',             # SQLAlchemy internals
            r'/celery/',                 # Celery internals
            r'/requests/',               # Requests library
        ]
    }
}
```

### 3. Environment-Based Configuration

```python
import os

# Different config based on environment
if os.getenv('ENVIRONMENT') == 'production':
    config = {
        'instrumentation': {'sample_rate': 0.01},  # 1% in production
        'sender': {'batch_size': 100}
    }
elif os.getenv('ENVIRONMENT') == 'staging':
    config = {
        'instrumentation': {'sample_rate': 0.1},   # 10% in staging
    }
else:
    config = {
        'instrumentation': {'sample_rate': 1.0},   # 100% in development
    }

thinking.start(
    api_key=os.getenv('THINKINGSDK_API_KEY', 'sk_live_XXXX'),
    server_url=os.getenv('THINKINGSDK_URL', 'http://localhost:8000'),
    config=config
)
```

## Monitoring and Debugging

### Check SDK Status

```python
import thinking_sdk_client as thinking

# Check if SDK is active
if thinking.is_active():
    print("ThinkingSDK is running")
    
    # Get detailed statistics
    stats = thinking.get_stats()
    print(f"Events captured: {stats['instrumentation']['event_count']}")
    print(f"Queue size: {stats['queue']['current_size']}")
    print(f"Sender status: {stats['sender']['thread_alive']}")
else:
    print("ThinkingSDK is not running")
```

### Error Handling

```python
try:
    thinking.start(api_key="invalid", server_url="http://invalid:9999")
except Exception as e:
    print(f"Failed to start ThinkingSDK: {e}")
    # Your app can continue without ThinkingSDK
```

## What Gets Captured

### Automatically Captured

- ✅ **Function calls**: Entry and exit of all functions
- ✅ **Exceptions**: All exceptions with stack traces
- ✅ **Local variables**: Limited number of local vars per function
- ✅ **Thread information**: Thread names and IDs
- ✅ **Timing information**: When each event occurred

### Not Captured (By Design)

- ❌ **Passwords or secrets**: Filtered out automatically
- ❌ **Large data structures**: Truncated for performance
- ❌ **Library internals**: Ignored by default patterns
- ❌ **File contents**: Only filenames and line numbers

## Dashboard Usage

1. **Start Dashboard**: `streamlit run thinking_sdk_server/dashboard.py`
2. **Access**: http://localhost:8501
3. **View Insights**: AI-generated insights appear within 5-10 seconds of exceptions

## Troubleshooting

### Common Issues

**1. Import Error**
```
ModuleNotFoundError: No module named 'thinking_sdk_client'
```
**Solution**: Install with `pip install -e .` from ThinkingSDK directory

**2. Connection Refused**
```
requests.exceptions.ConnectionError: Connection refused
```
**Solution**: Start ThinkingSDK server first

**3. High Performance Overhead**
```
Application running slowly with ThinkingSDK
```
**Solution**: Reduce sampling rate or add ignore patterns

**4. No Insights Generated**
```
Exceptions occur but no insights appear
```
**Solution**: Check server logs and OpenAI API key

### Performance Testing

```python
# Measure performance impact
import time
import thinking_sdk_client as thinking

def benchmark_function():
    # Your code here
    return sum(range(1000))

# Test without SDK
start = time.time()
for _ in range(100):
    benchmark_function()
baseline_time = time.time() - start

# Test with SDK
thinking.start(api_key="sk_live_XXXX", server_url="http://localhost:8000")
start = time.time()
for _ in range(100):
    benchmark_function()
sdk_time = time.time() - start
thinking.stop()

overhead = ((sdk_time - baseline_time) / baseline_time) * 100
print(f"Performance overhead: {overhead:.2f}%")
```

## Next Steps

1. **Start Small**: Begin with development environment and high sampling
2. **Monitor Performance**: Use the benchmark script to measure overhead
3. **Tune Configuration**: Adjust sampling rates and ignore patterns
4. **Analyze Insights**: Review AI-generated insights for usefulness
5. **Scale Gradually**: Reduce sampling for production deployment

For questions or issues, check the server logs and dashboard for insights into what's happening.