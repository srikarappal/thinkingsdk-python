# ThinkingSDK

AI crash debugging for Python in production. One line catches every uncaught exception in your live app, ships it to ThinkingSDK's analysis service, and gives you back the root cause and a concrete fix, not just another stack trace.

[![PyPI version](https://badge.fury.io/py/thinkingsdk.svg)](https://pypi.org/project/thinkingsdk/)
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```bash
pip install thinkingsdk
```

```python
import thinkingsdk as thinking

thinking.start(api_key="sk_live_...")   # the whole integration
```

That is it. Deploy. When your app throws an unhandled exception, in a request handler, a worker thread, or a background job, ThinkingSDK captures it with full context, analyzes it, and shows you the diagnosis in your dashboard at [thinkingsdk.ai](https://thinkingsdk.ai). Get your project key there.

## What you get for every crash

- **Root cause in plain language.** Why it happened, grounded in the actual stack and the local variables at each frame, not just where it threw.
- **A concrete fix.** The specific code change to make, not a generic "handle the exception."
- **Full context.** Stack trace, locals per frame, and the execution path into the failure.
- **Smart grouping.** Repeated crashes are deduplicated, so one real bug is one issue, not a thousand alerts.

## How it works

ThinkingSDK installs exception hooks at startup:

- `sys.excepthook` for the main thread and `threading.excepthook` for worker threads, so no uncaught exception escapes unseen.
- Captured events are sent asynchronously in batches on a background sender, off your request path, so reporting a crash never blocks or slows the failing request.
- Only runtime event data leaves your process. Your source code is never uploaded.

Deeper call tracing and performance capture are available via config, off by default to keep overhead near zero.

## Performance

ThinkingSDK is built to stay off your application's hot path. The capture path is cheap and bounded; the network and the AI analysis happen elsewhere. What makes that true, in the client itself:

- All sending runs on a background daemon thread, so capturing a crash queues it in microseconds and your request path is never blocked on network or analysis.
- The in process buffer is a fixed size ring (a `deque` with `maxlen`) that drops the oldest event when full instead of applying back pressure, so a burst of errors can never stall your app or grow its memory.
- Events go out in batches (default 50, or every couple of seconds), so network cost stays flat instead of one HTTP request per event.
- A circuit breaker trips after repeated backend failures and pauses sending for a cooldown, so a slow or down analysis service cannot turn into retry pressure on your process.
- Retries use bounded attempts with exponential backoff and a hard request timeout, all confined to the background thread, never your code.
- Priority sampling always captures exceptions and errors while sampling routine, noisy events by rate, so you keep every crash without paying to ship everything.
- A deduplicator collapses repeated crashes that share a call stack signature, so a hot error loop becomes one analyzed issue rather than thousands of identical sends.
- The exception hooks sit idle until something actually throws, adding no per call or per line cost on the happy path; deeper call tracing and performance capture stay opt in.

## Framework and library integrations

Awareness for the stack you already run:

- **Web:** FastAPI, Flask, Django
- **Data:** SQLAlchemy, psycopg2, PyMongo, Redis
- **Standard library:** logging

## Production example (FastAPI)

```python
import thinkingsdk as thinking
from fastapi import FastAPI

thinking.start(api_key="sk_live_...")

app = FastAPI()

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    # If this raises in production, ThinkingSDK captures it with the request
    # context and returns an AI root cause plus a fix in your dashboard.
    return load_order(order_id)
```

When `load_order` blows up on a malformed id, you do not get a bare `KeyError` buried in your logs. You get:

```
KeyError in get_order -> load_order at order_store.py:42

Root cause: load_order indexes self._orders[order_id] directly, but order_id
arrives from the URL unvalidated, so any unknown id raises KeyError instead of
returning a 404.

Suggested fix:
    order = self._orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order
```

## Configuration

`thinking.start()` accepts:

- `api_key`: your project key from [thinkingsdk.ai](https://thinkingsdk.ai)
- `server_url`: defaults to the hosted service (`https://api.thinkingsdk.ai`); point it at your own deployment to self host
- `config`: a dict of tuning options

```python
thinking.start(
    api_key="sk_live_...",
    config={
        "capture_exceptions": True,
        "capture_performance": False,
        "sample_rate": 1.0,   # e.g. 0.1 to sample 10% on a high traffic service
    },
)
```

### Environment variables

```bash
export THINKINGSDK_API_KEY=sk_live_...
export THINKINGSDK_SERVER_URL=https://api.thinkingsdk.ai   # optional override
```

## Self hosting

The analysis service (the AI engine and dashboard) runs as a separate component. To use your own instead of the hosted service, point `server_url` at your deployment. See [thinkingsdk.ai](https://thinkingsdk.ai) for details.

## License

MIT
