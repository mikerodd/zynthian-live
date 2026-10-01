# -*- coding: utf-8 -*-
"""Characterization (golden) tests for both render pipelines.

These pin the exact HTML produced by the two consumers of lib/:

  * the tornado server   -- track_renderer.render_chart()
  * the PDF exporter     -- gigs_to_pdf.build_html()

Purpose: the display-block loop was duplicated between them and had already
drifted.  A refactor that mutualises the code must not change a single byte
of either output, and these hashes are what prove that.  They are recorded
from the *unrefactored* code.

Regenerate after an intentional change::

    UPDATE_GOLDEN=1 python3 tests/test_display_blocks.py

then review the diff to tests/golden.json.  A hash hides the actual
difference, so when a case fails, dump the HTML and diff it by hand.

Cases whose output depends on the external .zss snapshot are deliberately
NOT hashed (that file is regenerated as snapshots evolve); those are
asserted structurally in SplitBlockTests instead.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import track_renderer  # noqa: E402
from keyboard_svg import split_svg  # noqa: E402
from zss_parser import collect_skins  # noqa: E402
from fixtures import (  # noqa: E402
    DataRootMixin, INPUT_DEVICES, ZSS_FIXTURE, ZSS3_ID, have_zss,
    import_gigs_to_pdf,
)

GOLDEN_PATH = Path(__file__).resolve().parent / 'golden.json'
UPDATE_GOLDEN = bool(os.environ.get('UPDATE_GOLDEN'))

# ── fixture track data ───────────────────────────────────────────────────

LEADSHEET = [
    {'label': 'Intro', 'chords': '| A9sus4 G9sus4 |', 'beat': '4/4'},
    {'label': 'Chorus', 'chords': '|< F#-7 | D7 | >|', 'voltas': '1.2'},
]

STRUCTURE = {
    'headers': ['Intro', 'Verse', 'Chorus'],
    'rows': [
        {'cells': [1, 0, 1]},
        {'cells': [0, 1, 0]},
    ],
}

HTML_BLOCK = {'text': 'Start on the <b>8th</b> kick'}

IMAGES = [{'caption': 'riff1', 'source': 'imgs/riff1.svg'}]


def full_track(display):
    return {
        'display': display,
        'leadsheet': LEADSHEET,
        'structure': STRUCTURE,
        'html': HTML_BLOCK,
        'images': IMAGES,
    }


#: Tracks whose output is fully determined by self-contained fixture files,
#: i.e. no .zss involved, so their hashes are stable across machines.
CASES = {
    'web_all_blocks': full_track(['leadsheet', 'structure', 'html', 'images']),
    'web_reordered': full_track(['images', 'html', 'structure', 'leadsheet']),
    'web_no_display_key': {
        key: value for key, value in full_track(
            ['leadsheet', 'structure', 'html', 'images']).items()
        if key != 'display'},
    'web_empty_display': full_track([]),
    'web_unknown_block': full_track(['nope', 'structure', 'bogus']),
    'web_images_not_selected': full_track(['structure', 'images']),
    'web_no_html_block': {
        'display': ['leadsheet', 'structure'],
        'leadsheet': LEADSHEET,
        'structure': STRUCTURE,
    },
    'web_structure_rows_without_headers': {
        'display': ['structure'],
        'structure': {'rows': [{'cells': [1]}]},
    },
    'web_structure_text_cells': {
        'display': ['structure'],
        'structure': {
            'headers': ['Intro', 'Chorus'],
            'rows': [{'cells': ['riff1', 0]}, {'cells': [0, 'riff2']}],
        },
    },
    'web_empty_track': {},
}


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class GoldenTestCase(DataRootMixin, unittest.TestCase):
    """Shared golden-hash bookkeeping."""

    @classmethod
    def setUpClass(cls):
        cls.golden = json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))

    def setUp(self):
        self.updated = {}
        self.addCleanup(self._flush)

    def _flush(self):
        if not self.updated:
            return
        self.golden.update(self.updated)
        GOLDEN_PATH.write_text(
            json.dumps(self.golden, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')

    def assertGolden(self, name, html):
        expected = self.golden.get(name)
        if UPDATE_GOLDEN or expected is None:
            self.updated[name] = digest(html)
            return
        self.assertEqual(
            expected, digest(html),
            '{} output changed (expected sha256 {}). If this is '
            'intentional, rerun with UPDATE_GOLDEN=1.'.format(name, expected))


class WebPipelineGoldenTests(GoldenTestCase):
    """track_renderer.render_chart() output."""

    def render(self, root, track, **kwargs):
        path = self.track_path(root, 'track.json')
        path.write_text(json.dumps(track), encoding='utf-8')
        kwargs.setdefault('title', 'Track')
        return track_renderer.render_chart(0, str(path), **kwargs)

    def test_golden_cases(self):
        for name, track in CASES.items():
            with self.subTest(case=name):
                root = self.make_data_root()
                self.write_image(root)
                self.assertGolden(name, self.render(root, track))

    def test_transposition_is_pinned(self):
        track = full_track(['leadsheet'])
        for semitones in (-3, 5):
            with self.subTest(semitones=semitones):
                root = self.make_data_root()
                html = self.render(root, track, semitones=semitones)
                self.assertGolden('web_transpose_{}'.format(semitones), html)

    def test_absent_leadsheet_block_is_skipped(self):
        root = self.make_data_root()
        html = self.render(root, {'display': ['leadsheet', 'structure'],
                                  'structure': STRUCTURE})
        self.assertNotIn('ls-line', html)
        self.assertIn('track-table', html)


class PdfPipelineGoldenTests(GoldenTestCase):
    """gigs_to_pdf.build_html() output for the same fixtures."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdf = import_gigs_to_pdf()

    def setUp(self):
        super().setUp()
        if self.pdf is None:
            self.skipTest('scripts/gigs_to_pdf.py not found')

    def build(self, tracks, gigs=None, input_devices=None):
        root = self.make_data_root(tracks=tracks, gigs=gigs,
                                   input_devices=input_devices)
        self.write_image(root)
        doc, titles, _ = self.pdf.build_html(str(self.config_path(root)))
        return doc, titles

    def test_golden_cases(self):
        for name, track in CASES.items():
            with self.subTest(case=name):
                doc, _ = self.build({'track.json': track})
                self.assertGolden('pdf_' + name[4:], doc)

    def test_missing_track_file_section(self):
        doc, _ = self.build({}, gigs=[self.default_gig(['gone.json'])])
        self.assertIn('MISSING track file', doc)
        self.assertGolden('pdf_missing_track_file', doc)

    def test_invalid_json_track_file_section(self):
        doc, _ = self.build({'broken.json': '{"display": ['})
        self.assertIn('ERROR: invalid JSON track file', doc)
        self.assertGolden('pdf_invalid_json_track_file', doc)

    def test_gig_without_tracks(self):
        doc, _ = self.build({}, gigs=[])
        self.assertGolden('pdf_no_gigs', doc)

    def test_split_block_without_input_devices(self):
        doc, _ = self.build({'track.json': full_track(['split', 'structure'])},
                            input_devices=[])
        self.assertNotIn('<div class="split-container">', doc)
        self.assertGolden('pdf_split_no_devices', doc)

    def test_alpha_index_orders_and_anchors(self):
        tracks = {'b.json': full_track(['structure']),
                  'a.json': full_track(['structure'])}
        root = self.make_data_root(tracks=tracks)
        doc, titles, cover = self.pdf.build_html(
            str(self.config_path(root)), alpha=True)
        self.assertEqual(['a.json', 'b.json'], titles)
        self.assertEqual('Test Gig', cover)
        self.assertGolden('pdf_alpha_index', doc)


@unittest.skipUnless(have_zss(), 'snapshot fixture unavailable')
class SplitBlockTests(unittest.TestCase):
    """Split output depends on the external .zss, so assert structure."""

    def setUp(self):
        self.pdf = import_gigs_to_pdf()
        if self.pdf is None:
            self.skipTest('scripts/gigs_to_pdf.py not found')

    def skins(self):
        return collect_skins({}, str(ZSS_FIXTURE), ZSS3_ID, INPUT_DEVICES)

    def test_collect_skins_yields_one_skin_per_channel(self):
        skins = self.skins()
        self.assertEqual(2, len(skins))
        self.assertEqual(3, len(skins[0]['banks']))
        self.assertEqual(1, len(skins[1]['banks']))

    def test_split_svg_is_a_multi_keyboard_group_per_device(self):
        svg = split_svg(self.skins())
        self.assertIn('<svg', svg)
        self.assertEqual(2, svg.count('<g transform='))

    def test_single_device_uses_plain_keyboard(self):
        svg = split_svg(self.skins()[:1])
        self.assertNotIn('<g transform=', svg)
        self.assertIn('<svg', svg)

    def test_missing_snapshot_yields_no_skins(self):
        self.assertEqual(
            [], collect_skins({}, '/nonexistent.zss', ZSS3_ID,
                              INPUT_DEVICES))

    def test_collect_skins_requires_all_arguments(self):
        path = str(ZSS_FIXTURE)
        self.assertEqual(
            [], collect_skins({}, path, None, INPUT_DEVICES))
        self.assertEqual([], collect_skins({}, path, ZSS3_ID, []))

    def test_track_renderer_renders_split_from_zss(self):
        html = track_renderer.render_chart(
            0, self._write_track(), zss_path=str(ZSS_FIXTURE),
            zs3_id=ZSS3_ID, input_devices=INPUT_DEVICES)
        self.assertIn('split-container', html)
        self.assertEqual(2, html.count('<g transform='))

    def _write_track(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / 'track.json'
        path.write_text(json.dumps({'display': ['split']}), encoding='utf-8')
        return str(path)


if __name__ == '__main__':
    unittest.main()