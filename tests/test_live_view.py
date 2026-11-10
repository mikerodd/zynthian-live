# -*- coding: utf-8 -*-
"""Tests for track status colors on the gig page."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT))

from tornado.template import Loader


class LiveViewStatusTests(unittest.TestCase):
    def setUp(self):
        self.loader = Loader(str(ROOT / 'templates'))

    def render(self, tracks):
        gig = {'name': 'Test Gig', 'tracks': tracks}
        return self.loader.load('live_view.html').generate(
            gig=gig, gig_id='0').decode('utf-8')

    def test_status_colors_on_track_number(self):
        tracks = [
            {'name': 'Unknown', 'json_filename': 'tracks/a.json'},
            {'name': 'Not started', 'json_filename': 'tracks/b.json',
             'status': 'Not started'},
            {'name': 'In progress', 'json_filename': 'tracks/c.json',
             'status': 'In progress'},
            {'name': 'OK Mike', 'json_filename': 'tracks/d.json',
             'status': 'OK Mike'},
            {'name': 'Rehearsed', 'json_filename': 'tracks/e.json',
             'status': 'Rehearsed'},
        ]
        html = self.render(tracks)
        self.assertIn(
            '<span class="track-number" style="background-color: grey;">1</span>',
            html)
        self.assertIn(
            '<span class="track-number" style="background-color: pink;">2</span>',
            html)
        self.assertIn(
            '<span class="track-number" style="background-color: orange;">3</span>',
            html)
        self.assertIn(
            '<span class="track-number" style="background-color: lightgreen;">4</span>',
            html)
        self.assertIn(
            '<span class="track-number" style="background-color: green;">5</span>',
            html)

    def test_track_button_has_no_status_background(self):
        tracks = [{'name': 'A', 'json_filename': 'tracks/a.json',
                   'status': 'Rehearsed'}]
        html = self.render(tracks)
        self.assertIn('class="track-btn ', html)
        self.assertNotIn('style="background-color: green;"', html.split('track-number')[0])


if __name__ == '__main__':
    unittest.main()
