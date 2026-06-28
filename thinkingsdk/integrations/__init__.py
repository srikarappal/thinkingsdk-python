"""
Framework integrations for ThinkingSDK.

Provides enhanced context capture for popular web frameworks.
"""

from typing import Optional, Dict, Any, List
import importlib


class Integration:
    """Base class for framework integrations."""
    
    identifier = None  # Override in subclasses
    
    def __init__(self, **options):
        self.options = options
        
    def setup_once(self):
        """Called once when the integration is installed."""
        raise NotImplementedError
        
    def capture_context(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add framework-specific context to exception data."""
        return exception_data


class IntegrationRegistry:
    """Registry for managing framework integrations."""
    
    def __init__(self):
        self.integrations = {}
        self.auto_detect_frameworks()
        
    def auto_detect_frameworks(self):
        """Auto-detect installed frameworks and load integrations."""
        framework_map = {
            'django': 'thinkingsdk.integrations.django.DjangoIntegration',
            'flask': 'thinkingsdk.integrations.flask.FlaskIntegration',
            'fastapi': 'thinkingsdk.integrations.fastapi.FastAPIIntegration',
        }
        
        for package, integration_path in framework_map.items():
            try:
                # Check if framework is installed
                importlib.import_module(package)
                
                # Load the integration
                module_path, class_name = integration_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                integration_class = getattr(module, class_name)
                
                # Register the integration
                self.register(integration_class())
                
            except ImportError:
                # Framework not installed, skip
                pass
            except Exception:
                # Integration failed to load, skip
                pass
    
    def register(self, integration: Integration):
        """Register an integration."""
        if integration.identifier:
            self.integrations[integration.identifier] = integration
            integration.setup_once()
    
    def get_all_context(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get context from all registered integrations."""
        for integration in self.integrations.values():
            exception_data = integration.capture_context(exception_data)
        return exception_data


# Singleton registry
_registry = None

def get_integration_registry() -> IntegrationRegistry:
    """Get the singleton integration registry."""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
    return _registry