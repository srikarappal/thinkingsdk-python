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

## Overhead and safety

- Exception hooks are effectively free until something actually throws.
- Reports are batched and delivered on a background sender, never on the hot path.
- `sample_rate` bounds volume on high traffic services.
- No source code is sent: only the runtime event data you choose to capture.

## Self hosting

The analysis service (the AI engine and dashboard) runs as a separate component. To use your own instead of the hosted service, point `server_url` at your deployment. See [thinkingsdk.ai](https://thinkingsdk.ai) for details.

## License

MIT
