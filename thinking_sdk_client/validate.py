#!/usr/bin/env python3
# thinking_sdk_client/validate.py
"""
Deployment validation and diagnostic tools for ThinkingSDK.

Usage:
    python -m thinking_sdk_client.validate
    
    Or programmatically:
    from thinking_sdk_client.validate import validate_deployment
    validate_deployment()
"""

import sys
import os
import time
import json
import traceback
from pathlib import Path
from typing import Dict, Any, List, Tuple
import subprocess
import platform

try:
    import requests
except ImportError:
    requests = None


class ValidationResult:
    """Result of a validation check."""
    
    def __init__(self, name: str, passed: bool, message: str, details: Any = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details
    
    def __str__(self):
        status = "✅" if self.passed else "❌"
        return f"{status} {self.name}: {self.message}"


class DeploymentValidator:
    """Validates ThinkingSDK deployment and configuration."""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.results: List[ValidationResult] = []
        
    def validate_all(self) -> bool:
        """Run all validation checks."""
        print("🔍 ThinkingSDK Deployment Validation\n")
        print("=" * 50)
        
        # Run checks
        self.check_python_version()
        self.check_installation()
        self.check_dependencies()
        self.check_configuration()
        self.check_api_key()
        self.check_server_connectivity()
        self.check_permissions()
        self.check_instrumentation()
        self.send_test_event()
        self.check_performance()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Validation Summary\n")
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        for result in self.results:
            print(result)
            if result.details and not result.passed:
                print(f"   Details: {result.details}")
        
        print(f"\n✨ {passed}/{total} checks passed")
        
        return passed == total
    
    def check_python_version(self) -> None:
        """Check Python version compatibility."""
        version = sys.version_info
        
        if version >= (3, 7):
            self.results.append(ValidationResult(
                "Python Version",
                True,
                f"Python {version.major}.{version.minor}.{version.micro}"
            ))
        else:
            self.results.append(ValidationResult(
                "Python Version",
                False,
                f"Python {version.major}.{version.minor} (requires 3.7+)",
                "Upgrade Python to 3.7 or higher"
            ))
    
    def check_installation(self) -> None:
        """Check if ThinkingSDK is properly installed."""
        try:
            import thinking_sdk_client
            version = getattr(thinking_sdk_client, '__version__', 'unknown')
            
            self.results.append(ValidationResult(
                "ThinkingSDK Installation",
                True,
                f"Version {version} installed"
            ))
        except ImportError as e:
            self.results.append(ValidationResult(
                "ThinkingSDK Installation",
                False,
                "Not installed",
                f"Run: pip install thinking-sdk-client"
            ))
    
    def check_dependencies(self) -> None:
        """Check required dependencies."""
        required = {
            'requests': 'HTTP client',
            'psutil': 'System monitoring',
            'yaml': 'Configuration',
        }
        
        missing = []
        for module, description in required.items():
            try:
                __import__(module)
            except ImportError:
                missing.append(f"{module} ({description})")
        
        if missing:
            self.results.append(ValidationResult(
                "Dependencies",
                False,
                f"Missing: {', '.join(missing)}",
                f"Run: pip install {' '.join(m.split()[0] for m in missing)}"
            ))
        else:
            self.results.append(ValidationResult(
                "Dependencies",
                True,
                "All required dependencies installed"
            ))
    
    def check_configuration(self) -> None:
        """Check configuration file."""
        from .config_loader import ConfigLoader
        
        try:
            loader = ConfigLoader(self.config_file)
            
            if loader.config_path:
                self.results.append(ValidationResult(
                    "Configuration File",
                    True,
                    f"Found at {loader.config_path}"
                ))
            else:
                self.results.append(ValidationResult(
                    "Configuration File",
                    True,
                    "Using defaults (no config file found)"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                "Configuration File",
                False,
                f"Error loading config: {e}",
                "Check YAML syntax and file permissions"
            ))
    
    def check_api_key(self) -> None:
        """Check API key configuration."""
        from .config_loader import ConfigLoader
        
        try:
            loader = ConfigLoader(self.config_file)
            api_key = loader.get_api_key()
            
            if api_key:
                # Mask the key for security
                masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
                
                self.results.append(ValidationResult(
                    "API Key",
                    True,
                    f"Configured ({masked})"
                ))
            else:
                self.results.append(ValidationResult(
                    "API Key",
                    False,
                    "Not configured",
                    "Set THINKINGSDK_API_KEY environment variable"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                "API Key",
                False,
                f"Error: {e}",
                "Check api_key_source configuration"
            ))
    
    def check_server_connectivity(self) -> None:
        """Check connectivity to ThinkingSDK server."""
        if not requests:
            self.results.append(ValidationResult(
                "Server Connectivity",
                False,
                "requests library not installed",
                "Run: pip install requests"
            ))
            return
        
        from .config_loader import ConfigLoader
        
        try:
            loader = ConfigLoader(self.config_file)
            server_url = loader.get("server_url", "http://localhost:8000")
            
            # Try health endpoint
            response = requests.get(
                f"{server_url}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                self.results.append(ValidationResult(
                    "Server Connectivity",
                    True,
                    f"Connected to {server_url}",
                    data
                ))
            else:
                self.results.append(ValidationResult(
                    "Server Connectivity",
                    False,
                    f"Server returned {response.status_code}",
                    "Check server status"
                ))
                
        except requests.ConnectionError:
            self.results.append(ValidationResult(
                "Server Connectivity",
                False,
                "Cannot connect to server",
                f"Check if server is running at {server_url}"
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                "Server Connectivity",
                False,
                f"Error: {e}",
                "Check network and server configuration"
            ))
    
    def check_permissions(self) -> None:
        """Check file system permissions."""
        issues = []
        
        # Check if we can write to temp directory
        temp_dir = Path("/tmp") if platform.system() != "Windows" else Path(os.environ.get("TEMP", "."))
        try:
            test_file = temp_dir / f"thinkingsdk_test_{os.getpid()}.tmp"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            issues.append(f"Cannot write to temp directory: {e}")
        
        # Check if we can read config file
        from .config_loader import ConfigLoader
        try:
            loader = ConfigLoader(self.config_file)
            if loader.config_path and not os.access(loader.config_path, os.R_OK):
                issues.append(f"Cannot read config file: {loader.config_path}")
        except Exception:
            pass
        
        if issues:
            self.results.append(ValidationResult(
                "File Permissions",
                False,
                "; ".join(issues)
            ))
        else:
            self.results.append(ValidationResult(
                "File Permissions",
                True,
                "All required permissions OK"
            ))
    
    def check_instrumentation(self) -> None:
        """Test basic instrumentation."""
        try:
            import thinking_sdk_client
            
            # Start instrumentation
            thinking_sdk_client.start()
            
            # Test function
            def test_func():
                return "test"
            
            result = test_func()
            
            # Get stats
            stats = thinking_sdk_client.get_stats()
            
            thinking_sdk_client.stop()
            
            if stats.get('instrumentation', {}).get('active'):
                self.results.append(ValidationResult(
                    "Instrumentation",
                    True,
                    "Successfully instrumenting code"
                ))
            else:
                self.results.append(ValidationResult(
                    "Instrumentation",
                    False,
                    "Instrumentation not active",
                    stats
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                "Instrumentation",
                False,
                f"Error: {e}",
                traceback.format_exc()
            ))
    
    def send_test_event(self) -> None:
        """Send a test event to the server."""
        try:
            import thinking_sdk_client
            from .config_loader import ConfigLoader
            
            loader = ConfigLoader(self.config_file)
            
            # Start SDK
            thinking_sdk_client.start(config_file=self.config_file)
            
            # Generate test event
            def test_function():
                raise ValueError("Test exception for validation")
            
            try:
                test_function()
            except ValueError:
                pass  # Expected
            
            # Wait for event to be sent
            time.sleep(2)
            
            # Check if event was queued
            stats = thinking_sdk_client.get_stats()
            event_count = stats.get('queue', {}).get('total_pushed', 0)
            
            thinking_sdk_client.stop()
            
            if event_count > 0:
                self.results.append(ValidationResult(
                    "Test Event",
                    True,
                    f"Successfully sent {event_count} events"
                ))
            else:
                self.results.append(ValidationResult(
                    "Test Event",
                    False,
                    "No events captured",
                    "Check instrumentation configuration"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                "Test Event",
                False,
                f"Error: {e}"
            ))
    
    def check_performance(self) -> None:
        """Check performance overhead."""
        try:
            from .performance_monitor import benchmark_instrumentation_overhead
            
            print("\n⏱️  Running performance benchmark...")
            results = benchmark_instrumentation_overhead()
            
            overhead_percent = results['overhead_percent']
            memory_overhead = results['memory_overhead_mb']
            
            if overhead_percent < 5 and memory_overhead < 50:
                self.results.append(ValidationResult(
                    "Performance",
                    True,
                    f"Overhead: {overhead_percent:.1f}% CPU, {memory_overhead:.1f}MB memory"
                ))
            else:
                self.results.append(ValidationResult(
                    "Performance",
                    False,
                    f"High overhead: {overhead_percent:.1f}% CPU, {memory_overhead:.1f}MB memory",
                    "Consider adjusting sampling rate or configuration"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                "Performance",
                False,
                f"Could not benchmark: {e}"
            ))


def validate_deployment(config_file: str = None) -> bool:
    """
    Validate ThinkingSDK deployment.
    
    Returns:
        True if all checks pass
    """
    validator = DeploymentValidator(config_file)
    return validator.validate_all()


def diagnose_issue(error_message: str) -> str:
    """
    Diagnose common issues based on error messages.
    
    Returns:
        Diagnostic advice
    """
    diagnostics = {
        "api_key": "Set THINKINGSDK_API_KEY environment variable or configure api_key_source in thinkingsdk.yaml",
        "connection": "Check if ThinkingSDK server is running and accessible",
        "import": "Install ThinkingSDK: pip install thinking-sdk-client",
        "permission": "Check file permissions and ensure the process has write access",
        "config": "Check YAML syntax in thinkingsdk.yaml",
    }
    
    error_lower = error_message.lower()
    
    for key, advice in diagnostics.items():
        if key in error_lower:
            return advice
    
    return "Check the documentation or contact support"


# CLI interface
def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate ThinkingSDK deployment")
    parser.add_argument(
        "--config",
        help="Path to configuration file",
        default=None
    )
    parser.add_argument(
        "--diagnose",
        help="Diagnose an error message",
        default=None
    )
    
    args = parser.parse_args()
    
    if args.diagnose:
        advice = diagnose_issue(args.diagnose)
        print(f"💡 Diagnosis: {advice}")
    else:
        success = validate_deployment(args.config)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()