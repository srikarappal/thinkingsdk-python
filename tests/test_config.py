# tests/test_config.py
"""Tests for Config component."""

import unittest
import os
from unittest.mock import patch
from thinkingsdk.config import Config
from tests.test_utils import IsolatedTestCase


class TestConfig(IsolatedTestCase):
    """Test cases for Config class."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = Config()
        
        # Test queue defaults
        queue_config = config.get_queue_config()
        self.assertEqual(queue_config['maxsize'], 10000)
        self.assertEqual(queue_config['drop_strategy'], 'oldest')
        
        # Test instrumentation defaults
        instr_config = config.get_instrumentation_config()
        self.assertEqual(instr_config['max_locals'], 5)
        self.assertEqual(instr_config['max_local_length'], 120)
        self.assertFalse(instr_config['capture_returns'])
        self.assertEqual(instr_config['sample_rate'], 1.0)
        
        # Test sender defaults
        sender_config = config.get_sender_config()
        self.assertEqual(sender_config['batch_size'], 50)
        self.assertEqual(sender_config['max_batch_wait'], 2.0)
        self.assertEqual(sender_config['retry_attempts'], 3)
        
        # Test global defaults
        self.assertFalse(config.is_logging_enabled())
        self.assertEqual(config.get_log_level(), 'WARNING')

    def test_custom_configuration(self):
        """Test configuration with custom values."""
        custom_config = {
            'queue': {
                'maxsize': 20000,
                'drop_strategy': 'newest'
            },
            'instrumentation': {
                'max_locals': 10,
                'sample_rate': 0.5,
                'capture_returns': True
            },
            'sender': {
                'batch_size': 100,
                'retry_attempts': 5
            },
            'enable_logging': True,
            'log_level': 'DEBUG'
        }
        
        config = Config(custom_config)
        
        # Test queue config
        queue_config = config.get_queue_config()
        self.assertEqual(queue_config['maxsize'], 20000)
        self.assertEqual(queue_config['drop_strategy'], 'newest')
        
        # Test instrumentation config
        instr_config = config.get_instrumentation_config()
        self.assertEqual(instr_config['max_locals'], 10)
        self.assertEqual(instr_config['sample_rate'], 0.5)
        self.assertTrue(instr_config['capture_returns'])
        
        # Test sender config
        sender_config = config.get_sender_config()
        self.assertEqual(sender_config['batch_size'], 100)
        self.assertEqual(sender_config['retry_attempts'], 5)
        
        # Test global config
        self.assertTrue(config.is_logging_enabled())
        self.assertEqual(config.get_log_level(), 'DEBUG')

    def test_partial_custom_configuration(self):
        """Test configuration with partial custom values."""
        custom_config = {
            'instrumentation': {
                'sample_rate': 0.8  # Only override sample_rate
            }
        }
        
        config = Config(custom_config)
        
        # Custom value should be applied
        instr_config = config.get_instrumentation_config()
        self.assertEqual(instr_config['sample_rate'], 0.8)
        
        # Default values should remain
        self.assertEqual(instr_config['max_locals'], 5)
        self.assertEqual(instr_config['max_local_length'], 120)

    def test_nested_configuration_merge(self):
        """Test that nested dictionaries are properly merged."""
        custom_config = {
            'sender': {
                'batch_size': 75,
                # Don't specify other sender config
            }
        }
        
        config = Config(custom_config)
        sender_config = config.get_sender_config()
        
        # Custom value should be applied
        self.assertEqual(sender_config['batch_size'], 75)
        
        # Default values should remain for unspecified keys
        self.assertEqual(sender_config['max_batch_wait'], 2.0)
        self.assertEqual(sender_config['retry_attempts'], 3)

    @patch.dict(os.environ, {
        'THINKINGSDK_SAMPLE_RATE': '0.3',
        'THINKINGSDK_BATCH_SIZE': '25',
        'THINKINGSDK_QUEUE_SIZE': '5000',
        'THINKINGSDK_ENABLE_LOGGING': 'true',
        'THINKINGSDK_LOG_LEVEL': 'INFO'
    })
    def test_environment_variable_overrides(self):
        """Test configuration overrides from environment variables."""
        config = Config()
        
        # Test float conversion
        instr_config = config.get_instrumentation_config()
        self.assertEqual(instr_config['sample_rate'], 0.3)
        
        # Test int conversion
        sender_config = config.get_sender_config()
        self.assertEqual(sender_config['batch_size'], 25)
        
        queue_config = config.get_queue_config()
        self.assertEqual(queue_config['maxsize'], 5000)
        
        # Test boolean conversion
        self.assertTrue(config.is_logging_enabled())
        
        # Test string value
        self.assertEqual(config.get_log_level(), 'INFO')

    @patch.dict(os.environ, {
        'THINKINGSDK_SAMPLE_RATE': 'invalid_float',
        'THINKINGSDK_BATCH_SIZE': 'not_a_number'
    })
    def test_invalid_environment_variables_ignored(self):
        """Test that invalid environment variables are ignored."""
        config = Config()
        
        # Should use defaults when env vars are invalid
        instr_config = config.get_instrumentation_config()
        self.assertEqual(instr_config['sample_rate'], 1.0)  # Default
        
        sender_config = config.get_sender_config()
        self.assertEqual(sender_config['batch_size'], 50)  # Default

    def test_environment_overrides_custom_config(self):
        """Test that environment variables override custom config."""
        custom_config = {
            'instrumentation': {
                'sample_rate': 0.9
            }
        }
        
        with patch.dict(os.environ, {'THINKINGSDK_SAMPLE_RATE': '0.1'}):
            config = Config(custom_config)
            
            instr_config = config.get_instrumentation_config()
            # Environment should win over custom config
            self.assertEqual(instr_config['sample_rate'], 0.1)

    def test_get_method(self):
        """Test the generic get method."""
        config = Config()
        
        # Test getting entire section
        queue_section = config.get('queue')
        self.assertIsInstance(queue_section, dict)
        self.assertIn('maxsize', queue_section)
        
        # Test getting specific key
        batch_size = config.get('sender', 'batch_size')
        self.assertEqual(batch_size, 50)
        
        # Test getting non-existent section
        missing_section = config.get('nonexistent')
        self.assertEqual(missing_section, {})
        
        # Test getting non-existent key
        missing_key = config.get('sender', 'nonexistent_key')
        self.assertIsNone(missing_key)

    def test_to_dict_method(self):
        """Test conversion to dictionary."""
        custom_config = {
            'instrumentation': {
                'sample_rate': 0.7
            }
        }
        
        config = Config(custom_config)
        config_dict = config.to_dict()
        
        # Should return complete configuration
        self.assertIn('queue', config_dict)
        self.assertIn('instrumentation', config_dict)
        self.assertIn('sender', config_dict)
        
        # Should include custom values
        self.assertEqual(config_dict['instrumentation']['sample_rate'], 0.7)
        
        # Should include defaults
        self.assertEqual(config_dict['queue']['maxsize'], 10000)

    def test_configuration_isolation(self):
        """Test that configuration objects don't interfere with each other."""
        config1 = Config({'instrumentation': {'sample_rate': 0.5}})
        config2 = Config({'instrumentation': {'sample_rate': 0.8}})
        
        # Each should have its own configuration
        self.assertEqual(config1.get_instrumentation_config()['sample_rate'], 0.5)
        self.assertEqual(config2.get_instrumentation_config()['sample_rate'], 0.8)

    def test_config_copy_independence(self):
        """Test that returned config dictionaries are independent copies."""
        config = Config()
        
        # Get queue config and modify it
        queue_config = config.get_queue_config()
        original_maxsize = queue_config['maxsize']
        queue_config['maxsize'] = 999999
        
        # Original config should be unchanged
        fresh_queue_config = config.get_queue_config()
        self.assertEqual(fresh_queue_config['maxsize'], original_maxsize)
        self.assertNotEqual(fresh_queue_config['maxsize'], 999999)

    def test_additional_ignore_patterns(self):
        """Test adding custom ignore patterns."""
        custom_config = {
            'instrumentation': {
                'ignore_patterns': [r'/custom/', r'/test/'],
                'ignore_functions': ['custom_func']
            }
        }
        
        config = Config(custom_config)
        instr_config = config.get_instrumentation_config()
        
        # Should include both default and custom patterns
        self.assertIn(r'/custom/', instr_config['ignore_patterns'])
        self.assertIn(r'/test/', instr_config['ignore_patterns'])
        self.assertIn('custom_func', instr_config['ignore_functions'])

    def test_boolean_environment_conversion(self):
        """Test various boolean environment variable formats."""
        test_cases = [
            ('true', True),
            ('True', True),
            ('TRUE', True),
            ('1', True),
            ('false', False),
            ('False', False),
            ('FALSE', False),
            ('0', False),
            ('', False),
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'THINKINGSDK_ENABLE_LOGGING': env_value}):
                config = Config()
                self.assertEqual(config.is_logging_enabled(), expected, 
                               f"Failed for env_value: {env_value}")


if __name__ == '__main__':
    unittest.main()