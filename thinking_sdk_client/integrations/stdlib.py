"""
Standard library integrations for ThinkingSDK.

Adapted from sentry-sdk's stdlib integration to capture HTTP and subprocess events as breadcrumbs.
"""

import sys
import subprocess
from http.client import HTTPConnection
from typing import Any, Optional
from . import Integration


class StdlibIntegration(Integration):
    """Standard library integration for HTTP and subprocess tracking."""

    identifier = "stdlib"

    @staticmethod
    def setup_once():
        """Install patches for stdlib modules."""
        _install_httplib()
        _install_subprocess()


def _install_httplib():
    """Patch HTTPConnection to track HTTP requests as breadcrumbs."""
    real_putrequest = HTTPConnection.putrequest
    real_getresponse = HTTPConnection.getresponse

    def thinking_putrequest(self, method, url, *args, **kwargs):
        """Wrapper that starts tracking an HTTP request."""
        # Store request info on the connection object
        self._thinking_request_info = {
            'method': method,
            'url': url,
            'host': self.host,
            'port': self.port,
        }

        return real_putrequest(self, method, url, *args, **kwargs)

    def thinking_getresponse(self, *args, **kwargs):
        """Wrapper that completes tracking an HTTP request."""
        response = real_getresponse(self, *args, **kwargs)

        try:
            # Get breadcrumb tracker
            from .. import _breadcrumb_tracker
            if _breadcrumb_tracker and hasattr(self, '_thinking_request_info'):
                info = self._thinking_request_info

                # Determine level based on status code
                if response.status >= 500:
                    level = "error"
                elif response.status >= 400:
                    level = "warning"
                else:
                    level = "info"

                # Build URL for display
                url = info['url']
                if not url.startswith(('http://', 'https://')):
                    scheme = 'https' if self.default_port == 443 else 'http'
                    port_str = '' if info['port'] == self.default_port else f":{info['port']}"
                    url = f"{scheme}://{info['host']}{port_str}{url}"

                # Add breadcrumb
                _breadcrumb_tracker.add_breadcrumb(
                    message=f"{info['method']} {url} [{response.status}]",
                    category="http",
                    level=level,
                    data={
                        'method': info['method'],
                        'url': url,
                        'status_code': response.status,
                        'reason': response.reason,
                    }
                )

                # Clean up
                del self._thinking_request_info

        except Exception:
            pass  # Never break HTTP requests

        return response

    HTTPConnection.putrequest = thinking_putrequest
    HTTPConnection.getresponse = thinking_getresponse


def _install_subprocess():
    """Patch subprocess to track subprocess calls as breadcrumbs."""
    old_popen_init = subprocess.Popen.__init__

    def thinking_popen_init(self, *a, **kw):
        """Wrapper that tracks subprocess creation."""
        # Convert args for safety
        a = list(a)

        # Extract args safely
        args = a[0] if len(a) > 0 else kw.get('args', [])

        # Build description
        description = None
        if isinstance(args, (list, tuple)) and len(args) < 100:
            try:
                description = " ".join(str(x) for x in args)
            except Exception:
                pass

        if description is None:
            description = str(args)[:100] if args else "subprocess"

        # Call original
        result = old_popen_init(self, *a, **kw)

        try:
            # Get breadcrumb tracker
            from .. import _breadcrumb_tracker
            if _breadcrumb_tracker:
                # Add breadcrumb
                _breadcrumb_tracker.add_breadcrumb(
                    message=f"Started: {description}",
                    category="subprocess",
                    level="info",
                    data={
                        'pid': self.pid,
                        'args': args if isinstance(args, (list, tuple)) else str(args),
                    }
                )
        except Exception:
            pass  # Never break subprocess creation

        return result

    subprocess.Popen.__init__ = thinking_popen_init