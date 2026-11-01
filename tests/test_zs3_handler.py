import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))

import zs3_handler


class OscClientTests(unittest.TestCase):
    def test_unavailable_client_reports_unavailable(self):
        original = zs3_handler.LIBLO_AVAILABLE
        zs3_handler.LIBLO_AVAILABLE = False
        try:
            client = zs3_handler.OSCClient()
            self.assertFalse(client.available)
            self.assertIsNone(client.addr)
            self.assertFalse(client.send_zs3('zs3-1'))
            self.assertFalse(client.send_snapshot(1, 2))
        finally:
            zs3_handler.LIBLO_AVAILABLE = original

    def test_init_osc_replaces_singleton(self):
        original = zs3_handler.LIBLO_AVAILABLE
        zs3_handler.LIBLO_AVAILABLE = False
        try:
            zs3_handler.init_osc('example.invalid', 1234)
            self.assertFalse(zs3_handler.osc_client.available)
            self.assertFalse(zs3_handler.load_zs3('zs3-1'))
            self.assertFalse(zs3_handler.load_snapshot(1, 2))
        finally:
            zs3_handler.LIBLO_AVAILABLE = original
            zs3_handler.init_osc()


if __name__ == '__main__':
    unittest.main()
