# -*- coding: utf-8 -*-
"""Tests for track inheritance (lib/track_loader.py).

Inheritance is deliberately shallow and deliberately forgiving: a child
replaces its parent's top-level keys, one level is followed, and anything
wrong with the *parent* only produces a warning.  These tests pin all three.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import track_renderer  # noqa: E402
from track_loader import load_track  # noqa: E402
from fixtures import DataRootMixin, import_gigs_to_pdf  # noqa: E402

PARENT = {
    'display': ['leadsheet', 'structure'],
    'leadsheet': [{'label': 'Intro', 'chords': '| Am G |', 'beat': '4/4'}],
    'structure': {
        'headers': ['Intro', 'Chorus'],
        'rows': [{'cells': [1, 0]}],
    },
}

CHILD = {
    'inherit': 'parent.json',
    'display': ['leadsheet'],
}


class TrackDirMixin:
    """Writes track files into a temporary directory."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.dir = Path(temp_dir.name)

    def write(self, name, content):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding='utf-8')
        else:
            path.write_text(json.dumps(content), encoding='utf-8')
        return str(path)


class LoadTrackTests(TrackDirMixin, unittest.TestCase):

    def test_track_without_inherit_is_returned_unchanged(self):
        path = self.write('solo.json', PARENT)
        self.assertEqual(PARENT, load_track(path))

    def test_child_overrides_keys_and_inherits_the_rest(self):
        parent = self.write('parent.json', PARENT)
        child = self.write('child.json', CHILD)
        merged = load_track(child)

        self.assertEqual(['leadsheet'], merged['display'])
        self.assertEqual(PARENT['leadsheet'], merged['leadsheet'])
        self.assertEqual(PARENT['structure'], merged['structure'])

    def test_merge_is_shallow_so_a_child_key_replaces_the_whole_value(self):
        parent = self.write('parent.json', PARENT)
        child = self.write('child.json', {
            'inherit': 'parent.json',
            'structure': {'rows': [{'cells': ['riff1']}]},
        })
        merged = load_track(child)

        self.assertEqual({'rows': [{'cells': ['riff1']}]}, merged['structure'])
        self.assertNotIn('headers', merged['structure'])

    def test_inherit_key_is_not_part_of_the_merged_track(self):
        self.write('parent.json', PARENT)
        child = self.write('child.json', CHILD)
        self.assertNotIn('inherit', load_track(child))

    def test_only_one_level_is_followed(self):
        grandparent = self.write('grandparent.json', {
            'leadsheet': [{'label': 'Grandparent', 'chords': '| C |'}],
            'time': '3/4',
        })
        parent = self.write('parent.json', {
            'inherit': 'grandparent.json',
            'leadsheet': [{'label': 'Parent', 'chords': '| G |'}],
        })
        child = self.write('child.json', {'inherit': 'parent.json'})

        with self.assertLogs('track_loader', level='WARNING') as logs:
            merged = load_track(child)

        # the parent's own leadsheet wins, and its parent's keys stop there
        self.assertEqual([{'label': 'Parent', 'chords': '| G |'}],
                         merged['leadsheet'])
        self.assertNotIn('time', merged)
        self.assertNotIn('inherit', merged)
        self.assertTrue(any('only one level' in line for line in logs.output))
        self.assertTrue(os.path.isfile(grandparent))

    def test_missing_parent_warns_and_keeps_the_child(self):
        child = self.write('child.json', CHILD)
        with self.assertLogs('track_loader', level='WARNING'):
            merged = load_track(child)
        self.assertEqual(['leadsheet'], merged['display'])

    def test_invalid_json_parent_warns_and_keeps_the_child(self):
        self.write('parent.json', '{"display": [')
        child = self.write('child.json', CHILD)
        with self.assertLogs('track_loader', level='WARNING'):
            merged = load_track(child)
        self.assertEqual(['leadsheet'], merged['display'])

    def test_non_object_parent_warns_and_keeps_the_child(self):
        self.write('parent.json', '[1, 2, 3]')
        child = self.write('child.json', CHILD)
        with self.assertLogs('track_loader', level='WARNING'):
            merged = load_track(child)
        self.assertEqual(['leadsheet'], merged['display'])

    def test_parent_in_a_subdirectory_is_allowed(self):
        self.write('shared/parent.json', PARENT)
        child = self.write('child.json', {
            'inherit': 'shared/parent.json',
            'display': ['structure'],
        })
        merged = load_track(child)
        self.assertEqual(['structure'], merged['display'])
        self.assertEqual(PARENT['leadsheet'], merged['leadsheet'])

    def test_parent_reached_through_dotdot_is_refused(self):
        self.write('shared/parent.json', PARENT)
        child = self.write('nested/child.json', {
            'inherit': '../shared/parent.json',
        })
        with self.assertLogs('track_loader', level='WARNING'):
            merged = load_track(child)
        self.assertEqual({'inherit': '../shared/parent.json'}, merged)

    def test_paths_outside_the_track_directory_are_refused(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / 'secret.json').write_text('{"leadsheet": "secret"}',
                                             encoding='utf-8')
        self.write('parent.json', PARENT)

        for inherit in ('../{}'.format(outside.name),
                        str(outside / 'secret.json'),
                        'file:///etc/passwd',
                        'http://example.com/x.json'):
            with self.subTest(inherit=inherit):
                child = self.write('child.json', {'inherit': inherit})
                with self.assertLogs('track_loader', level='WARNING'):
                    merged = load_track(child)
                self.assertEqual({'inherit': inherit}, merged)

    def test_non_string_inherit_is_refused(self):
        child = self.write('child.json', {'inherit': ['parent.json']})
        with self.assertLogs('track_loader', level='WARNING'):
            self.assertEqual({'inherit': ['parent.json']}, load_track(child))

    def test_child_load_failure_still_raises(self):
        with self.assertRaises(ValueError):
            load_track(self.write('broken.json', '{"display": ['))

    def test_missing_child_still_raises(self):
        with self.assertRaises(OSError):
            load_track(str(self.dir / 'nope.json'))


class InheritedRenderTests(DataRootMixin, TrackDirMixin, unittest.TestCase):
    """Both pipelines must see the merged track."""

    def setUp(self):
        TrackDirMixin.setUp(self)
        self.pdf = import_gigs_to_pdf()
        if self.pdf is None:
            self.skipTest('scripts/gigs_to_pdf.py not found')

    def test_server_renders_the_inherited_leadsheet(self):
        self.write('parent.json', PARENT)
        child = self.write('child.json', CHILD)

        html = track_renderer.render_chart(0, child, title='Child')

        self.assertIn('Intro', html)
        self.assertIn('<div class="ls-beat">G</div>', html)
        # display came from the child, so the parent's structure is dropped
        self.assertNotIn('track-table', html)

    def test_pdf_renders_the_inherited_leadsheet(self):
        tracks = {'parent.json': PARENT, 'child.json': CHILD}
        root = self.make_data_root(tracks=tracks, input_devices=[])
        doc, _titles, _cover = self.pdf.build_html(str(self.config_path(root)))
        sheet = doc[doc.find('child.json'):]

        self.assertIn('Intro', sheet)
        self.assertIn('<div class="ls-beat">G</div>', sheet)
        self.assertNotIn('track-table', sheet)


if __name__ == '__main__':
    unittest.main()
