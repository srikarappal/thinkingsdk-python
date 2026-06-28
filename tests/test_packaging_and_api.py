"""Packaging + public-API regression tests.

These lock in the changes from the rename/packaging cleanup so they can't
silently regress:

  - the package and its subpackages import under the `thinkingsdk` name
    (the rename from `thinking_sdk_client` and the find-based packaging fix),
  - the documented public API surface stays present,
  - no module still references the old `thinking_sdk_client` name,
  - the single `thinkingsdk` console script points at the validate entry point
    (the old `thinking` / `thinking-validate` scripts are gone).

They are import-only and offline: no `start()`, no network, no threads.
"""
import importlib
import importlib.util
import pathlib

import pytest

import thinkingsdk

# Mirrors thinkingsdk.__all__ , the surface callers depend on.
_PUBLIC_API = [
    "__version__", "__version_info__",
    "start", "stop", "get_stats", "is_active",
    "context", "set_context", "clear_context", "add_context",
    "track_event", "track_metric", "add_breadcrumb", "mark_feature_usage", "timer",
    "RuntimeInstrumentation", "BackgroundSender", "EventQueue", "Config",
]

# Integration modules that must ship inside the package (the subpackage the
# broken packaging used to drop, causing ModuleNotFoundError at import).
_INTEGRATION_MODULES = [
    "console", "django", "fastapi", "flask", "logging",
    "middleware_base", "psycopg2", "pymongo", "redis_integration",
    "sqlalchemy", "stdlib",
]


@pytest.mark.parametrize("name", _PUBLIC_API)
def test_public_api_surface_present(name):
    assert hasattr(thinkingsdk, name), f"thinkingsdk.{name} missing from the public API"


def test_version_is_set_and_consistent():
    assert isinstance(thinkingsdk.__version__, str) and thinkingsdk.__version__
    from thinkingsdk import _version

    assert thinkingsdk.__version__ == _version.__version__


def test_integrations_subpackage_imports():
    integrations = importlib.import_module("thinkingsdk.integrations")
    registry = integrations.get_integration_registry()
    assert registry is not None


@pytest.mark.parametrize("module", _INTEGRATION_MODULES)
def test_integration_module_packaged_under_thinkingsdk(module):
    # find_spec locates the module without importing the framework it wraps.
    spec = importlib.util.find_spec(f"thinkingsdk.integrations.{module}")
    assert spec is not None, f"thinkingsdk.integrations.{module} is not packaged"
    assert spec.origin and "thinkingsdk/integrations/" in spec.origin.replace("\\", "/")


def test_no_legacy_module_name_anywhere_in_package():
    """The old name must not survive anywhere in the shipped package , a dotted
    path string left as `thinking_sdk_client...` would fail only at runtime."""
    pkg_dir = pathlib.Path(thinkingsdk.__file__).resolve().parent
    offenders = [
        str(py.relative_to(pkg_dir))
        for py in pkg_dir.rglob("*.py")
        if "thinking_sdk_client" in py.read_text(encoding="utf-8")
    ]
    assert not offenders, f"legacy name 'thinking_sdk_client' still referenced in: {offenders}"


def test_cli_validate_entrypoint_callable():
    from thinkingsdk.validate import main, validate_deployment

    assert callable(main)
    assert callable(validate_deployment)


def test_console_script_is_thinkingsdk_only():
    """The installed dist must expose exactly one console script, `thinkingsdk`,
    bound to the validate entry point , not the old broken `thinking` (which
    pointed at a non-existent cli module) or `thinking-validate`."""
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        distribution("thinkingsdk")
    except PackageNotFoundError:
        pytest.skip("thinkingsdk is not installed; entry-point metadata unavailable")

    from importlib.metadata import entry_points

    eps = entry_points()
    scripts = eps.select(group="console_scripts") if hasattr(eps, "select") else eps.get("console_scripts", [])
    names = {ep.name: ep.value for ep in scripts}

    assert names.get("thinkingsdk") == "thinkingsdk.validate:main"
    assert "thinking" not in names
    assert "thinking-validate" not in names
