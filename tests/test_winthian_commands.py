# -*- coding: utf-8 -*-
"""Tests for sending winthian commands when a chart is displayed."""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT))

import gig_handler  # noqa: E402
from fixtures import DataRootMixin  # noqa: E402
from tornado.testing import AsyncHTTPTestCase

import live_session_server  # noqa: E402


class WinthianCommandsGigTests(DataRootMixin, unittest.TestCase):
    def test_get_track_paths_includes_winthian_commands(self):
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
                    'winthian_commands': ['load scripts/a.spaph', 'backing volume -3'],
                }],
            }])
        original = gig_handler.CONFIG_PATH
        gig_handler.CONFIG_PATH = str(self.config_path(root))
        self.addCleanup(setattr, gig_handler, 'CONFIG_PATH', original)

        paths = gig_handler.get_track_paths('0', '0')
        self.assertEqual(['load scripts/a.spaph', 'backing volume -3'],
                         paths['winthian_commands'])

    def test_winthian_commands_defaults_to_empty_list(self):
        root = self.make_data_root(
            tracks={'one.json': {'display': []}})
        original = gig_handler.CONFIG_PATH
        gig_handler.CONFIG_PATH = str(self.config_path(root))
        self.addCleanup(setattr, gig_handler, 'CONFIG_PATH', original)

        paths = gig_handler.get_track_paths('0', '0')
        self.assertEqual([], paths['winthian_commands'])


class WinthianCommandsChartTests(AsyncHTTPTestCase):
    def get_app(self):
        return live_session_server.make_app()

    def setUp(self):
        super().setUp()
        live_session_server.PLAY_ALONG['enabled'] = False
        self.sent = []
        patcher = mock.patch.object(live_session_server.spaph_client, 'command',
                                    side_effect=self.sent.append)
        self.command = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        live_session_server.PLAY_ALONG['enabled'] = False
        super().tearDown()

    def _paths_with_commands(self):
        return {
            'json_path': None,
            'snapshot_path': None,
            'zs3_id': None,
            'name': 'Soldier',
            'notes': '',
            'status': None,
            'play_along': None,
            'winthian_commands': ['load scripts/soldier.spaph', 'backing play'],
            'input_devices': [],
        }

    def test_commands_are_sent_in_order_when_present(self):
        with mock.patch.object(live_session_server, 'get_track_paths',
                               return_value=self._paths_with_commands()), \
             mock.patch.object(live_session_server, 'load_zs3'), \
             mock.patch.object(live_session_server, 'render_chart',
                               return_value='<div class="chart-nav"></div>'):
            response = self.fetch('/chart/0/0')
        self.assertEqual(200, response.code)
        self.assertEqual(['load scripts/soldier.spaph', 'backing play'], self.sent)

    def test_unload_all_is_sent_when_field_is_absent(self):
        paths = self._paths_with_commands()
        paths['winthian_commands'] = []
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=paths), \
             mock.patch.object(live_session_server, 'load_zs3'), \
             mock.patch.object(live_session_server, 'render_chart',
                               return_value='<div class="chart-nav"></div>'):
            self.fetch('/chart/0/0')
        self.assertEqual(['plugin unload all'], self.sent)

    def test_failing_command_does_not_prevent_render(self):
        self.command.side_effect = OSError('no route to host')
        with mock.patch.object(live_session_server, 'get_track_paths',
                               return_value=self._paths_with_commands()), \
             mock.patch.object(live_session_server, 'load_zs3'), \
             mock.patch.object(live_session_server, 'render_chart',
                               return_value='<div class="chart-nav"></div>') as render:
            response = self.fetch('/chart/0/0')
        self.assertEqual(200, response.code)
        render.assert_called_once()

    def test_commands_are_sent_even_when_play_along_is_off(self):
        with mock.patch.object(live_session_server, 'get_track_paths',
                               return_value=self._paths_with_commands()), \
             mock.patch.object(live_session_server, 'load_zs3'), \
             mock.patch.object(live_session_server, 'render_chart',
                               return_value='<div class="chart-nav"></div>'):
            live_session_server.PLAY_ALONG['enabled'] = False
            self.fetch('/chart/0/0')
        self.assertEqual(['load scripts/soldier.spaph', 'backing play'], self.sent)


if __name__ == '__main__':
    unittest.main()
