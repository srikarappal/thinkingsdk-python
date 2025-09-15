"""
FastAPI integration for ThinkingSDK.

Captures FastAPI-specific context when exceptions occur, including
async context, dependency injection, and Pydantic validation.
"""

import time
from typing import Dict, Any, Optional, List
from . import Integration


class FastAPIIntegration(Integration):
    """FastAPI framework integration."""
    
    identifier = "fastapi"
    
    def __init__(self, **options):
        super().__init__(**options)
        self.capture_request = options.get('capture_request', True)
        self.capture_response = options.get('capture_response', False)
        self.capture_dependencies = options.get('capture_dependencies', True)
        self.capture_validation_errors = options.get('capture_validation_errors', True)
    
    def setup_once(self):
        """Hook into FastAPI/Starlette to capture context."""
        try:
            from starlette.exceptions import HTTPException
            from fastapi import FastAPI
            from fastapi.exceptions import RequestValidationError
            import starlette
            
            # Store versions for context
            self.fastapi_version = self._get_fastapi_version()
            self.starlette_version = starlette.__version__
            
            # Hook into exception handlers
            self._setup_exception_handlers()
            
        except ImportError:
            pass
        except Exception:
            pass
    
    def _get_fastapi_version(self) -> str:
        """Get FastAPI version."""
        try:
            import fastapi
            return fastapi.__version__
        except:
            return "unknown"
    
    def _setup_exception_handlers(self):
        """Setup exception handlers to capture context."""
        try:
            import asyncio
            import threading
            
            # Store original exception handler
            self._original_exception_handler = None
            
            # Create a middleware to capture exceptions
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.requests import Request
            
            class ThinkingSDKMiddleware(BaseHTTPMiddleware):
                def __init__(self, app, integration):
                    super().__init__(app)
                    self.integration = integration
                
                async def dispatch(self, request: Request, call_next):
                    try:
                        # Store request in context for later use
                        self.integration._store_request_context(request)
                        response = await call_next(request)
                        return response
                    except Exception as exc:
                        # Store exception context
                        self.integration._store_exception_context(request, exc)
                        raise
            
            # Store middleware class for app integration
            self._middleware_class = ThinkingSDKMiddleware
            
        except Exception:
            pass
    
    def _store_request_context(self, request):
        """Store request context in async-safe way."""
        try:
            import asyncio
            import threading
            
            # Get current event loop and thread
            loop = asyncio.get_event_loop()
            thread_id = threading.current_thread().ident
            
            # Create context key
            context_key = f"tsdk_fastapi_{thread_id}_{id(loop)}"
            
            # Store in thread-local
            if not hasattr(threading.current_thread(), 'tsdk_contexts'):
                threading.current_thread().tsdk_contexts = {}
            
            threading.current_thread().tsdk_contexts[context_key] = {
                'request': request,
                'timestamp': time.time()
            }
            
        except Exception:
            pass
    
    def _store_exception_context(self, request, exception):
        """Store exception context with request data."""
        try:
            import threading
            
            # Store in thread-local storage
            if not hasattr(threading.current_thread(), 'tsdk_fastapi_context'):
                threading.current_thread().tsdk_fastapi_context = {}
            
            context = {
                'request': self._extract_request_context(request),
                'exception': self._extract_exception_context(exception),
            }
            
            # Add route information
            if hasattr(request, 'scope'):
                context['route'] = self._extract_route_context(request.scope)
            
            threading.current_thread().tsdk_fastapi_context = context
            
        except Exception:
            pass
    
    def capture_context(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add FastAPI-specific context to exception data."""
        try:
            import threading
            fastapi_context = {}
            
            # Get stored request context
            if hasattr(threading.current_thread(), 'tsdk_fastapi_context'):
                fastapi_context.update(threading.current_thread().tsdk_fastapi_context)
            
            # Add FastAPI metadata
            fastapi_context['fastapi_version'] = getattr(self, 'fastapi_version', 'unknown')
            fastapi_context['starlette_version'] = getattr(self, 'starlette_version', 'unknown')
            
            # Add async context if available
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                fastapi_context['async_context'] = {
                    'running': loop.is_running(),
                    'tasks': len(asyncio.all_tasks(loop)) if hasattr(asyncio, 'all_tasks') else 0,
                }
            except Exception:
                pass
            
            # Add to exception data
            if 'framework_context' not in exception_data:
                exception_data['framework_context'] = {}
            
            exception_data['framework_context']['fastapi'] = fastapi_context
            
        except Exception:
            pass
        
        return exception_data
    
    def _extract_request_context(self, request) -> Dict[str, Any]:
        """Extract FastAPI/Starlette request information."""
        try:
            context = {
                'method': request.method,
                'url': str(request.url),
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'path_params': dict(request.path_params) if hasattr(request, 'path_params') else {},
                'client': {
                    'host': request.client.host if request.client else None,
                    'port': request.client.port if request.client else None,
                },
            }
            
            # Headers (safe subset)
            safe_headers = ['host', 'user-agent', 'accept', 'accept-language',
                          'content-type', 'content-length', 'referer', 'origin']
            context['headers'] = {k: v for k, v in request.headers.items()
                                if k.lower() in safe_headers}
            
            # Cookies (sanitized)
            context['cookies'] = self._sanitize_cookies(request.cookies)
            
            # Get route information from scope
            if hasattr(request, 'scope'):
                scope = request.scope
                context['scope'] = {
                    'type': scope.get('type'),
                    'scheme': scope.get('scheme'),
                    'root_path': scope.get('root_path'),
                    'app': str(scope.get('app', ''))[:100],  # Truncate app info
                }
                
                # Route/endpoint info
                if 'endpoint' in scope:
                    endpoint = scope['endpoint']
                    context['endpoint'] = {
                        'name': getattr(endpoint, '__name__', str(endpoint)),
                        'module': getattr(endpoint, '__module__', None),
                    }
                
                # Path info
                if 'path' in scope:
                    context['matched_path'] = scope['path']
            
            return context
            
        except Exception:
            return {}
    
    def _extract_route_context(self, scope: Dict) -> Dict[str, Any]:
        """Extract route and endpoint information from ASGI scope."""
        try:
            route_context = {}
            
            # Get route from scope
            if 'route' in scope:
                route = scope['route']
                route_context['path'] = getattr(route, 'path', None)
                route_context['name'] = getattr(route, 'name', None)
                route_context['methods'] = getattr(route, 'methods', None)
            
            # Get endpoint function info
            if 'endpoint' in scope:
                endpoint = scope['endpoint']
                route_context['endpoint'] = {
                    'function': getattr(endpoint, '__name__', str(endpoint)),
                    'module': getattr(endpoint, '__module__', None),
                    'doc': getattr(endpoint, '__doc__', '')[:200] if hasattr(endpoint, '__doc__') else None,
                }
                
                # Check if it's a dependency
                if hasattr(endpoint, '__wrapped__'):
                    route_context['has_dependencies'] = True
            
            # Get path parameters
            if 'path_params' in scope:
                route_context['path_params'] = scope['path_params']
            
            return route_context
            
        except Exception:
            return {}
    
    def _extract_exception_context(self, exception) -> Dict[str, Any]:
        """Extract exception-specific context (validation errors, etc.)."""
        try:
            import time
            exc_context = {
                'type': type(exception).__name__,
                'message': str(exception),
            }
            
            # Handle Pydantic validation errors
            try:
                from fastapi.exceptions import RequestValidationError
                from pydantic import ValidationError
                
                if isinstance(exception, RequestValidationError):
                    exc_context['validation_errors'] = [
                        {
                            'loc': err['loc'],
                            'msg': err['msg'],
                            'type': err['type'],
                        }
                        for err in exception.errors()[:10]  # Limit to 10 errors
                    ]
                    exc_context['body'] = self._sanitize_body(exception.body) if hasattr(exception, 'body') else None
                    
                elif isinstance(exception, ValidationError):
                    exc_context['validation_errors'] = [
                        {
                            'loc': err['loc'],
                            'msg': err['msg'],
                            'type': err['type'],
                        }
                        for err in exception.errors()[:10]
                    ]
            except ImportError:
                pass
            
            # Handle HTTP exceptions
            try:
                from starlette.exceptions import HTTPException
                
                if isinstance(exception, HTTPException):
                    exc_context['status_code'] = exception.status_code
                    exc_context['detail'] = exception.detail
                    exc_context['headers'] = exception.headers if hasattr(exception, 'headers') else None
            except ImportError:
                pass
            
            return exc_context
            
        except Exception:
            return {}
    
    def _sanitize_cookies(self, cookies: Dict) -> Dict:
        """Sanitize cookies to avoid logging sensitive info."""
        safe_cookies = ['session', 'csrf', 'locale', 'theme']
        return {k: '***' if k not in safe_cookies else v[:10] + '...' if len(v) > 10 else v
                for k, v in cookies.items()}
    
    def _sanitize_body(self, body: Any) -> Any:
        """Sanitize request body to avoid logging sensitive data."""
        if body is None:
            return None
            
        if isinstance(body, dict):
            sensitive_keys = ['password', 'passwd', 'secret', 'token', 'key', 'api', 'credit']
            sanitized = {}
            for key, value in body.items():
                if any(s in key.lower() for s in sensitive_keys):
                    sanitized[key] = '***REDACTED***'
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_body(value)
                elif isinstance(value, list):
                    sanitized[key] = value[:3]  # Only first 3 items
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(body, list):
            return body[:5]  # Only first 5 items
        else:
            return str(body)[:1000]  # Truncate long strings