"""psycopg2 instrumentation: it must not break the connection it is instrumenting.

The bug these lock in (issue #16): setup_once() patched psycopg2.connect and then did
``conn.cursor = _wrapped_cursor``. psycopg2.extensions.connection is a C type with no instance
__dict__, so that assignment raises AttributeError on every real connection. Any application using
psycopg2 went from working to unable to open a database connection at all, the moment start() ran.

    File ".../thinkingsdk/integrations/psycopg2.py", line 111, in _thinking_connect
        conn.cursor = _wrapped_cursor
    AttributeError: 'psycopg2.extensions.connection' object attribute 'cursor' is read-only

The integration already knew half of this. Its own comment said "We can't patch cursor directly
(immutable C type), instead wrap the connection's cursor() method". Connections are immutable too,
so both patch sites were unreachable.

Offline: no database, no network, no start(). The connect() call itself is stubbed, because what is
under test is which factories get passed, not what Postgres does with them.
"""
import os

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from psycopg2.extensions import connection as BaseConnection  # noqa: E402
from psycopg2.extensions import cursor as BaseCursor  # noqa: E402

from thinkingsdk.integrations.psycopg2 import Psycopg2Integration  # noqa: E402


@pytest.fixture
def restored_connect():
    """setup_once() rebinds a module global; put it back so tests do not leak into each other."""
    original = psycopg2.connect
    yield original
    psycopg2.connect = original


class TestTheCTypesAreImmutable:
    """The premise. If these ever start passing as mutable, the old approach became viable and this
    whole file can be reconsidered. Until then they are why factories are the only option."""

    @pytest.mark.parametrize("c_type", [BaseConnection, BaseCursor], ids=["connection", "cursor"])
    def test_instances_have_no_dict_so_no_attribute_can_be_set(self, c_type):
        assert c_type.__dictoffset__ == 0, (
            f"{c_type.__name__} instances gained a __dict__; the read-only assumption changed"
        )

    @pytest.mark.parametrize("c_type", [BaseConnection, BaseCursor], ids=["connection", "cursor"])
    def test_both_are_subclassable_which_is_the_supported_route(self, c_type):
        subclass = type("Sub", (c_type,), {})
        assert issubclass(subclass, c_type)


class TestSetupInstallsAWrapper:
    def test_connect_is_replaced_and_marked(self, monkeypatch, restored_connect):
        # Install a known-unwrapped connect first. Another test in the suite may have called start(),
        # which leaves psycopg2.connect already wrapped; without this the idempotence guard correctly
        # does nothing and the assertion below reads as a failure of the wrong thing.
        def _plain_connect(*args, **kwargs):
            return object()

        monkeypatch.setattr(psycopg2, "connect", _plain_connect)
        Psycopg2Integration.setup_once()

        assert psycopg2.connect is not _plain_connect
        assert getattr(psycopg2.connect, "_thinkingsdk_wrapped", False) is True

    def test_setting_up_twice_does_not_wrap_the_wrapper(self, monkeypatch, restored_connect):
        """start() can be reached more than once, and a wrapper around a wrapper records every query
        twice while making the stack harder to read."""
        monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: object())
        Psycopg2Integration.setup_once()
        once = psycopg2.connect
        Psycopg2Integration.setup_once()
        assert psycopg2.connect is once


class TestWhatGetsPassedToConnect:
    """The whole fix in one place: instrumentation arrives as a factory, not as an assignment."""

    def _capture(self, monkeypatch):
        seen = {}

        def _fake_connect(*args, **kwargs):
            seen.update(kwargs)
            return object()

        monkeypatch.setattr(psycopg2, "connect", _fake_connect)
        Psycopg2Integration.setup_once()
        return seen

    def test_a_connection_factory_is_supplied_by_default(self, monkeypatch, restored_connect):
        seen = self._capture(monkeypatch)
        psycopg2.connect("postgresql://localhost/x")
        factory = seen.get("connection_factory")
        assert factory is not None
        assert issubclass(factory, BaseConnection)

    def test_it_never_touches_the_returned_connection(self, monkeypatch, restored_connect):
        """The regression itself. A real connection cannot be assigned to, so the wrapper must hand
        back exactly what psycopg2 returned."""
        sentinel = object()
        monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: sentinel)
        Psycopg2Integration.setup_once()
        assert psycopg2.connect("postgresql://localhost/x") is sentinel

    def test_a_callers_own_connection_factory_wins(self, monkeypatch, restored_connect):
        """Someone already using connection_factory has a reason to. Overriding it would change what
        their connection IS, which is a bigger harm than losing a breadcrumb."""
        class CallerConnection(BaseConnection):
            pass

        seen = self._capture(monkeypatch)
        psycopg2.connect("postgresql://localhost/x", connection_factory=CallerConnection)
        assert seen["connection_factory"] is CallerConnection


DSN = os.environ.get("THINKINGSDK_TEST_DSN")


@pytest.mark.skipif(not DSN, reason="set THINKINGSDK_TEST_DSN to a live Postgres to run these")
class TestAgainstARealDatabase:
    """Cursor behaviour needs a server, because super().cursor() lands in psycopg2's C code.

    Opt-in rather than skipped-and-forgotten: these are the tests that actually prove the reported
    crash is gone, so the DSN is worth setting when touching this file.
    """

    @pytest.fixture
    def instrumented(self, restored_connect):
        Psycopg2Integration.setup_once()
        connection = psycopg2.connect(DSN)
        yield connection
        connection.close()

    def test_connecting_no_longer_raises(self, restored_connect):
        """The bug, directly. This raised AttributeError before the fix."""
        Psycopg2Integration.setup_once()
        connection = psycopg2.connect(DSN)
        connection.close()

    def test_the_default_cursor_is_instrumented(self, instrumented):
        assert type(instrumented.cursor()).__name__ == "ThinkingCursor"

    def test_queries_still_return_what_they_should(self, instrumented):
        cursor = instrumented.cursor()
        cursor.execute("SELECT 42")
        assert cursor.fetchone() == (42,)

    def test_a_caller_asking_for_realdictcursor_still_gets_one(self, instrumented):
        """Silently swapping this would change every row from a tuple to a dict, or back, which
        corrupts results rather than merely losing a breadcrumb."""
        from psycopg2.extras import RealDictCursor

        cursor = instrumented.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT 7 AS n")
        assert cursor.fetchone() == {"n": 7}

    def test_a_failing_query_still_raises(self, instrumented):
        """Instrumentation records the error and re-raises; it must not swallow a real failure."""
        cursor = instrumented.cursor()
        with pytest.raises(psycopg2.Error):
            cursor.execute("SELECT * FROM a_table_that_does_not_exist")
