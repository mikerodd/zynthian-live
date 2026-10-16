# -*- coding: utf-8 -*-
"""Tests for config includes (lib/config_loader.py).

An include splices another config's gigs into the including one.  Three
properties are deliberately chosen and pinned here:

* ``includes`` sits beside ``gigs``, so the gig list stays a plain list of
  gigs and included gigs land after the including file's own, in order.
* Only one level is followed, so a cycle cannot loop.
* A broken *include* raises, because quietly dropping gigs would leave a
  performer with a set list that lost songs.  A missing root config is
  still just an empty config.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gig_handler  # noqa: E402
from config_loader import load_config  # noqa: E402
from fixtures import DataRootMixin, import_gigs_to_pdf  # noqa: E402


def names(config):
    return [gig.get('name') for gig in config['gigs']]


class LoadConfigTest(DataRootMixin, unittest.TestCase):

    def test_config_without_includes_is_unchanged(self):
        root = self.make_data_root(gigs=[self.default_gig([], name='Solo')])
        config = load_config(str(self.config_path(root)))
        self.assertEqual(names(config), ['Solo'])

    def test_included_gigs_follow_the_including_files_own(self):
        root = self.make_data_root(
            gigs=[self.default_gig([], name='Mine')],
            includes={
                'config-first.json': [self.default_gig([], name='First')],
                'config-second.json': [self.default_gig([], name='Second')],
            })
        config = load_config(str(self.config_path(root)))
        self.assertEqual(names(config), ['Mine', 'First', 'Second'])

    def test_include_order_follows_the_includes_list(self):
        root = self.make_data_root(
            gigs=[self.default_gig([], name='Mine')],
            includes={
                'config-a.json': [self.default_gig([], name='A')],
                'config-b.json': [self.default_gig([], name='B')],
            })
        # Reverse the list; the spliced order must follow it, not the
        # directory listing.
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-b.json', 'config-a.json']
        path.write_text(json.dumps(config))
        self.assertEqual(
            names(load_config(str(path))), ['Mine', 'B', 'A'])

    def test_included_gig_keeps_its_own_tracks(self):
        root = self.make_data_root(
            tracks={'one.json': {'display': []},
                    'two.json': {'display': []}},
            gigs=[self.default_gig(['one.json'], name='Mine')],
            includes={'config-other.json': [
                self.default_gig(['two.json'], name='Other')]})
        config = load_config(str(self.config_path(root)))
        tracks = [[t['json_filename'] for t in g['tracks']]
                  for g in config['gigs']]
        self.assertEqual(
            tracks, [['tracks/one.json'], ['tracks/two.json']])

    def test_missing_root_config_is_empty(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        missing = root / 'live-session' / 'nope.json'
        self.assertEqual(load_config(str(missing)), {'gigs': []})

    def test_missing_include_raises(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-absent.json']
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError) as caught:
            load_config(str(path))
        self.assertIn('config-absent.json', str(caught.exception))

    def test_missing_include_without_extension_suggests_the_json(self):
        """A forgotten '.json' is named back in the error, not just a path."""
        root = self.make_data_root(gigs=[self.default_gig([])])
        (root / 'live-session' / 'config-orphans.json').write_text(
            json.dumps({'gigs': []}))
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-orphans']
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError) as caught:
            load_config(str(path))
        message = str(caught.exception)
        self.assertIn('config-orphans', message)
        self.assertIn("did you mean 'config-orphans.json'", message)

    def test_malformed_include_raises(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        (root / 'live-session' / 'config-broken.json').write_text('{ nope')
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-broken.json']
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError) as caught:
            load_config(str(path))
        self.assertIn('config-broken.json', str(caught.exception))

    def test_include_that_is_not_an_object_raises(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        (root / 'live-session' / 'config-list.json').write_text('[]')
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-list.json']
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            load_config(str(path))

    def test_nested_include_is_ignored_but_its_gigs_are_used(self):
        """One level only: the inner 'includes' is reported, not followed."""
        root = self.make_data_root(gigs=[self.default_gig([], name='Mine')])
        (root / 'live-session' / 'config-mid.json').write_text(json.dumps({
            'includes': ['config-leaf.json'],
            'gigs': [self.default_gig([], name='Mid')],
        }))
        (root / 'live-session' / 'config-leaf.json').write_text(json.dumps({
            'gigs': [self.default_gig([], name='Leaf')],
        }))
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-mid.json']
        path.write_text(json.dumps(config))
        with self.assertLogs('config_loader', level='WARNING') as logs:
            loaded = load_config(str(path))
        self.assertEqual(names(loaded), ['Mine', 'Mid'])
        self.assertIn('only one level', '\n'.join(logs.output))

    def test_self_include_terminates(self):
        """A config naming itself must not loop."""
        root = self.make_data_root(gigs=[self.default_gig([], name='Mine')])
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config.json']
        path.write_text(json.dumps(config))
        with self.assertLogs('config_loader', level='WARNING'):
            loaded = load_config(str(path))
        self.assertEqual(names(loaded), ['Mine', 'Mine'])

    def test_include_outside_the_config_directory_is_refused(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['../config.json']
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError) as caught:
            load_config(str(path))
        self.assertIn('outside', str(caught.exception))

    def test_absolute_include_is_refused(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['/etc/passwd']
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError) as caught:
            load_config(str(path))
        self.assertIn('not a path or URL', str(caught.exception))

    def test_non_string_include_is_refused(self):
        root = self.make_data_root(gigs=[self.default_gig([])])
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = [7]
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError) as caught:
            load_config(str(path))
        self.assertIn('must be a file name', str(caught.exception))

    def test_include_without_gigs_contributes_nothing(self):
        root = self.make_data_root(gigs=[self.default_gig([], name='Mine')])
        (root / 'live-session' / 'config-empty.json').write_text('{}')
        path = self.config_path(root)
        config = json.loads(path.read_text())
        config['includes'] = ['config-empty.json']
        path.write_text(json.dumps(config))
        self.assertEqual(names(load_config(str(path))), ['Mine'])


class GigHandlerTest(DataRootMixin, unittest.TestCase):
    """gig_handler must serve the merged list, with stable positional ids."""

    def test_list_gigs_sees_included_gigs(self):
        root = self.make_data_root(
            gigs=[self.default_gig([], name='Mine')],
            includes={'config-other.json': [
                self.default_gig([], name='Other')]})
        original = gig_handler.CONFIG_PATH
        gig_handler.CONFIG_PATH = str(self.config_path(root))
        self.addCleanup(setattr, gig_handler, 'CONFIG_PATH', original)

        listed = gig_handler.list_gigs()
        self.assertEqual([g['name'] for g in listed], ['Mine', 'Other'])
        self.assertEqual([g['id'] for g in listed], ['0', '1'])

        # The id a template renders must select the same gig.
        self.assertEqual(
            gig_handler.load_gig(listed[1]['id'])['name'], 'Other')


class GigsToPdfTest(DataRootMixin, unittest.TestCase):
    """The PDF builder must splice includes the same way the server does."""

    def test_build_html_renders_included_gigs(self):
        module = import_gigs_to_pdf()
        if module is None:
            self.skipTest('scripts/gigs_to_pdf.py is not present')

        root = self.make_data_root(
            tracks={'one.json': {'display': ['structure'],
                                 'structure': {'headers': ['A'],
                                               'rows': [{'cells': [1]}]}},
                    'two.json': {'display': ['structure'],
                                 'structure': {'headers': ['B'],
                                               'rows': [{'cells': [2]}]}}},
            gigs=[self.default_gig(['one.json'], name='Mine')],
            includes={'config-other.json': [
                self.default_gig(['two.json'], name='Other')]})

        html, titles, cover_title = module.build_html(
            str(self.config_path(root)), alpha=True)
        self.assertEqual(titles, ['one.json', 'two.json'])
        self.assertIn('Mine', html)
        self.assertIn('Other', html)

    def test_gigs_all_dedupes_tracks_by_name_first_gig_wins(self):
        module = import_gigs_to_pdf()
        if module is None:
            self.skipTest('scripts/gigs_to_pdf.py is not present')

        def track(name, filename):
            return {'name': name, 'json_filename': 'tracks/' + filename,
                    'notes': name + ' notes'}

        def structure(letter):
            return {'display': ['structure'],
                    'structure': {'headers': [letter],
                                  'rows': [{'cells': [1]}]}}

        root = self.make_data_root(
            tracks={'one.json': structure('A'),
                    'two.json': structure('B'),
                    'three.json': structure('C')},
            # config.json's own gig declares "Song" first, so its file wins
            # over the same-named track contributed by the include.
            gigs=[{'name': 'Mine', 'description': 'Fixture gig',
                   'tracks': [track('Song', 'one.json')]}],
            includes={'config-other.json': [
                {'name': 'Other', 'description': 'Fixture gig',
                 'tracks': [track('Song', 'two.json'),
                            track('Another', 'three.json')]}]})

        html, titles, cover = module.build_html(
            str(self.config_path(root)), alpha=True, all_tracks=True)
        self.assertEqual(titles, ['Another', 'Song'])
        self.assertEqual('All tracks', cover)
        self.assertNotIn('class="sheet" id="track-2"', html)



if __name__ == '__main__':
    unittest.main()
