# thinkingsdk/config_loader.py
import os
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import keyring

# Automatically load .env file if available
try:
    from dotenv import load_dotenv
    # Look for .env in current directory and parent directories
    current_dir = Path.cwd()
    for directory in [current_dir] + list(current_dir.parents):
        env_file = directory / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    # dotenv not installed, continue without it
    pass

logger = logging.getLogger("thinkingsdk.config")


class ConfigLoader:
    """Load and parse ThinkingSDK configuration from YAML files."""
    
    DEFAULT_CONFIG = {
        "enabled": True,
        "auto_start": False,
        "sampling_rate": 1.0,
        "api_key_source": "env:THINKINGSDK_API_KEY",
        "server_url": "http://localhost:8000",
        "environment": "development",
        "git_repositories": [],
        "tracking": {
            "mode": "manual",
            "include_modules": [],
            "include_functions": [],
            "exclude_patterns": ["test_*", "*_test.py", "__pycache__"],
            "capture_locals": True,
            "capture_returns": False,
            "capture_exceptions": True,
            "capture_performance": True,
            "capture_memory": False,
            "capture_call_patterns": True,
            "capture_source_lines": False,
            "capture_data_flow": False,
            "max_locals": 10,
            "max_local_length": 500,
            "max_stack_depth": 50,
        },
        "performance": {
            "slow_function_threshold_ms": 100,
            "hot_path_threshold_calls": 50,
            "memory_spike_threshold_mb": 100,
        },
        "privacy": {
            "redact_keys": ["password", "token", "api_key", "secret"],
            "sanitize_sql": True,
            "hash_user_identifiers": False,
        },
        "export": {
            "batch_size": 100,
            "flush_interval_seconds": 5,
            "max_queue_size": 10000,
            "timeout_seconds": 10,
            "retry_attempts": 3,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 60,
        },
        # Future feature - framework integrations not yet implemented
        # "integrations": {},
        "debug": False,
        "log_level": "WARNING",
        "custom_handlers": [],
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to config file. If None, searches for thinkingsdk.yaml
                        in current directory and parent directories.
        """
        self.config_path = self._find_config_file(config_path)
        self.config = self._load_config()
        self._validate_config()
        
    def _find_config_file(self, config_path: Optional[str] = None) -> Optional[Path]:
        """Find the configuration file."""
        if config_path:
            path = Path(config_path)
            if path.exists():
                logger.info(f"Using explicit config file: {path}")
                return path
            logger.warning(f"Config file not found: {config_path}")
            return None

        # Search for thinkingsdk.yaml in current and parent directories
        current_dir = Path.cwd()
        logger.debug(f"Searching for thinkingsdk.yaml starting from: {current_dir}")

        for directory in [current_dir] + list(current_dir.parents):
            config_file = directory / "thinkingsdk.yaml"
            if config_file.exists():
                logger.info(f"Found config file: {config_file}")
                return config_file

        logger.warning(f"No thinkingsdk.yaml found (searched from {current_dir} upwards). Using defaults - git_repositories will be empty!")
        return None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config = self.DEFAULT_CONFIG.copy()
        
        if not self.config_path:
            return config
            
        try:
            with open(self.config_path, 'r') as f:
                yaml_content = f.read()
                
            # Expand environment variables in YAML content
            yaml_content = self._expand_env_vars(yaml_content)
            
            # Parse YAML
            user_config = yaml.safe_load(yaml_content) or {}
            
            # Deep merge with defaults
            config = self._deep_merge(config, user_config)
            
            logger.info(f"Loaded config from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading config from {self.config_path}: {e}")
            logger.warning("Using default configuration")
            return config
            
    def _expand_env_vars(self, content: str) -> str:
        """
        Expand environment variables in the format ${VAR_NAME:-default_value}.
        
        Examples:
            ${ENV:-development} -> "production" if ENV="production", else "development"
            ${PORT:-8000} -> "8080" if PORT="8080", else "8000"
        """
        pattern = re.compile(r'\$\{([^}]+)\}')
        
        def replacer(match):
            var_expr = match.group(1)
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                return os.getenv(var_expr, match.group(0))
                
        return pattern.sub(replacer, content)
        
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Check required fields
        if not self.config.get("api_key_source"):
            raise ValueError("api_key_source is required in configuration")
            
        # Validate sampling rate
        sampling_rate = self.config.get("sampling_rate", 1.0)
        if not 0.0 <= sampling_rate <= 1.0:
            raise ValueError(f"sampling_rate must be between 0.0 and 1.0, got {sampling_rate}")
            
        # Validate tracking mode
        tracking_mode = self.config.get("tracking", {}).get("mode", "manual")
        if tracking_mode not in ["manual", "selective", "all"]:
            raise ValueError(f"Invalid tracking mode: {tracking_mode}")
            
        # Warn about insecure configurations
        if "api_key" in self.config:
            logger.warning("API key found directly in config! Use api_key_source with environment variables instead")
            
    def get_api_key(self) -> str:
        """
        Retrieve API key from the configured source.
        
        Supports:
            - env:VAR_NAME - Environment variable
            - keyring:service_name - System keyring
            - file:path - File path
            - aws:secretsmanager:name - AWS Secrets Manager
            - gcp:secretmanager:name - GCP Secret Manager
            - azure:keyvault:name - Azure Key Vault
        """
        source = self.config.get("api_key_source", "")
        
        if not source:
            raise ValueError("No api_key_source configured")
            
        try:
            if source.startswith("env:"):
                var_name = source[4:]
                api_key = os.getenv(var_name)
                if not api_key:
                    raise ValueError(f"Environment variable {var_name} not set")
                return api_key
                
            elif source.startswith("keyring:"):
                service = source[8:]
                try:
                    api_key = keyring.get_password(service, "api_key")
                    if not api_key:
                        raise ValueError(f"No API key found in keyring for service: {service}")
                    return api_key
                except Exception as e:
                    raise ValueError(f"Failed to retrieve key from keyring: {e}")
                    
            elif source.startswith("file:"):
                file_path = os.path.expanduser(source[5:])
                if not Path(file_path).exists():
                    raise ValueError(f"Key file not found: {file_path}")
                    
                # Check file permissions (should be readable only by owner)
                file_stat = os.stat(file_path)
                if file_stat.st_mode & 0o077:
                    logger.warning(f"Key file {file_path} has overly permissive permissions")
                    
                with open(file_path, 'r') as f:
                    return f.read().strip()
                    
            elif source.startswith("aws:"):
                # TODO: Implement AWS Secrets Manager integration
                raise NotImplementedError("AWS Secrets Manager not yet implemented")
                
            elif source.startswith("gcp:"):
                # TODO: Implement GCP Secret Manager integration
                raise NotImplementedError("GCP Secret Manager not yet implemented")
                
            elif source.startswith("azure:"):
                # TODO: Implement Azure Key Vault integration
                raise NotImplementedError("Azure Key Vault not yet implemented")
                
            else:
                # Assume it's a direct key (not recommended)
                if source.startswith("tsk_"):
                    logger.warning("API key appears to be directly in config. Use environment variables instead!")
                    return source
                raise ValueError(f"Unknown api_key_source format: {source}")
                
        except Exception as e:
            logger.error(f"Failed to retrieve API key: {e}")
            raise
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Examples:
            config.get("tracking.mode")  # Returns "selective"
            config.get("performance.slow_function_threshold_ms", 100)
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
                
        return value
        
    def get_tracking_config(self) -> Dict[str, Any]:
        """Get tracking-specific configuration."""
        return self.config.get("tracking", {})
        
    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance-specific configuration."""
        return self.config.get("performance", {})
        
    def get_export_config(self) -> Dict[str, Any]:
        """Get export/batching configuration."""
        return self.config.get("export", {})
        
    def is_enabled(self) -> bool:
        """Check if ThinkingSDK is enabled."""
        return self.config.get("enabled", True)
        
    def should_auto_start(self) -> bool:
        """Check if auto-start is enabled."""
        return self.config.get("auto_start", False)
        
    def __repr__(self) -> str:
        """String representation."""
        return f"ConfigLoader(config_path={self.config_path})"


# Convenience function for quick config loading
def load_config(config_path: Optional[str] = None) -> ConfigLoader:
    """Load ThinkingSDK configuration."""
    return ConfigLoader(config_path)
