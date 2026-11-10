# -*- coding: utf-8 -*-
"""Tests for surfacing track status in gig_handler."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gig_handler  # noqa: E402
from fixtures import DataRootMixin  # noqa: E402


class GigTrackStatusTests(DataRootMixin, unittest.TestCase):
    def test_get_track_paths_includes_status(self):
        root = self.make_data_root(
            tracks={'one.json': {'display': []}},
            gigs=[{
                'name': 'Gig',
                'description': 'd',
                'snapshot_path': 'snapshots/004-Gigs/004-set3.zss',
                'tracks': [{
                    'name': 'Track',
                    'json_filename': 'tracks/one.json',
                    'zs3_id': 'zs3-15',
                    'notes': 'n',
                    'status': 'OK Mike',
                }],
            }])
        original = gig_handler.CONFIG_PATH
        gig_handler.CONFIG_PATH = str(self.config_path(root))
        self.addCleanup(setattr, gig_handler, 'CONFIG_PATH', original)

        paths = gig_handler.get_track_paths('0', '0')
        self.assertEqual('OK Mike', paths['status'])

    def test_get_track_paths_status_defaults_to_none(self):
        root = self.make_data_root(
            tracks={'one.json': {'display': []}})
        original = gig_handler.CONFIG_PATH
        gig_handler.CONFIG_PATH = str(self.config_path(root))
        self.addCleanup(setattr, gig_handler, 'CONFIG_PATH', original)

        paths = gig_handler.get_track_paths('0', '0')
        self.assertIsNone(paths['status'])


if __name__ == '__main__':
    unittest.main()
