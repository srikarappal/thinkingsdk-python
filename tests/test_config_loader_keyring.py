"""Tests for optional keyring handling in ConfigLoader.get_api_key (issue #8).

keyring is now an optional import: config_loader.keyring is None when the package is absent, and the
`keyring:` api_key_source raises a helpful error instead of the module failing to import.
"""
import os
import types
import unittest
from unittest.mock import patch

from thinkingsdk import config_loader
from thinkingsdk.config_loader import ConfigLoader


class TestKeyringOptional(unittest.TestCase):
    def _loader(self, source):
        # Skip __init__ (which searches for thinkingsdk.yaml); get_api_key only reads self.config.
        loader = ConfigLoader.__new__(ConfigLoader)
        loader.config = {"api_key_source": source}
        return loader

    def test_keyring_source_without_keyring_raises_helpful_error(self):
        with patch.object(config_loader, "keyring", None):
            with self.assertRaises(ValueError) as ctx:
                self._loader("keyring:myservice").get_api_key()
            msg = str(ctx.exception)
            self.assertIn("keyring", msg.lower())
            self.assertIn("thinkingsdk[keyring]", msg)

    def test_keyring_source_reads_from_keyring_when_present(self):
        fake = types.SimpleNamespace(get_password=lambda service, key: "sk_from_keyring")
        with patch.object(config_loader, "keyring", fake):
            self.assertEqual(self._loader("keyring:myservice").get_api_key(), "sk_from_keyring")

    def test_env_source_works_without_keyring(self):
        # A non-keyring source must resolve even when keyring is absent (the module still imports).
        with patch.object(config_loader, "keyring", None):
            with patch.dict(os.environ, {"TSDK_TEST_KEY": "sk_env"}):
                self.assertEqual(self._loader("env:TSDK_TEST_KEY").get_api_key(), "sk_env")


if __name__ == "__main__":
    unittest.main()
