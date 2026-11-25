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
from mpd_client import MpdError

TRACK = {'name': 'Tenessee', 'play_along': 'tenessee.flac', 'json_path': None,
         'snapshot_path': None, 'zs3_id': None, 'notes': '', 'input_devices': []}
NO_PLAY_ALONG = dict(TRACK, play_along=None)


class PlayAlongApiTests(AsyncHTTPTestCase):
    def get_app(self):
        return live_session_server.make_app()

    def setUp(self):
        super().setUp()
        live_session_server.PLAY_ALONG['enabled'] = False

    def tearDown(self):
        live_session_server.PLAY_ALONG['enabled'] = False
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

    def test_play_starts_the_track_when_stopped(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK), \
             mock.patch.object(live_session_server.mpd_client, 'state_and_file',
                               return_value=('stop', None)), \
             mock.patch.object(live_session_server.mpd_client, 'play_track') as play:
            response = self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(200, response.code)
        play.assert_called_once_with('tenessee.flac')

    def test_play_resumes_when_this_track_is_paused(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK), \
             mock.patch.object(live_session_server.mpd_client, 'state_and_file',
                               return_value=('pause', 'tenessee.flac')), \
             mock.patch.object(live_session_server.mpd_client, 'resume') as resume, \
             mock.patch.object(live_session_server.mpd_client, 'play_track') as play:
            self.post_json('/api/play-along/play/0/1', {})
        resume.assert_called_once_with()
        play.assert_not_called()

    def test_play_leaves_a_track_that_is_already_playing(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=TRACK), \
             mock.patch.object(live_session_server.mpd_client, 'state_and_file',
                               return_value=('play', 'tenessee.flac')), \
             mock.patch.object(live_session_server.mpd_client, 'play_track') as play:
            response = self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(200, response.code)
        play.assert_not_called()

    def test_play_without_play_along_field_is_rejected(self):
        with mock.patch.object(live_session_server, 'get_track_paths',
                               return_value=NO_PLAY_ALONG), \
             mock.patch.object(live_session_server.mpd_client, 'play_track') as play:
            response = self.post_json('/api/play-along/play/0/1', {})
        self.assertEqual(400, response.code)
        play.assert_not_called()

    def test_play_unknown_track_is_not_found(self):
        with mock.patch.object(live_session_server, 'get_track_paths', return_value=None):
            response = self.post_json('/api/play-along/play/9/9', {})
        self.assertEqual(404, response.code)

    def test_transport_actions_call_the_matching_command(self):
        for action in ('pause', 'stop', 'begin'):
            with self.subTest(action=action), \
                 mock.patch.object(live_session_server.mpd_client, action) as call:
                response = self.post_json('/api/mpd/' + action, {})
                self.assertEqual(200, response.code)
                call.assert_called_once_with()

    def test_back_and_forward_seek_by_the_step(self):
        with mock.patch.object(live_session_server.mpd_client, 'seek') as seek:
            self.post_json('/api/mpd/back', {})
            self.post_json('/api/mpd/forward', {})
        self.assertEqual([mock.call(-10), mock.call(10)], seek.call_args_list)

    def test_unknown_transport_action_is_not_found(self):
        response = self.post_json('/api/mpd/rewind', {})
        self.assertEqual(404, response.code)

    def test_mpd_ack_is_a_conflict(self):
        with mock.patch.object(live_session_server.mpd_client, 'pause',
                               side_effect=MpdError('ACK [50@0] Not playing')):
            response = self.post_json('/api/mpd/pause', {})
        self.assertEqual(409, response.code)
        self.assertIn('Not playing', json.loads(response.body)['error'])

    def test_unreachable_mpd_is_service_unavailable(self):
        with mock.patch.object(live_session_server.mpd_client, 'pause',
                               side_effect=OSError('refused')):
            response = self.post_json('/api/mpd/pause', {})
        self.assertEqual(503, response.code)
        self.assertEqual('MPD unreachable', json.loads(response.body)['error'])

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
        self.assertEqual(6, html.count('data-action='))
        self.assertNotIn('disabled', html)
        self.assertIn('class="pa-btn" data-action="play">', html)

    def test_buttons_are_disabled_without_play_along_field(self):
        html = track_renderer.build_play_along_html(0, 1, None)
        self.assertEqual(6, html.count('disabled>'))
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
