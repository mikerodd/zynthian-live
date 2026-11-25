# -*- coding: utf-8 -*-
"""Tests for the play-along endpoints and the play-along controls in the top bar."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT))

from tornado.template import Loader
from tornado.testing import AsyncHTTPTestCase

import live_session_server
import track_renderer

TRACK = {'name': 'Tenessee', 'play_along': 'tenessee.flac', 'json_path': None,
         'snapshot_path': None, 'zs3_id': None, 'notes': '', 'input_devices': []}
NO_PLAY_ALONG = dict(TRACK, play_along=None)


class PlayAlongApiTests(AsyncHTTPTestCase):
    def get_app(self):
        return live_session_server.make_app()

    def setUp(self):
        super().setUp()
        live_session_server.PLAY_ALONG['enabled'] = False
        live_session_server.BACKING['file'] = None
        self.sent = []
        patcher = mock.patch.object(live_session_server.spaph_client, 'command',
                                    side_effect=self.sent.append)
        self.command = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        live_session_server.PLAY_ALONG['enabled'] = False
        live_session_server.BACKING['file'] = None
        super().tearDown()

    def post_json(self, path, body):
        return self.fetch(path, method='POST', body=json.dumps(body))

    def test_mode_defaults_to_off_and_can_be_switched(self):
        self.assertEqual({'enabled': False}, json.loads(self.fetch('/api/play-along').body))
        self.post_json('/api/play-along', {'enabled': True})
        self.assertEqual({'enabled': True}, json.loads(self.fetch('/api/play-along').body))

    def test_mode_rejects_invalid_json(self):
        response = self.fetch('/api/play-along', method='POST', body='{not json')
        self.assertEqual(400, response.code)

    def test_first_play_loads_the_track_then_plays(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK):
            response = self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(200, response.code)
        self.assertEqual(['backing load tenessee.flac', 'backing play'], self.sent)

    def test_play_of_the_loaded_track_does_not_reload_it(self):
        live_session_server.BACKING['file'] = 'tenessee.flac'
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK):
            self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(['backing play'], self.sent)

    def test_play_of_another_track_loads_it(self):
        live_session_server.BACKING['file'] = 'other.flac'
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK):
            self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(['backing load tenessee.flac', 'backing play'], self.sent)

    def test_play_without_play_along_field_is_rejected(self):
        with mock.patch.object(live_session_server, 'get_track_paths',
                               return_value=NO_PLAY_ALONG):
            response = self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(400, response.code)
        self.assertEqual([], self.sent)

    def test_play_unknown_track_is_not_found(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=None):
            response = self.post_json('/api/play-along/play/9/9', {})
        self.assertEqual(404, response.code)
        self.assertEqual([], self.sent)

    def test_transport_actions_send_the_matching_spaph_command(self):
        cases = {
            'pause': 'backing pause',
            'stop': 'backing stop',
            'begin': 'backing begin',
            'back': 'backing seek -10',
            'forward': 'backing seek +10',
            'volume-down': 'backing volume -2',
            'volume-up': 'backing volume +2',
        }
        for action, command in cases.items():
            with self.subTest(action=action):
                self.sent.clear()
                response = self.post_json('/api/backing/' + action, {})
                self.assertEqual(200, response.code)
                self.assertEqual([command], self.sent)

    def test_unknown_transport_action_is_not_found(self):
        response = self.post_json('/api/backing/rewind', {})
        self.assertEqual(404, response.code)
        self.assertEqual([], self.sent)

    def test_unreachable_spaph_is_service_unavailable(self):
        self.command.side_effect = OSError('no route to host')
        response = self.post_json('/api/backing/pause', {})
        self.assertEqual(503, response.code)
        self.assertEqual('spaph unreachable', json.loads(response.body)['error'])

    def test_chart_page_gets_controls_only_when_mode_is_on(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK), \
             mock.patch.object(live_session_server, 'load_zs3'), \
             mock.patch.object(live_session_server, 'render_chart',
                               return_value='<div class="chart-nav"></div>') as render:
            self.fetch('/chart/0/1')
            self.assertEqual('', render.call_args.kwargs['controls_html'])

            self.post_json('/api/play-along', {'enabled': True})
            self.fetch('/chart/0/1')
            controls = render.call_args.kwargs['controls_html']
        self.assertIn('play-along-bar', controls)
        self.assertIn('data-track-idx="1"', controls)


class PlayAlongControlsTests(unittest.TestCase):
    def setUp(self):
        self.loader = Loader(str(ROOT / 'templates'))

    def test_buttons_are_enabled_when_track_has_play_along(self):
        html = track_renderer.build_play_along_html(0, 1, 'tenessee.flac')
        self.assertEqual(8, html.count('data-action='))
        self.assertNotIn('disabled', html)
        self.assertIn('class="pa-btn" data-action="play" title="Play"', html)
        self.assertNotIn('>Play<', html)

    def test_volume_buttons_are_in_the_bar(self):
        html = track_renderer.build_play_along_html(0, 1, 'tenessee.flac')
        self.assertIn('data-action="volume-down"', html)
        self.assertIn('data-action="volume-up"', html)

    def test_buttons_are_disabled_without_play_along_field(self):
        html = track_renderer.build_play_along_html(0, 1, None)
        self.assertEqual(8, html.count('disabled>'))
        self.assertIn('No play-along track for this song', html)

    def test_controls_are_placed_in_the_top_bar(self):
        controls = track_renderer.build_play_along_html(0, 1, 'tenessee.flac')
        html = track_renderer._build_page(
            title='Tenessee', notes='', gig_id=0, blocks=[],
            controls_html=controls)
        nav = html.split('<div class="chart-body')[0]
        self.assertIn('class="chart-nav with-controls"', nav)
        self.assertIn('play-along-bar', nav)

    def test_top_bar_is_unchanged_without_controls(self):
        html = track_renderer._build_page(
            title='Tenessee', notes='', gig_id=0, blocks=[])
        self.assertIn('<div class="chart-nav">', html)
        self.assertNotIn('play-along-bar', html)

    def test_chart_script_is_only_included_when_mode_is_on(self):
        def render(on):
            return self.loader.load('chart.html').generate(
                title='T', chart_body='', play_along_mode=on).decode('utf-8')
        self.assertIn("querySelector('.play-along-bar')", render(True))
        self.assertIn('/api/backing/', render(True))
        self.assertNotIn("querySelector('.play-along-bar')", render(False))

    def test_gig_page_toggle_reflects_mode(self):
        gigs = []
        on = self.loader.load('gig_list.html').generate(
            gigs=gigs, play_along_mode=True).decode('utf-8')
        off = self.loader.load('gig_list.html').generate(
            gigs=gigs, play_along_mode=False).decode('utf-8')
        self.assertIn('Play along: ON', on)
        self.assertIn('Play along: OFF', off)


if __name__ == '__main__':
    unittest.main()
