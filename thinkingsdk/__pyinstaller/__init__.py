"""PyInstaller hook directory, advertised via the pyinstaller40 entry point in pyproject.toml.

thinkingsdk loads its integrations lazily through importlib, so at runtime an app only pays for the
frameworks it actually has installed. PyInstaller's static analysis does not work that way: it
follows every `import` statement it can see, including ones inside function bodies, so freezing an
app that depends on thinkingsdk drags in the dependency tree of EVERY optional integration that
happens to be present in the build environment.

Shipping these hooks means consumers get the right behaviour automatically, with no flags to
remember. See issue #12.
"""
import os


def get_hook_dirs():
    return [os.path.dirname(__file__)]
