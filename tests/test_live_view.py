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

    def test_status_colors(self):
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
        self.assertIn('style="background-color: #e8e8e8;"', html)
        self.assertIn('style="background-color: pink;"', html)
        self.assertIn('style="background-color: orange;"', html)
        self.assertIn('style="background-color: lightgreen;"', html)
        self.assertIn('style="background-color: green;"', html)


if __name__ == '__main__':
    unittest.main()
