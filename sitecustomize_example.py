"""
Example sitecustomize.py for system-wide ThinkingSDK auto-instrumentation.

To enable:
1. Copy this file to your Python's site-packages directory as 'sitecustomize.py'
   Or add to existing sitecustomize.py if one exists
2. Set environment variable: THINKINGSDK_ENABLED=true
3. All Python processes will automatically be instrumented

To find site-packages location:
    python -c "import site; print(site.getsitepackages())"
"""

import os

# Only instrument if explicitly enabled
if os.environ.get('THINKINGSDK_ENABLED', '').lower() in ('true', '1', 'yes', 'on'):
    try:
        import thinking_sdk_client.auto_instrument
    except ImportError:
        # ThinkingSDK not installed, skip silently
        pass
    except Exception as e:
        # Log but don't crash
        import sys
        print(f"Warning: Failed to auto-instrument with ThinkingSDK: {e}", file=sys.stderr)