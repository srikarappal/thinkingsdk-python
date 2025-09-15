# thinking_sdk_client/config.py
"""Configuration management for ThinkingSDK client."""

import os
from typing import Dict, Any, Optional


class Config:
    """Configuration class for ThinkingSDK client settings."""
    
    # Default configuration values
    DEFAULT_CONFIG = {
        # Event Queue settings
        'queue': {
            'maxsize': 10000,
            'drop_strategy': 'oldest',  # 'oldest' or 'newest'
        },
        
        # Instrumentation settings
        'instrumentation': {
            'max_locals': 5,
            'max_local_length': 120,
            'capture_returns': False,
            'sample_rate': 1.0,
            'ignore_patterns': [],
            'ignore_functions': [],
            'exceptions_only': True,  # MVP: Only capture exception events
        },
        
        # Strategic sampling settings for AI-agentic debugging
        'strategic_sampling': {
            'enabled': True,  # Enable intelligent filtering and sampling
            'environment': 'development',  # development, staging, production, high_scale
            'slow_function_threshold_ms': 100,  # Functions slower than this are always captured
            'custom_sampling_rates': {},  # Override default environment sampling rates
            'custom_capture_rules': {},   # Override default capture rules
            'always_patterns': [],        # Additional patterns for always capture
            'never_patterns': [],         # Additional patterns for never capture
            'remote_config_enabled': False,  # Enable server-controlled configuration
            'remote_config_poll_interval': 300,  # Seconds between config polls
        },
        
        # Background sender settings
        'sender': {
            'batch_size': 50,
            'max_batch_wait': 2.0,
            'retry_attempts': 3,
            'backoff_factor': 1.0,
            'circuit_breaker_threshold': 5,
            'circuit_breaker_timeout': 60,
            'request_timeout': 10,
            'exceptions_only': True,  # MVP: Only send exception events
        },
        
        # Global settings
        'enable_logging': False,
        'log_level': 'WARNING',
    }
    
    def __init__(self, custom_config: Optional[Dict[str, Any]] = None):
        """Initialize configuration with optional custom settings.
        
        Args:
            custom_config: Custom configuration to override defaults
        """
        self._config = self._merge_config(self.DEFAULT_CONFIG, custom_config or {})
        self._apply_env_overrides()
        
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Allow overriding key settings via environment variables
        env_mappings = {
            'THINKINGSDK_SAMPLE_RATE': ('instrumentation', 'sample_rate', float),
            'THINKINGSDK_BATCH_SIZE': ('sender', 'batch_size', int),
            'THINKINGSDK_QUEUE_SIZE': ('queue', 'maxsize', int),
            'THINKINGSDK_ENABLE_LOGGING': ('enable_logging', None, bool),
            'THINKINGSDK_LOG_LEVEL': ('log_level', None, str),
        }
        
        for env_var, (section, key, type_converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Special handling for boolean conversion
                    if type_converter == bool:
                        converted_value = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        converted_value = type_converter(value)
                        
                    if key is None:
                        self._config[section] = converted_value
                    else:
                        self._config[section][key] = converted_value
                except (ValueError, TypeError):
                    # Ignore invalid environment variable values
                    pass
                    
    def get(self, section: str, key: Optional[str] = None) -> Any:
        """Get a configuration value.
        
        Args:
            section: Configuration section name
            key: Optional key within the section
            
        Returns:
            Configuration value or entire section if key is None
        """
        if key is None:
            return self._config.get(section, {})
        return self._config.get(section, {}).get(key)
        
    def get_queue_config(self) -> Dict[str, Any]:
        """Get event queue configuration."""
        return self._config['queue'].copy()
        
    def get_instrumentation_config(self) -> Dict[str, Any]:
        """Get instrumentation configuration."""
        config = self._config['instrumentation'].copy()
        # Include git_repositories for repository context
        if 'git_repositories' in self._config:
            config['git_repositories'] = self._config['git_repositories']
        return config
        
    def get_sender_config(self) -> Dict[str, Any]:
        """Get background sender configuration."""
        return self._config['sender'].copy()
        
    def get_strategic_sampling_config(self) -> Dict[str, Any]:
        """Get strategic sampling configuration."""
        return self._config['strategic_sampling'].copy()
        
    def is_strategic_sampling_enabled(self) -> bool:
        """Check if strategic sampling is enabled."""
        return self._config.get('strategic_sampling', {}).get('enabled', True)
        
    def is_logging_enabled(self) -> bool:
        """Check if logging is enabled."""
        return self._config.get('enable_logging', False)
        
    def get_log_level(self) -> str:
        """Get the configured log level."""
        return self._config.get('log_level', 'WARNING')
        
    def to_dict(self) -> Dict[str, Any]:
        """Return the full configuration as a dictionary."""
        return self._config.copy()