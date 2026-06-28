"""
Console integration for ThinkingSDK.

Tracks print statements as breadcrumbs without modifying behavior.
"""

import sys
import builtins
from typing import Any
from . import Integration


class ConsoleIntegration(Integration):
    """Console output integration."""

    identifier = "console"

    def __init__(self, **options):
        super().__init__(**options)
        self.capture_print = options.get('capture_print', True)

    def setup_once(self):
        """Hook into console output."""
        if self.capture_print:
            _patch_print()


def _patch_print():
    """Wrap print function to capture as breadcrumbs without modifying behavior."""
    original_print = builtins.print

    def thinking_print(*args, **kwargs):
        """Wrapper that captures print statements as breadcrumbs."""
        # Always call the original print first to maintain behavior
        result = original_print(*args, **kwargs)

        try:
            # Get breadcrumb tracker
            from .. import _breadcrumb_tracker
            if _breadcrumb_tracker:
                # Convert args to message
                sep = kwargs.get('sep', ' ')
                message = sep.join(str(arg) for arg in args)

                # Only capture non-empty messages
                if message.strip():
                    _breadcrumb_tracker.add_breadcrumb(
                        message=message[:200],  # Limit length
                        category="console",
                        level="info",
                        data={
                            'output': 'stdout' if kwargs.get('file', sys.stdout) == sys.stdout else 'other'
                        }
                    )
        except Exception:
            pass  # Never break print statements

        return result

    builtins.print = thinking_print