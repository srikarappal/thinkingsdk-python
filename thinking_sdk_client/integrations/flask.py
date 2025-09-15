"""
Flask integration for ThinkingSDK.

Captures Flask-specific context when exceptions occur.
"""

from typing import Dict, Any, Optional, List
from . import Integration


class FlaskIntegration(Integration):
    """Flask framework integration."""
    
    identifier = "flask"
    
    def __init__(self, **options):
        super().__init__(**options)
        self.capture_request = options.get('capture_request', True)
        self.capture_response = options.get('capture_response', False)
        self.capture_session = options.get('capture_session', True)
    
    def setup_once(self):
        """Hook into Flask to capture context."""
        try:
            import flask
            from flask import signals
            
            # Hook into Flask's got_request_exception signal
            signals.got_request_exception.connect(self._handle_exception)
            
            # Store Flask version for context
            self.flask_version = flask.__version__
            
        except ImportError:
            pass
        except Exception:
            pass
    
    def _handle_exception(self, sender, exception, **kwargs):
        """Store Flask context when exception occurs."""
        try:
            import threading
            from flask import request, g, session, current_app
            
            # Store in thread-local storage for later retrieval
            if not hasattr(threading.current_thread(), 'tsdk_flask_context'):
                threading.current_thread().tsdk_flask_context = {}
            
            context = {
                'app': self._extract_app_context(sender),
                'request': self._extract_request_context(request) if self.capture_request else None,
                'g': self._extract_g_context(g),
                'session': self._extract_session_context(session) if self.capture_session else None,
            }
            
            threading.current_thread().tsdk_flask_context = context
            
        except Exception:
            pass
    
    def capture_context(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add Flask-specific context to exception data."""
        try:
            import threading
            flask_context = {}
            
            # Get stored request context
            if hasattr(threading.current_thread(), 'tsdk_flask_context'):
                flask_context.update(threading.current_thread().tsdk_flask_context)
            
            # Add Flask metadata
            flask_context['flask_version'] = getattr(self, 'flask_version', 'unknown')
            
            # Try to get current app config (safe keys only)
            try:
                from flask import current_app
                if current_app:
                    flask_context['config'] = self._get_safe_config(current_app.config)
                    flask_context['blueprints'] = list(current_app.blueprints.keys())
                    flask_context['extensions'] = list(current_app.extensions.keys())
            except Exception:
                pass
            
            # Add to exception data
            if 'framework_context' not in exception_data:
                exception_data['framework_context'] = {}
            
            exception_data['framework_context']['flask'] = flask_context
            
        except Exception:
            pass
        
        return exception_data
    
    def _extract_app_context(self, app) -> Dict[str, Any]:
        """Extract Flask app information."""
        try:
            context = {
                'name': app.name if hasattr(app, 'name') else None,
                'import_name': app.import_name if hasattr(app, 'import_name') else None,
                'root_path': app.root_path if hasattr(app, 'root_path') else None,
                'instance_path': app.instance_path if hasattr(app, 'instance_path') else None,
            }
            
            # Add debug mode
            if hasattr(app, 'debug'):
                context['debug'] = app.debug
            
            return context
            
        except Exception:
            return {}
    
    def _extract_request_context(self, request) -> Dict[str, Any]:
        """Extract Flask request information."""
        try:
            context = {
                'method': request.method,
                'path': request.path,
                'full_path': request.full_path,
                'url': request.url,
                'base_url': request.base_url,
                'url_root': request.url_root,
                'blueprint': request.blueprint,
                'endpoint': request.endpoint,
                'view_args': dict(request.view_args) if request.view_args else None,
            }
            
            # Headers (safe subset)
            safe_headers = ['Host', 'User-Agent', 'Accept', 'Accept-Language', 
                          'Content-Type', 'Content-Length', 'Referer']
            context['headers'] = {k: v for k, v in request.headers.items() 
                                if k in safe_headers}
            
            # Query parameters
            context['args'] = dict(request.args)
            
            # Form data (sanitized)
            if request.method in ['POST', 'PUT', 'PATCH']:
                context['form'] = self._sanitize_form_data(dict(request.form))
                
                # JSON data if present
                try:
                    if request.is_json:
                        context['json'] = self._sanitize_json_data(request.get_json())
                except Exception:
                    pass
            
            # Files (just names)
            if request.files:
                context['files'] = list(request.files.keys())
            
            # Cookies (sanitized)
            context['cookies'] = self._sanitize_cookies(request.cookies)
            
            # Remote address
            context['remote_addr'] = request.remote_addr
            
            return context
            
        except Exception:
            return {}
    
    def _extract_g_context(self, g) -> Dict[str, Any]:
        """Extract Flask g (application context globals)."""
        try:
            # Get all attributes from g
            g_dict = {}
            for key in dir(g):
                if not key.startswith('_'):
                    try:
                        value = getattr(g, key)
                        # Only include serializable values
                        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                            g_dict[key] = value
                        else:
                            g_dict[key] = str(type(value))
                    except Exception:
                        pass
            
            return g_dict
            
        except Exception:
            return {}
    
    def _extract_session_context(self, session) -> Dict[str, Any]:
        """Extract Flask session information."""
        try:
            if session is None:
                return {}
            
            # Get session keys (not values for privacy)
            context = {
                'keys': list(session.keys()) if hasattr(session, 'keys') else [],
                'new': session.new if hasattr(session, 'new') else None,
                'modified': session.modified if hasattr(session, 'modified') else None,
                'permanent': session.permanent if hasattr(session, 'permanent') else None,
            }
            
            # Include non-sensitive session values
            safe_keys = ['user_id', 'username', 'locale', 'theme']
            for key in safe_keys:
                if key in session:
                    context[key] = session[key]
            
            return context
            
        except Exception:
            return {}
    
    def _get_safe_config(self, config: Dict) -> Dict[str, Any]:
        """Get safe Flask configuration values."""
        safe_keys = [
            'DEBUG', 'TESTING', 'PROPAGATE_EXCEPTIONS', 'PRESERVE_CONTEXT_ON_EXCEPTION',
            'TRAP_HTTP_EXCEPTIONS', 'TRAP_BAD_REQUEST_ERRORS', 'JSON_AS_ASCII',
            'JSON_SORT_KEYS', 'JSONIFY_PRETTYPRINT_REGULAR', 'JSONIFY_MIMETYPE',
            'TEMPLATES_AUTO_RELOAD', 'EXPLAIN_TEMPLATE_LOADING', 'MAX_CONTENT_LENGTH',
            'SEND_FILE_MAX_AGE_DEFAULT', 'ERROR_404_HELP', 'SERVER_NAME',
            'APPLICATION_ROOT', 'SESSION_COOKIE_NAME', 'SESSION_COOKIE_DOMAIN',
            'SESSION_COOKIE_PATH', 'SESSION_COOKIE_HTTPONLY', 'SESSION_COOKIE_SECURE',
            'SESSION_COOKIE_SAMESITE', 'PERMANENT_SESSION_LIFETIME', 'USE_X_SENDFILE',
            'LOGGER_NAME', 'LOGGER_HANDLER_POLICY', 'PREFERRED_URL_SCHEME',
        ]
        
        return {k: v for k, v in config.items() if k in safe_keys}
    
    def _sanitize_form_data(self, form_data: Dict) -> Dict:
        """Sanitize form data to avoid logging sensitive info."""
        sensitive_keys = ['password', 'passwd', 'secret', 'token', 'key', 'api', 'credit']
        
        sanitized = {}
        for key, value in form_data.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_json_data(self, json_data: Any) -> Any:
        """Sanitize JSON data recursively."""
        if isinstance(json_data, dict):
            return self._sanitize_form_data(json_data)
        elif isinstance(json_data, list):
            return [self._sanitize_json_data(item) for item in json_data[:10]]  # Limit arrays
        else:
            return json_data
    
    def _sanitize_cookies(self, cookies: Dict) -> Dict:
        """Sanitize cookies to avoid logging sensitive info."""
        safe_cookies = ['session', 'remember_token', 'locale', 'theme']
        return {k: '***' if k not in safe_cookies else v[:10] + '...' if len(v) > 10 else v
                for k, v in cookies.items()}