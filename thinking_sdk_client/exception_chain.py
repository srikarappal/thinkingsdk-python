"""
Exception chaining support for ThinkingSDK.

Captures the full chain of exceptions including __cause__ and __context__,
similar to Sentry's implementation but adapted for TSDK's architecture.

WHAT IS EXCEPTION CHAINING?
===========================
Python 3+ supports exception chaining to preserve error context when one exception 
leads to another. There are two types:

1. EXPLICIT CHAINING (using 'from'):
   try:
       config = json.load(file)  # Raises JSONDecodeError
   except JSONDecodeError as e:
       raise ConfigError("Invalid config file") from e
   
   Result chain: ConfigError → JSONDecodeError
   The JSONDecodeError is stored in ConfigError.__cause__

2. IMPLICIT CHAINING (exception during exception handling):
   try:
       process_data()  # Raises ValueError
   except ValueError:
       log_to_file(data)  # This raises FileNotFoundError
   
   Result chain: FileNotFoundError → ValueError
   The ValueError is stored in FileNotFoundError.__context__

WHY THIS MATTERS:
Without exception chaining, TSDK only sees the final exception (ConfigError or 
FileNotFoundError) and loses the root cause (JSONDecodeError or ValueError).
With chaining, the AI gets the full story and can provide better fixes.

EXAMPLE CHAIN:
User code tries to load config → JSON parse fails → Config error raised
The chain would be: [ConfigError, JSONDecodeError]
This tells AI: "Config loading failed BECAUSE of invalid JSON syntax"
"""

import sys
import traceback
from typing import List, Tuple, Optional, Dict, Any, Set


class ExceptionChainProcessor:
    """Processes exception chains to capture full error context."""
    
    @staticmethod
    def extract_exception_chain(exc_info: Tuple) -> List[Dict[str, Any]]:
        """
        Extract the full exception chain including causes and contexts.
        
        Args:
            exc_info: The (type, value, traceback) tuple from sys.exc_info()
            
        Returns:
            List of exception dictionaries in the chain, from most recent to root cause
        """
        chain = []
        seen_exceptions = set()  # Prevent infinite loops
        
        exc_type, exc_value, exc_tb = exc_info
        
        # Walk through the exception chain
        while exc_value is not None:
            # Create unique ID for this exception to detect cycles
            exc_id = id(exc_value)
            
            if exc_id in seen_exceptions:
                # Circular reference detected, stop processing
                break
                
            seen_exceptions.add(exc_id)
            
            # Extract exception data
            exception_data = ExceptionChainProcessor._extract_single_exception(
                exc_type, exc_value, exc_tb
            )
            chain.append(exception_data)
            
            # Determine next exception in chain
            # Python's exception chaining: __cause__ takes precedence over __context__
            next_exc = None
            
            if hasattr(exc_value, '__cause__') and exc_value.__cause__ is not None:
                # Explicit chaining with "raise ... from ..."
                next_exc = exc_value.__cause__
                exception_data['chained_via'] = 'cause'
            elif hasattr(exc_value, '__context__') and exc_value.__context__ is not None:
                # Implicit chaining (exception during exception handling)
                # Only use context if not suppressed
                if not getattr(exc_value, '__suppress_context__', False):
                    next_exc = exc_value.__context__
                    exception_data['chained_via'] = 'context'
            
            if next_exc is None:
                break
                
            # Get type and traceback for next exception
            exc_type = type(next_exc)
            exc_value = next_exc
            
            # Try to get traceback from the exception object
            exc_tb = getattr(next_exc, '__traceback__', None)
            
        return chain
    
    @staticmethod
    def _extract_single_exception(exc_type, exc_value, exc_tb) -> Dict[str, Any]:
        """
        Extract data from a single exception.
        
        Args:
            exc_type: Exception class
            exc_value: Exception instance
            exc_tb: Traceback object
            
        Returns:
            Dictionary with exception details
        """
        # Get exception type name
        if exc_type:
            type_name = exc_type.__name__
            module = exc_type.__module__
            if module and module != 'builtins':
                full_type = f"{module}.{type_name}"
            else:
                full_type = type_name
        else:
            type_name = 'Unknown'
            full_type = 'Unknown'
        
        # Get exception message
        try:
            message = str(exc_value)
        except:
            message = '<unprintable exception>'
        
        # Extract traceback
        tb_lines = []
        structured_tb = []
        
        if exc_tb:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            
            # Extract structured traceback for better analysis
            for frame_summary in traceback.extract_tb(exc_tb):
                structured_tb.append({
                    'file': frame_summary.filename,
                    'line': frame_summary.lineno,
                    'func': frame_summary.name,
                    'code': frame_summary.line
                })
        
        exception_dict = {
            'type': type_name,
            'full_type': full_type,
            'message': message,
            'traceback': tb_lines,
            'structured_traceback': structured_tb
        }
        
        # Add any custom attributes from the exception
        if hasattr(exc_value, '__dict__'):
            custom_attrs = {}
            for key, value in exc_value.__dict__.items():
                if not key.startswith('_'):
                    try:
                        # Only include serializable attributes
                        custom_attrs[key] = str(value)
                    except:
                        pass
            
            if custom_attrs:
                exception_dict['attributes'] = custom_attrs
        
        return exception_dict
    
    @staticmethod
    def format_chain_for_display(chain: List[Dict[str, Any]]) -> str:
        """
        Format exception chain for human-readable display.
        
        Args:
            chain: List of exception dictionaries
            
        Returns:
            Formatted string showing the exception chain
        """
        if not chain:
            return "No exception chain"
        
        parts = []
        
        for i, exc in enumerate(chain):
            if i == 0:
                parts.append(f"Exception: {exc['type']}: {exc['message']}")
            else:
                chained_via = exc.get('chained_via', 'unknown')
                if chained_via == 'cause':
                    parts.append(f"\n↳ Caused by: {exc['type']}: {exc['message']}")
                elif chained_via == 'context':
                    parts.append(f"\n↳ During handling of: {exc['type']}: {exc['message']}")
                else:
                    parts.append(f"\n↳ Related: {exc['type']}: {exc['message']}")
        
        return ''.join(parts)
    
    @staticmethod
    def get_root_cause(chain: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Get the root cause exception from the chain.
        
        Args:
            chain: List of exception dictionaries
            
        Returns:
            The root cause exception or None
        """
        if chain:
            return chain[-1]
        return None
    
    @staticmethod
    def has_exception_type(chain: List[Dict[str, Any]], exception_type: str) -> bool:
        """
        Check if a specific exception type exists in the chain.
        
        Args:
            chain: List of exception dictionaries
            exception_type: Exception type name to search for
            
        Returns:
            True if the exception type is found in the chain
        """
        for exc in chain:
            if exc.get('type') == exception_type or exc.get('full_type') == exception_type:
                return True
        return False


def test_exception_chaining():
    """Test the exception chain processor."""
    
    print("Testing Exception Chaining:\n")
    
    # Test 1: Simple explicit chaining
    print("1. Explicit chaining (raise ... from ...):")
    try:
        try:
            int("not a number")
        except ValueError as e:
            raise RuntimeError("Failed to parse number") from e
    except Exception:
        exc_info = sys.exc_info()
        chain = ExceptionChainProcessor.extract_exception_chain(exc_info)
        print(ExceptionChainProcessor.format_chain_for_display(chain))
        print(f"   Chain length: {len(chain)}")
        print()
    
    # Test 2: Implicit chaining
    print("2. Implicit chaining (exception during exception):")
    try:
        try:
            1 / 0
        except ZeroDivisionError:
            undefined_variable  # This will cause NameError
    except Exception:
        exc_info = sys.exc_info()
        chain = ExceptionChainProcessor.extract_exception_chain(exc_info)
        print(ExceptionChainProcessor.format_chain_for_display(chain))
        print(f"   Chain length: {len(chain)}")
        print()
    
    # Test 3: Multi-level chaining
    print("3. Multi-level chaining:")
    try:
        try:
            try:
                open("/nonexistent/file.txt")
            except FileNotFoundError as e:
                raise IOError("Cannot read config") from e
        except IOError as e:
            raise RuntimeError("Application startup failed") from e
    except Exception:
        exc_info = sys.exc_info()
        chain = ExceptionChainProcessor.extract_exception_chain(exc_info)
        print(ExceptionChainProcessor.format_chain_for_display(chain))
        print(f"   Chain length: {len(chain)}")
        
        # Test helper methods
        root = ExceptionChainProcessor.get_root_cause(chain)
        print(f"   Root cause: {root['type']}: {root['message']}")
        
        has_io = ExceptionChainProcessor.has_exception_type(chain, 'IOError')
        print(f"   Has IOError: {has_io}")


if __name__ == "__main__":
    test_exception_chaining()