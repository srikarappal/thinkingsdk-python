"""
PII (Personally Identifiable Information) scrubbing for privacy protection.

Automatically detects and redacts sensitive information from events.
"""

import re
from typing import Any, Dict, List, Set, Pattern
import ipaddress
from typing import Optional


class PIIScrubber:
    """
    Scrubs PII and sensitive data from events before transmission.
    """
    
    # Sensitive key patterns (case-insensitive)
    SENSITIVE_KEY_PATTERNS = [
        'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
        'auth', 'authorization', 'credential', 'private_key', 'privatekey',
        'access_token', 'refresh_token', 'bearer', 'session', 'cookie',
        'ssn', 'social_security', 'tax_id', 'license', 'passport',
        'credit_card', 'card_number', 'cvv', 'cvc', 'pin',
        'bank_account', 'routing_number', 'iban', 'swift'
    ]
    
    # Regex patterns for common PII formats
    PII_PATTERNS = {
        'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
        'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        'phone_us': re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        'phone_intl': re.compile(r'\b\+[1-9]\d{1,14}\b'),
        'ipv4': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
        'ipv6': re.compile(r'(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}'),
        'jwt': re.compile(r'eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+'),
        'aws_key': re.compile(r'AKIA[0-9A-Z]{16}'),
        'aws_secret': re.compile(r'[A-Za-z0-9/+=]{40}'),
        'github_token': re.compile(r'ghp_[A-Za-z0-9]{36}'),
        'stripe_key': re.compile(r'(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{24,}'),
        'uuid': re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I),
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: Scrubbing configuration
                - enabled: Enable PII scrubbing (default: True)
                - custom_patterns: Additional regex patterns to scrub
                - custom_keys: Additional sensitive key names
                - excluded_keys: Keys to never scrub
                - scrub_ips: Whether to scrub IP addresses (default: False)
                - scrub_emails: Whether to scrub emails (default: True)
                - scrub_uuids: Whether to scrub UUIDs (default: False)
                - replacement: Replacement text (default: "[REDACTED]")
        """
        config = config or {}
        
        self.enabled = config.get('enabled', True)
        self.replacement = config.get('replacement', '[REDACTED]')
        self.scrub_ips = config.get('scrub_ips', False)
        self.scrub_emails = config.get('scrub_emails', True)
        self.scrub_uuids = config.get('scrub_uuids', False)
        
        # Build sensitive keys set
        self.sensitive_keys = set(self.SENSITIVE_KEY_PATTERNS)
        if 'custom_keys' in config:
            self.sensitive_keys.update(config['custom_keys'])
            
        # Excluded keys
        self.excluded_keys = set(config.get('excluded_keys', []))
        
        # Build patterns to use
        self.patterns = {}
        for name, pattern in self.PII_PATTERNS.items():
            # Skip certain patterns based on config
            if name == 'ipv4' and not self.scrub_ips:
                continue
            if name == 'ipv6' and not self.scrub_ips:
                continue
            if name == 'email' and not self.scrub_emails:
                continue
            if name == 'uuid' and not self.scrub_uuids:
                continue
                
            self.patterns[name] = pattern
            
        # Add custom patterns
        if 'custom_patterns' in config:
            for name, pattern_str in config['custom_patterns'].items():
                self.patterns[name] = re.compile(pattern_str)
                
        # Statistics
        self.stats = {
            'values_scrubbed': 0,
            'keys_scrubbed': 0,
            'patterns_matched': {}
        }
    
    def scrub_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrub PII from an event.
        
        Returns:
            Scrubbed event (modifies in place for efficiency)
        """
        if not self.enabled:
            return event
            
        # Scrub recursively
        self._scrub_value(event)
        return event
    
    def _scrub_value(self, obj: Any, key: str = None) -> Any:
        """Recursively scrub a value."""
        if isinstance(obj, dict):
            # Check each key-value pair
            for k, v in list(obj.items()):
                if k in self.excluded_keys:
                    continue
                    
                # Check if key name is sensitive
                if self._is_sensitive_key(k):
                    obj[k] = self._redact_value(v, reason=f"sensitive_key:{k}")
                    self.stats['keys_scrubbed'] += 1
                else:
                    # Recursively scrub the value
                    obj[k] = self._scrub_value(v, key=k)
                    
        elif isinstance(obj, list):
            # Scrub each item in list
            for i, item in enumerate(obj):
                obj[i] = self._scrub_value(item, key=key)
                
        elif isinstance(obj, str):
            # Check string for PII patterns
            scrubbed = self._scrub_string(obj)
            if scrubbed != obj:
                self.stats['values_scrubbed'] += 1
            return scrubbed
            
        return obj
    
    def _is_sensitive_key(self, key) -> bool:
        """Check if a key name indicates sensitive data."""
        # Only process string keys - ignore numeric/other key types
        if not isinstance(key, str):
            return False
            
        key_lower = key.lower()
        
        # Check exact matches and substrings
        for sensitive in self.sensitive_keys:
            if sensitive in key_lower:
                return True
                
        return False
    
    def _scrub_string(self, text: str) -> str:
        """Scrub PII patterns from a string."""
        if not text or not isinstance(text, str):
            return text
            
        scrubbed = text
        
        # Apply each pattern
        for pattern_name, pattern in self.patterns.items():
            matches = pattern.findall(scrubbed)
            if matches:
                # Special handling for certain types
                if pattern_name == 'email':
                    # Partially redact email (keep domain)
                    for match in matches:
                        parts = match.split('@')
                        if len(parts) == 2:
                            redacted = f"{self._partial_redact(parts[0])}@{parts[1]}"
                            scrubbed = scrubbed.replace(match, redacted)
                        else:
                            scrubbed = pattern.sub(self.replacement, scrubbed)
                            
                elif pattern_name == 'credit_card':
                    # Keep last 4 digits
                    for match in matches:
                        digits = re.sub(r'[^\d]', '', match)
                        if len(digits) >= 4:
                            redacted = f"****-****-****-{digits[-4:]}"
                            scrubbed = scrubbed.replace(match, redacted)
                        else:
                            scrubbed = pattern.sub(self.replacement, scrubbed)
                            
                elif pattern_name in ['ipv4', 'ipv6']:
                    # Validate it's actually an IP (not version number like 1.2.3.4)
                    for match in matches:
                        try:
                            ipaddress.ip_address(match)
                            scrubbed = scrubbed.replace(match, self.replacement)
                        except ValueError:
                            # Not a valid IP, skip
                            pass
                else:
                    # Default replacement
                    scrubbed = pattern.sub(self.replacement, scrubbed)
                    
                # Track statistics
                if pattern_name not in self.stats['patterns_matched']:
                    self.stats['patterns_matched'][pattern_name] = 0
                self.stats['patterns_matched'][pattern_name] += len(matches)
        return scrubbed
    
    def _redact_value(self, value: Any, reason: str = "") -> str:
        """Redact a sensitive value while preserving type info."""
        if value is None:
            return None
            
        type_name = type(value).__name__
        
        if isinstance(value, bool):
            return value  # Don't redact booleans
        elif isinstance(value, (int, float)):
            # Redact numbers but indicate type
            return f"[REDACTED_{type_name.upper()}]"
        elif isinstance(value, str):
            if len(value) > 0:
                # Show partial info for debugging
                return f"[REDACTED_len={len(value)}]"
            return value
        elif isinstance(value, (list, dict)):
            # Redact complex types
            return f"[REDACTED_{type_name.upper()}]"
        else:
            return self.replacement
    
    def _partial_redact(self, text: str, visible_chars: int = 2) -> str:
        """Partially redact text, keeping first few characters."""
        if len(text) <= visible_chars:
            return '*' * len(text)
        return text[:visible_chars] + '*' * (len(text) - visible_chars)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scrubbing statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'values_scrubbed': 0,
            'keys_scrubbed': 0,
            'patterns_matched': {}
        }
