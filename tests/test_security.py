import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))

from security import safe_resolve_path


class SafeResolvePathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = self.temp_dir.name

    def test_resolves_simple_relative_path(self):
        target = os.path.join(self.base, 'a', 'b.txt')
        os.makedirs(os.path.dirname(target))
        Path(target).write_text('x', encoding='utf-8')
        self.assertEqual(target, safe_resolve_path(self.base, 'a/b.txt'))

    def test_rejects_null_byte(self):
        self.assertIsNone(safe_resolve_path(self.base, 'a\x00b.txt'))

    def test_rejects_absolute_path(self):
        self.assertIsNone(safe_resolve_path(self.base, '/etc/passwd'))

    def test_rejects_url(self):
        self.assertIsNone(safe_resolve_path(self.base, 'https://example.com/x'))

    def test_rejects_traversal(self):
        self.assertIsNone(safe_resolve_path(self.base, '../outside.txt'))
        self.assertIsNone(safe_resolve_path(self.base, 'a/../../outside.txt'))

    def test_allows_base_itself(self):
        self.assertEqual(os.path.abspath(self.base),
                         safe_resolve_path(self.base, ''))

    def test_rejects_non_string(self):
        self.assertIsNone(safe_resolve_path(self.base, None))  # type: ignore[arg-type]
