# thinking_sdk_client/strategic_sampling.py
"""Strategic sampling and intelligent filtering for AI-agentic debugging."""

import os
import time
import random
from typing import Dict, Any, List, Set, Optional
from enum import Enum


class EventPriority(Enum):
    """Event priority levels for intelligent filtering."""
    ALWAYS = "always"        # Critical events - always captured
    SAMPLE = "sample"        # Normal events - sampled based on rate
    NEVER = "never"          # Framework/library events - never captured


class EnvironmentType(Enum):
    """Environment types with different sampling strategies."""
    DEVELOPMENT = "development"
    STAGING = "staging" 
    PRODUCTION = "production"
    HIGH_SCALE = "high_scale"


class StrategicSampler:
    """Implements intelligent sampling and filtering for AI-agentic debugging.
    
    Key Strategy:
    - ALWAYS capture: exceptions, slow functions, custom events (real-time AI analysis)
    - SAMPLE capture: normal function calls (reduced volume)
    - NEVER capture: framework internals, library calls (noise reduction)
    
    This enables real-time agentic remediation on critical events while
    maintaining cost efficiency and performance.
    """
    
    # Environment-based sampling rates for normal events
    SAMPLING_RATES = {
        EnvironmentType.DEVELOPMENT: 1.0,    # 100% sampling - full debugging context
        EnvironmentType.STAGING: 0.5,        # 50% sampling - catch integration issues
        EnvironmentType.PRODUCTION: 0.1,     # 10% sampling - minimal overhead
        EnvironmentType.HIGH_SCALE: 0.01,    # 1% sampling - enterprise efficiency
    }
    
    # Event classification rules for intelligent filtering
    CAPTURE_RULES = {
        EventPriority.ALWAYS: [
            "exceptions",           # All exceptions for immediate AI analysis
            "slow_functions",       # Performance issues for optimization
            "custom_events",        # Business logic events
            "errors",              # All error conditions
            "security_events",     # Security-related events
            "business_critical"    # Custom business-critical events
        ],
        EventPriority.SAMPLE: [
            "normal_function_calls", # Regular function execution
            "api_calls",            # API endpoint calls
            "database_queries",     # DB operations
            "user_interactions"     # User-triggered events
        ],
        EventPriority.NEVER: [
            "framework_internals",  # Flask/Django/FastAPI internals
            "library_calls",        # Third-party library calls
            "system_calls",         # Low-level system operations
            "logging_calls",        # Logging framework calls
            "test_framework"        # Testing framework calls
        ]
    }
    
    # Default patterns for automatic event classification
    DEFAULT_ALWAYS_PATTERNS = {
        # Exception patterns
        "exception", "error", "failed", "timeout", "abort",
        # Performance patterns  
        "slow", "bottleneck", "memory_spike", "cpu_spike",
        # Security patterns
        "auth", "security", "unauthorized", "forbidden",
        # Business patterns
        "payment", "order", "checkout", "critical"
    }
    
    DEFAULT_NEVER_PATTERNS = {
        # Framework patterns
        "flask", "django", "fastapi", "starlette", "werkzeug",
        "sqlalchemy", "alembic", "celery", "redis",
        # Library patterns
        "requests", "urllib", "json", "logging", "threading",
        # System patterns
        "__pycache__", "site-packages", "dist-packages",
        # Test patterns
        "pytest", "unittest", "test_", "_test"
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize strategic sampler with configuration.
        
        Args:
            config: Configuration dictionary with optional settings:
                - environment: Environment type (development, staging, production, high_scale)
                - custom_sampling_rates: Override default sampling rates
                - custom_capture_rules: Override default capture rules  
                - slow_function_threshold_ms: Threshold for slow function detection
                - always_patterns: Additional patterns for ALWAYS classification
                - never_patterns: Additional patterns for NEVER classification
        """
        self.config = config or {}
        
        # Determine environment
        env_name = self.config.get('environment', os.getenv('ENV', 'development')).lower()
        self.environment = self._parse_environment(env_name)
        
        # Configure sampling rates
        custom_rates = self.config.get('custom_sampling_rates', {})
        self.sampling_rates = {**self.SAMPLING_RATES, **custom_rates}
        
        # Configure capture rules
        custom_rules = self.config.get('custom_capture_rules', {})
        self.capture_rules = self._merge_capture_rules(custom_rules)
        
        # Performance thresholds
        self.slow_function_threshold_ms = self.config.get('slow_function_threshold_ms', 100)
        
        # Event classification patterns
        self.always_patterns = self.DEFAULT_ALWAYS_PATTERNS | set(
            self.config.get('always_patterns', [])
        )
        self.never_patterns = self.DEFAULT_NEVER_PATTERNS | set(
            self.config.get('never_patterns', [])
        )
        
        # Sampling state
        self._sample_counter = 0
        self._last_sample_decision = {}
        
    def _parse_environment(self, env_name: str) -> EnvironmentType:
        """Parse environment name to EnvironmentType."""
        env_mapping = {
            'dev': EnvironmentType.DEVELOPMENT,
            'development': EnvironmentType.DEVELOPMENT,
            'local': EnvironmentType.DEVELOPMENT,
            'stage': EnvironmentType.STAGING,
            'staging': EnvironmentType.STAGING,
            'test': EnvironmentType.STAGING,
            'prod': EnvironmentType.PRODUCTION,
            'production': EnvironmentType.PRODUCTION,
            'live': EnvironmentType.PRODUCTION,
            'scale': EnvironmentType.HIGH_SCALE,
            'high_scale': EnvironmentType.HIGH_SCALE,
            'enterprise': EnvironmentType.HIGH_SCALE
        }
        return env_mapping.get(env_name, EnvironmentType.DEVELOPMENT)
    
    def _merge_capture_rules(self, custom_rules: Dict[str, List[str]]) -> Dict[EventPriority, Set[str]]:
        """Merge default and custom capture rules."""
        merged_rules = {}
        
        for priority in EventPriority:
            default_events = set(self.CAPTURE_RULES.get(priority, []))
            custom_events = set(custom_rules.get(priority.value, []))
            merged_rules[priority] = default_events | custom_events
            
        return merged_rules
    
    def should_capture_event(self, event_info: Dict[str, Any]) -> bool:
        """Determine if an event should be captured based on strategic sampling.
        
        Args:
            event_info: Event information dictionary containing:
                - event: Event type ('call', 'return', 'exception')
                - func: Function name
                - file: Source file name
                - execution_time_ms: Execution time (if available)
                - exception: Exception information (if applicable)
        
        Returns:
            True if event should be captured, False otherwise
        """
        # Classify event priority
        priority = self._classify_event_priority(event_info)
        
        # Apply capture rules based on priority
        if priority == EventPriority.NEVER:
            return False
        elif priority == EventPriority.ALWAYS:
            return True
        elif priority == EventPriority.SAMPLE:
            return self._should_sample()
        
        # Default to sampling for unknown events
        return self._should_sample()
    
    def _classify_event_priority(self, event_info: Dict[str, Any]) -> EventPriority:
        """Classify event priority for capture decision.
        
        Uses multiple strategies:
        1. Exception detection - always capture
        2. Performance detection - slow functions always captured
        3. Pattern matching - file/function patterns
        4. Explicit classification - user-defined rules
        """
        func_name = event_info.get('func', '').lower()
        file_name = event_info.get('file', '').lower()
        event_type = event_info.get('event', '')
        
        # Strategy 1: Exception events are always captured
        if event_type == 'exception' or event_info.get('exception'):
            return EventPriority.ALWAYS
        
        # Strategy 2: Slow function detection
        execution_time_ms = event_info.get('execution_time_ms', 0)
        if execution_time_ms > self.slow_function_threshold_ms:
            return EventPriority.ALWAYS
        
        # Strategy 3: Pattern-based classification
        
        # Check NEVER patterns first (performance optimization)
        full_context = f"{file_name} {func_name}"
        for pattern in self.never_patterns:
            if pattern in full_context:
                return EventPriority.NEVER
        
        # Check ALWAYS patterns
        for pattern in self.always_patterns:
            if pattern in full_context:
                return EventPriority.ALWAYS
        
        # Strategy 4: Explicit classification based on event metadata
        if event_info.get('is_custom_event'):
            return EventPriority.ALWAYS
        
        if event_info.get('is_security_event'):
            return EventPriority.ALWAYS
        
        if event_info.get('is_business_critical'):
            return EventPriority.ALWAYS
        
        # Default: sample normal events
        return EventPriority.SAMPLE
    
    def _should_sample(self) -> bool:
        """Determine if a sample-priority event should be captured."""
        sampling_rate = self.sampling_rates.get(self.environment, 0.1)
        
        if sampling_rate >= 1.0:
            return True
        if sampling_rate <= 0.0:
            return False
        
        # Use deterministic sampling based on counter
        self._sample_counter += 1
        return (self._sample_counter * sampling_rate) % 1.0 < sampling_rate
    
    def get_sampling_stats(self) -> Dict[str, Any]:
        """Get current sampling statistics."""
        return {
            'environment': self.environment.value,
            'sampling_rate': self.sampling_rates.get(self.environment),
            'sample_counter': self._sample_counter,
            'slow_function_threshold_ms': self.slow_function_threshold_ms,
            'capture_rules': {
                priority.value: list(events) 
                for priority, events in self.capture_rules.items()
            }
        }
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update sampler configuration at runtime (for server-controlled updates).
        
        Args:
            new_config: New configuration to merge with existing config
        """
        # Update environment if provided
        if 'environment' in new_config:
            env_name = new_config['environment'].lower()
            self.environment = self._parse_environment(env_name)
        
        # Update sampling rates
        if 'custom_sampling_rates' in new_config:
            self.sampling_rates.update(new_config['custom_sampling_rates'])
        
        # Update thresholds
        if 'slow_function_threshold_ms' in new_config:
            self.slow_function_threshold_ms = new_config['slow_function_threshold_ms']
        
        # Update patterns
        if 'always_patterns' in new_config:
            self.always_patterns.update(new_config['always_patterns'])
        
        if 'never_patterns' in new_config:
            self.never_patterns.update(new_config['never_patterns'])
    
    def mark_custom_event(self, event_info: Dict[str, Any]) -> None:
        """Mark an event as custom/business-critical for always capture."""
        event_info['is_custom_event'] = True
    
    def mark_security_event(self, event_info: Dict[str, Any]) -> None:
        """Mark an event as security-related for always capture."""
        event_info['is_security_event'] = True
    
    def mark_business_critical(self, event_info: Dict[str, Any]) -> None:
        """Mark an event as business-critical for always capture."""
        event_info['is_business_critical'] = True


class RemoteConfigManager:
    """Manages runtime configuration updates from ThinkingSDK server.
    
    Enables server to dynamically adjust client sampling rates and capture rules
    without requiring new client releases.
    """
    
    def __init__(self, api_client=None, poll_interval_seconds: int = 300):
        """Initialize remote config manager.
        
        Args:
            api_client: API client for server communication
            poll_interval_seconds: How often to check for config updates
        """
        self.api_client = api_client
        self.poll_interval = poll_interval_seconds
        self._last_poll = 0
        self._current_config_version = None
    
    def get_remote_config(self) -> Optional[Dict[str, Any]]:
        """Fetch latest configuration from server.
        
        Returns:
            Remote configuration dict or None if unavailable
        """
        if not self.api_client:
            return None
        
        current_time = time.time()
        if current_time - self._last_poll < self.poll_interval:
            return None
        
        try:
            # Call server API to get latest config
            response = self.api_client.get('/api/v1/client-config')
            if response and 'config' in response:
                config = response['config']
                config_version = response.get('version')
                
                # Only return config if it's a new version
                if config_version != self._current_config_version:
                    self._current_config_version = config_version
                    self._last_poll = current_time
                    return config
            
            self._last_poll = current_time
            return None
            
        except Exception:
            # Fail silently - don't break client if server is unavailable
            self._last_poll = current_time
            return None