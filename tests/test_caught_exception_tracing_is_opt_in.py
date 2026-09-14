"""A raise is not a crash, so the SDK must not trace one by default (issue #20).

sys.monitoring.events.RAISE fires on EVERY raise. Real code raises constantly without anything
going wrong: any() short-circuiting closes a generator (GeneratorExit), SQLAlchemy's type cache uses
try/except KeyError as its miss path, every iterator ends with StopIteration. Subscribing to all of
it measured 2703x on caught exceptions and cost one real FastAPI request 5.2s for 981 raises and
zero errors.

What must stay true:
  - by default, nothing is traced and a caught exception costs the host application nothing
  - by default, an UNHANDLED exception is still captured, with its traceback, in full
  - opting in restores the old behaviour for users who want caught-exception telemetry
"""
import logging
import sys
import time

import pytest

from thinkingsdk.config import Config
from thinkingsdk.instrumentation import RuntimeInstrumentation


class _Queue:
    def __init__(self):
        self.events = []

    def push(self, event):
        self.events.append(event)

    def put(self, event, *args, **kwargs):
        self.events.append(event)

    def add_event(self, event, *args, **kwargs):
        self.events.append(event)

    def enqueue(self, event, *args, **kwargs):
        self.events.append(event)


def _build(**config):
    queue = _Queue()
    inst = RuntimeInstrumentation(queue, config)
    return inst, queue


def _teardown(inst):
    try:
        inst.cleanup_hooks()
    except Exception:
        pass
    sys.settrace(None)


@pytest.fixture
def default():
    inst, queue = _build()
    yield inst, queue
    _teardown(inst)


@pytest.fixture
def opted_in():
    inst, queue = _build(capture_caught_exceptions=True)
    yield inst, queue
    _teardown(inst)


def test_default_config_does_not_trace_caught_exceptions():
    """The default is the whole fix. Flip this and every host application pays again."""
    assert Config().get("instrumentation", "capture_caught_exceptions") is False


def test_no_hook_is_installed_by_default(default):
    inst, _ = default
    inst.setup_hooks()
    assert inst._monitoring_tool_id is None, "subscribed to RAISE without being asked"
    assert sys.gettrace() is None, "installed a settrace hook without being asked"


def test_excepthooks_are_installed_by_default(default):
    """The crash path is NOT optional. Turning the tracer off must not turn crash reporting off."""
    inst, _ = default
    original_sys, original_thread = sys.excepthook, __import__("threading").excepthook
    inst.setup_hooks()
    assert sys.excepthook is not original_sys, "sys.excepthook was not installed"
    assert __import__("threading").excepthook is not original_thread, (
        "threading.excepthook was not installed"
    )


def test_caught_exception_is_not_captured_by_default(default, tmp_path):
    """A KeyError used as a cache-miss path is not an error and must not reach the queue."""
    module = tmp_path / "cache_miss_mod.py"
    module.write_text(
        "def lookup(cache, key):\n"
        "    try:\n"
        "        return cache[key]\n"
        "    except KeyError:\n"
        "        cache[key] = len(key)\n"
        "        return cache[key]\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        import cache_miss_mod

        inst, queue = default
        inst.setup_hooks()
        cache = {}
        for i in range(50):
            cache_miss_mod.lookup(cache, f"key_{i}")

        assert queue.events == [], f"captured {len(queue.events)} events for zero errors"
        assert inst._last_captured_exception is None
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("cache_miss_mod", None)


def test_unhandled_exception_is_still_captured_by_default(default, tmp_path):
    """THE safety test. With the tracer off, a real crash must still be reported in full, because
    the excepthook is the crash path and it is always installed."""
    module = tmp_path / "crash_mod.py"
    module.write_text(
        "def die():\n"
        "    order_id = 4471\n"
        "    raise ValueError('a real crash')\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        import crash_mod

        inst, queue = default
        inst.setup_hooks()
        try:
            crash_mod.die()
        except ValueError:
            sys.excepthook(*sys.exc_info())  # what the interpreter does on an uncaught raise

        assert len(queue.events) == 1, f"crash produced {len(queue.events)} events, want exactly 1"
        detail = queue.events[0].get("exception", {})
        assert detail.get("type") == "ValueError"
        assert detail.get("message") == "a real crash"
        assert detail.get("traceback"), "crash report has no traceback"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("crash_mod", None)


def test_caught_exceptions_cost_nothing_by_default(default):
    """The performance guarantee, stated as a test. 2703x before, ~1x after."""

    def churn(rounds=3000):
        start = time.perf_counter()
        for i in range(rounds):
            try:
                {}["missing"]
            except KeyError:
                pass
        return time.perf_counter() - start

    churn()
    baseline = churn()
    inst, _ = default
    inst.setup_hooks()
    instrumented = churn()

    ratio = instrumented / max(baseline, 1e-9)
    assert ratio < 5, (
        f"caught exceptions cost {ratio:.0f}x baseline with the default config. The RAISE hook "
        f"should not be installed at all."
    )


@pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 669 requires Python 3.12+")
def test_opting_in_restores_raise_tracing(opted_in, tmp_path):
    """Users who want caught-exception telemetry can still have it."""
    module = tmp_path / "optin_mod.py"
    module.write_text("def boom():\n    raise ValueError('canary')\n")
    sys.path.insert(0, str(tmp_path))
    try:
        import optin_mod

        inst, _ = opted_in
        inst.setup_hooks()
        assert inst._monitoring_tool_id is not None, "did not take the sys.monitoring path"
        try:
            optin_mod.boom()
        except ValueError:
            pass
        assert inst._last_captured_exception is not None, "RAISE callback did not fire"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("optin_mod", None)


def test_env_var_opts_in(monkeypatch):
    """Deployed services set env vars, not config files."""
    monkeypatch.setenv("THINKINGSDK_CAPTURE_CAUGHT_EXCEPTIONS", "true")
    assert Config().get("instrumentation", "capture_caught_exceptions") is True


def test_cleanup_does_not_clobber_a_foreign_trace_hook(default):
    """With the tracer off we never called sys.settrace, so cleanup must not reset it either. A
    debugger or coverage tool attached after start() has to survive stop()."""
    inst, _ = default
    inst.setup_hooks()

    def foreign_hook(frame, event, arg):
        return foreign_hook

    sys.settrace(foreign_hook)
    try:
        inst.cleanup_hooks()
        assert sys.gettrace() is foreign_hook, "cleanup detached someone else's trace hook"
    finally:
        sys.settrace(None)


def test_logging_integration_does_not_breadcrumb_debug_records_by_default():
    """start() forced DEBUG, which made every debug record in the process a breadcrumb and measured
    5.4x on logging calls. The breadcrumb handler should sit at the class's own INFO default."""
    from thinkingsdk.integrations.logging import LoggingIntegration

    integration = LoggingIntegration()
    assert integration._breadcrumb_handler.level == logging.INFO, "breadcrumb handler is below INFO"

    handled = []
    integration._breadcrumb_handler.handle = handled.append

    integration._handle_record(logging.LogRecord("app", logging.DEBUG, __file__, 1, "x", None, None))
    assert handled == [], "a DEBUG record became a breadcrumb"

    integration._handle_record(logging.LogRecord("app", logging.INFO, __file__, 1, "x", None, None))
    assert len(handled) == 1, "an INFO record should still become a breadcrumb"
