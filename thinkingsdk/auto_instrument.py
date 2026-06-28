# thinkingsdk/auto_instrument.py
"""
Auto-instrumentation module for zero-code ThinkingSDK activation.

Usage:
    1. Set environment variable: THINKINGSDK_ENABLED=true
    2. Either:
       - Add to sitecustomize.py: import thinkingsdk.auto_instrument
       - Use -X importtime: python -X importtime=thinkingsdk.auto_instrument app.py
       - Set PYTHONPATH to include this module
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Check if auto-instrumentation should be enabled
ENABLED = os.environ.get('THINKINGSDK_ENABLED', '').lower() in ('true', '1', 'yes', 'on')
CONFIG_FILE = os.environ.get('THINKINGSDK_CONFIG_FILE', 'thinkingsdk.yaml')

logger = logging.getLogger('thinkingsdk.auto')


def should_instrument() -> bool:
    """Determine if auto-instrumentation should be activated."""
    if not ENABLED:
        return False
        
    # Check for opt-out markers
    if os.environ.get('THINKINGSDK_DISABLE_AUTO'):
        return False
        
    # Don't instrument in test environments unless explicitly enabled
    if 'pytest' in sys.modules or 'unittest' in sys.modules:
        if not os.environ.get('THINKINGSDK_INSTRUMENT_TESTS'):
            return False
            
    return True


def find_config() -> Optional[Path]:
    """Find the configuration file."""
    # Check explicit path
    if os.path.isabs(CONFIG_FILE):
        config_path = Path(CONFIG_FILE)
        if config_path.exists():
            return config_path
            
    # Search in common locations
    search_paths = [
        Path.cwd(),  # Current directory
        Path.cwd().parent,  # Parent directory
        Path.home() / '.thinkingsdk',  # User home
        Path('/etc/thinkingsdk'),  # System config
    ]
    
    for search_dir in search_paths:
        config_path = search_dir / CONFIG_FILE
        if config_path.exists():
            return config_path
            
    return None


def auto_start():
    """Automatically start ThinkingSDK instrumentation."""
    if not should_instrument():
        return
        
    try:
        # Import here to avoid circular dependencies
        import thinkingsdk
        
        # Check if already started
        if thinkingsdk.is_active():
            return
            
        # Find configuration
        config_path = find_config()
        
        if not config_path and not os.environ.get('THINKINGSDK_API_KEY'):
            logger.warning(
                "ThinkingSDK auto-instrumentation enabled but no config found "
                "and THINKINGSDK_API_KEY not set"
            )
            return
            
        # Start with auto-discovery
        thinkingsdk.start(
            config_file=str(config_path) if config_path else None,
            enable_logging=os.environ.get('THINKINGSDK_DEBUG', '').lower() in ('true', '1')
        )
        
        logger.info(f"ThinkingSDK auto-instrumentation started (config: {config_path})")
        
        # Register cleanup on exit
        import atexit
        atexit.register(thinkingsdk.stop)
        
    except Exception as e:
        # Never crash the application due to instrumentation
        logger.error(f"Failed to auto-start ThinkingSDK: {e}")
        if os.environ.get('THINKINGSDK_DEBUG'):
            import traceback
            traceback.print_exc()


# Auto-start when imported
auto_start()


# For use in sitecustomize.py
__all__ = ['auto_start']