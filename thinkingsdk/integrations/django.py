"""
Django integration for ThinkingSDK.

Captures Django-specific context when exceptions occur.
"""

from typing import Dict, Any, Optional, List
from . import Integration


class DjangoIntegration(Integration):
    """Django framework integration."""
    
    identifier = "django"
    
    def __init__(self, **options):
        super().__init__(**options)
        self.capture_templates = options.get('capture_templates', True)
        self.capture_middleware = options.get('capture_middleware', True)
        self.capture_settings = options.get('capture_settings', True)
        self.safe_settings = options.get('safe_settings', self._get_safe_settings())
    
    def _get_safe_settings(self) -> List[str]:
        """Get list of safe Django settings to capture."""
        return [
            'DEBUG', 'ALLOWED_HOSTS', 'INSTALLED_APPS', 'MIDDLEWARE',
            'ROOT_URLCONF', 'TEMPLATES', 'DATABASES',  # Without credentials
            'LANGUAGE_CODE', 'TIME_ZONE', 'USE_I18N', 'USE_TZ',
            'STATIC_URL', 'MEDIA_URL', 'DEFAULT_AUTO_FIELD',
            'APPEND_SLASH', 'PREPEND_WWW', 'USE_X_FORWARDED_HOST',
        ]
    
    def setup_once(self):
        """Hook into Django to capture context."""
        try:
            from django.core import signals
            from django.core.handlers.exception import convert_exception_to_response
            import django

            # Check Django is properly configured
            if not hasattr(django, 'setup'):
                return

            # Hook into Django's got_request_exception signal
            signals.got_request_exception.connect(self._handle_exception)

            # Hook into request signals for breadcrumbs
            signals.request_started.connect(self._on_request_started)
            signals.request_finished.connect(self._on_request_finished)

            # Store original exception handler
            self._original_exception_handler = convert_exception_to_response

        except ImportError:
            pass
        except Exception:
            pass
    
    def _handle_exception(self, sender, request, **kwargs):
        """Store request context when exception occurs."""
        try:
            # Store in thread-local storage for later retrieval
            import threading
            if not hasattr(threading.current_thread(), 'tsdk_django_context'):
                threading.current_thread().tsdk_django_context = {}
            
            threading.current_thread().tsdk_django_context = {
                'request': self._extract_request_context(request),
                'view': self._extract_view_context(sender),
            }
        except Exception:
            pass
    
    def capture_context(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add Django-specific context to exception data."""
        try:
            import threading
            django_context = {}
            
            # Get stored request context
            if hasattr(threading.current_thread(), 'tsdk_django_context'):
                django_context.update(threading.current_thread().tsdk_django_context)
            
            # Add current Django context
            django_context.update({
                'middleware': self._get_middleware_stack() if self.capture_middleware else None,
                'settings': self._get_safe_settings_values() if self.capture_settings else None,
                'database': self._get_database_info(),
            })
            
            # Add to exception data
            if 'framework_context' not in exception_data:
                exception_data['framework_context'] = {}
            
            exception_data['framework_context']['django'] = django_context
            
        except Exception:
            pass
        
        return exception_data
    
    def _extract_request_context(self, request) -> Dict[str, Any]:
        """Extract relevant request information."""
        try:
            from django.urls import resolve
            
            context = {
                'method': request.method,
                'path': request.path,
                'path_info': request.path_info,
                'META': self._sanitize_meta(request.META),
                'GET': dict(request.GET),
                'POST': self._sanitize_post(request.POST) if request.method == 'POST' else None,
                'COOKIES': self._sanitize_cookies(request.COOKIES),
                'FILES': list(request.FILES.keys()) if hasattr(request, 'FILES') else [],
                'content_type': request.content_type,
            }
            
            # Add URL resolver info
            try:
                resolved = resolve(request.path_info)
                context['url_resolver'] = {
                    'view_name': resolved.view_name,
                    'namespace': resolved.namespace,
                    'route': str(resolved.route),
                    'args': resolved.args,
                    'kwargs': self._sanitize_kwargs(resolved.kwargs),
                }
            except Exception:
                pass
            
            # Add user info if available
            if hasattr(request, 'user'):
                try:
                    context['user'] = {
                        'id': request.user.id if hasattr(request.user, 'id') else None,
                        'username': request.user.username if hasattr(request.user, 'username') else None,
                        'is_authenticated': request.user.is_authenticated,
                        'is_staff': getattr(request.user, 'is_staff', False),
                        'is_superuser': getattr(request.user, 'is_superuser', False),
                    }
                except Exception:
                    pass
            
            # Add session info
            if hasattr(request, 'session'):
                context['session'] = {
                    'session_key': request.session.session_key if hasattr(request.session, 'session_key') else None,
                    'keys': list(request.session.keys()) if hasattr(request.session, 'keys') else [],
                }
            
            return context
            
        except Exception:
            return {}
    
    def _extract_view_context(self, view) -> Dict[str, Any]:
        """Extract view information."""
        try:
            context = {}
            
            if hasattr(view, '__name__'):
                context['name'] = view.__name__
            if hasattr(view, '__module__'):
                context['module'] = view.__module__
            if hasattr(view, '__class__'):
                context['class'] = view.__class__.__name__
                
            # For class-based views
            if hasattr(view, 'view_class'):
                context['view_class'] = view.view_class.__name__
                context['view_module'] = view.view_class.__module__
                
            return context
            
        except Exception:
            return {}
    
    def _get_middleware_stack(self) -> List[str]:
        """Get the middleware stack."""
        try:
            from django.conf import settings
            return list(settings.MIDDLEWARE)
        except Exception:
            return []
    
    def _get_safe_settings_values(self) -> Dict[str, Any]:
        """Get safe Django settings values."""
        try:
            from django.conf import settings
            
            safe_values = {}
            for setting in self.safe_settings:
                if hasattr(settings, setting):
                    value = getattr(settings, setting)
                    
                    # Special handling for DATABASES
                    if setting == 'DATABASES':
                        value = self._sanitize_databases(value)
                    
                    safe_values[setting] = value
            
            return safe_values
            
        except Exception:
            return {}
    
    def _get_database_info(self) -> Dict[str, Any]:
        """Get database connection information."""
        try:
            from django.db import connections
            
            db_info = {}
            for alias in connections:
                conn = connections[alias]
                db_info[alias] = {
                    'vendor': conn.vendor,
                    'queries_count': len(conn.queries) if hasattr(conn, 'queries') else 0,
                    'is_usable': conn.is_usable() if hasattr(conn, 'is_usable') else None,
                }
            
            return db_info
            
        except Exception:
            return {}
    
    def _sanitize_meta(self, meta: Dict) -> Dict:
        """Sanitize request.META dictionary."""
        safe_keys = [
            'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT', 'PATH_INFO',
            'QUERY_STRING', 'CONTENT_TYPE', 'CONTENT_LENGTH', 'HTTP_HOST',
            'HTTP_USER_AGENT', 'HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE',
            'HTTP_REFERER', 'REMOTE_ADDR', 'REMOTE_HOST', 'SERVER_PROTOCOL',
        ]
        
        return {k: v for k, v in meta.items() if k in safe_keys}
    
    def _sanitize_post(self, post_data) -> Dict:
        """Sanitize POST data to avoid logging sensitive info."""
        sensitive_keys = ['password', 'passwd', 'secret', 'token', 'key', 'api']
        
        sanitized = {}
        for key, value in post_data.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_cookies(self, cookies: Dict) -> Dict:
        """Sanitize cookies to avoid logging sensitive info."""
        safe_cookies = ['sessionid', 'csrftoken', 'messages']
        return {k: '***' if k not in safe_cookies else v[:10] + '...' 
                for k, v in cookies.items()}
    
    def _sanitize_kwargs(self, kwargs: Dict) -> Dict:
        """Sanitize URL kwargs."""
        # Simple sanitization - could be enhanced
        return {k: v if not isinstance(v, (str, int, float)) else v 
                for k, v in kwargs.items()}
    
    def _sanitize_databases(self, databases: Dict) -> Dict:
        """Remove sensitive database information."""
        sanitized = {}
        for alias, config in databases.items():
            sanitized[alias] = {
                'ENGINE': config.get('ENGINE'),
                'NAME': config.get('NAME'),
                'HOST': config.get('HOST'),
                'PORT': config.get('PORT'),
                # Exclude USER, PASSWORD, etc.
            }
        return sanitized

    def _on_request_started(self, sender, environ, **kwargs):
        """Add breadcrumb when request starts."""
        try:
            from .. import _breadcrumb_tracker

            if not _breadcrumb_tracker:
                return

            # Extract request info from environ
            method = environ.get('REQUEST_METHOD', 'GET')
            path = environ.get('PATH_INFO', '/')
            query_string = environ.get('QUERY_STRING', '')

            # Build breadcrumb data
            data = {
                'method': method,
                'path': path,
            }

            if query_string:
                data['query_string'] = query_string

            # Add breadcrumb
            _breadcrumb_tracker.add_breadcrumb(
                message=f"{method} {path}",
                category="http",
                level="info",
                data=data
            )

        except Exception:
            pass

    def _on_request_finished(self, sender, **kwargs):
        """Add breadcrumb when request finishes."""
        try:
            from .. import _breadcrumb_tracker

            if not _breadcrumb_tracker:
                return

            # Try to get response info if available
            # Django's request_finished signal doesn't provide response details
            # So we just mark completion
            _breadcrumb_tracker.add_breadcrumb(
                message="Request completed",
                category="http",
                level="info",
                data={}
            )

        except Exception:
            pass