"""Instrumentation must not install a per-call trace hook on Python 3.12+.

sys.settrace fires on every function call, line and return in the thread. Measured on a real
workload it cost ~80% of a CPU core sustained, and 467x on a tight loop (issue #10). PEP 669 lets us
subscribe to RAISE only, so non-exception code runs at full speed.

These tests pin that: no per-call hook on 3.12+, exception capture unchanged, clean teardown.

Tracing caught exceptions is opt-in since issue #20, so the tests that exercise the RAISE path ask
for it explicitly via the `tracing` fixture. The default-path guarantees live in
test_caught_exception_tracing_is_opt_in.py.
"""
import sys

import pytest

from thinkingsdk.instrumentation import RuntimeInstrumentation


class _Queue:
    def __init__(self):
        self.count = 0

    def put(self, *args, **kwargs):
        self.count += 1

    def add_event(self, *args, **kwargs):
        self.count += 1

    def enqueue(self, *args, **kwargs):
        self.count += 1


def _make(**config):
    return RuntimeInstrumentation(_Queue(), config)


def _teardown(inst):
    try:
        inst.cleanup_hooks()
    except Exception:
        pass
    sys.settrace(None)


@pytest.fixture
def instrumentation():
    inst = _make()
    yield inst
    _teardown(inst)


@pytest.fixture
def tracing():
    """Instrumentation with caught-exception tracing turned on, which is what the RAISE-path
    assertions below are about."""
    inst = _make(capture_caught_exceptions=True)
    yield inst
    _teardown(inst)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 669 requires Python 3.12+")
def test_no_per_call_trace_hook_is_installed(tracing):
    """THE regression test. If this fails, every host application pays the per-call tax again."""
    tracing.setup_hooks()
    assert tracing._monitoring_tool_id is not None, "did not take the sys.monitoring path"
    assert sys.gettrace() is None, (
        "a global sys.settrace hook is installed; this costs ~80% of a core on a busy app"
    )


@pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 669 requires Python 3.12+")
def test_instrumentation_overhead_is_negligible(tracing):
    """Guards the whole point of the change. settrace measured 467x here; monitoring should be ~1x."""
    import time

    def work(n=200):
        total = 0
        for i in range(n):
            total += len(str(i)) + sum(x for x in (1, 2, 3))
        return total

    work()
    start = time.perf_counter(); work(); baseline = time.perf_counter() - start
    tracing.setup_hooks()
    start = time.perf_counter(); work(); instrumented = time.perf_counter() - start

    ratio = instrumented / max(baseline, 1e-9)
    assert ratio < 10, (
        f"instrumentation cost {ratio:.0f}x baseline. sys.settrace measured 467x; sys.monitoring "
        f"should be near 1x. Did it silently fall back to settrace?"
    )


@pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 669 requires Python 3.12+")
def test_exceptions_are_still_seen(tracing, tmp_path):
    """Speed is worthless if capture regressed. The dedup marker is what the excepthook path checks,
    so it is the observable proving the RAISE callback reached the shared capture code."""
    module = tmp_path / "canary_mod.py"
    module.write_text("def boom():\n    raise ValueError('canary')\n")
    sys.path.insert(0, str(tmp_path))
    try:
        import canary_mod
        tracing.setup_hooks()
        try:
            canary_mod.boom()
        except ValueError:
            pass
        assert tracing._last_captured_exception is not None, (
            "RAISE callback did not reach the capture path"
        )
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("canary_mod", None)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 669 requires Python 3.12+")
def test_cleanup_releases_the_tool_id(tracing):
    """A leaked tool id makes the next setup_hooks() fall back to settrace, silently reintroducing
    the cost."""
    tracing.setup_hooks()
    tracing.cleanup_hooks()
    assert tracing._monitoring_tool_id is None
    # the id must be reusable
    sys.monitoring.use_tool_id(sys.monitoring.PROFILER_ID, "probe")
    sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)


def test_excepthooks_are_installed_either_way(instrumentation):
    """sys.monitoring replaces the trace hook only. The excepthooks that report unhandled crashes
    must still be installed on every Python version."""
    original = sys.excepthook
    instrumentation.setup_hooks()
    assert sys.excepthook is not original, "sys.excepthook was not installed"
