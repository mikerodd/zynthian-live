# -*- coding: utf-8 -*-
"""Shared fixtures for the zynthian-live test suite.

Builds a throwaway data root that *both* render pipelines can consume::

    <tmp>/                            data_root == $ZYNTHIAN_MY_DATA_DIR
      snapshots/004-Gigs/004-set3.zss
      live-session/
        config.json
        tracks/*.json
        tracks/imgs/*.svg

gigs_to_pdf.build_html() derives base_dir/data_root from the config path,
while gig_handler resolves snapshot_path against the data root, so this
single layout feeds both without any per-test path juggling.

Split rendering needs a real .zss snapshot.  004-set3.zss is the current
one (used by three of the five gigs in the shipped config) and is symlinked
into the gitignored ``test/`` tree, following the existing fixture pattern.
Tests that need it skip themselves when it is absent.
"""

import json
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
LIVE_DIR = TESTS_DIR.parent
REPO_ROOT = LIVE_DIR.parent

ZSS_FIXTURE = LIVE_DIR / 'test' / 'snapshots' / '004-Gigs' / '004-set3.zss'

#: Path as written in config.json's ``snapshot_path`` (data-root relative).
SNAPSHOT_REL = 'snapshots/004-Gigs/004-set3.zss'

#: A ZS3 entry that yields zones on both channels, so the multi-device
#: keyboard renderer is exercised.
ZSS3_ID = 'zs3-15'

#: Same shape as the shipped config.json: 61 keys on channel 0, a small
#: upper split on channel 1.
INPUT_DEVICES = [
    {'midi_chan': 0, 'keys': 61, 'begins': 36},
    {'midi_chan': 1, 'keys': 22, 'begins': 48},
]

SVG_IMAGE = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'


def have_zss():
    """True when the real snapshot fixture is available."""
    return ZSS_FIXTURE.is_file()


class DataRootMixin:
    """Creates a temporary data root on behalf of a TestCase."""

    def make_data_root(self, tracks=None, gigs=None, input_devices=None,
                       snapshot=True):
        """Populate and return a fresh temporary data root.

        Parameters
        ----------
        tracks : dict
            Maps ``filename`` to either a JSON-serialisable dict or a raw
            string (use a string to write deliberately malformed JSON).
        gigs : list or None
            Gig definitions for config.json.  When None a single gig is
            built from ``tracks``.
        input_devices : list or None
            Gig-level input devices; defaults to :data:`INPUT_DEVICES`.
        snapshot : bool
            Symlink the .zss fixture into place.  Skipped automatically
            when the fixture is unavailable.
        """
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)

        tracks_dir = root / 'live-session' / 'tracks'
        tracks_dir.mkdir(parents=True)

        if snapshot and have_zss():
            snapshot_dir = root / 'snapshots' / '004-Gigs'
            snapshot_dir.mkdir(parents=True)
            try:
                (snapshot_dir / '004-set3.zss').symlink_to(ZSS_FIXTURE)
            except OSError:
                pass

        for filename, content in (tracks or {}).items():
            path = tracks_dir / filename
            if isinstance(content, str):
                path.write_text(content, encoding='utf-8')
            else:
                path.write_text(json.dumps(content), encoding='utf-8')

        if gigs is None:
            gigs = [self.default_gig(list((tracks or {}).keys()),
                                     input_devices=input_devices)]
        else:
            gigs = [self.with_devices(gig, input_devices) for gig in gigs]

        config_path = root / 'live-session' / 'config.json'
        config_path.write_text(
            json.dumps({'gigs': gigs}), encoding='utf-8')
        return root

    def default_gig(self, filenames, name='Test Gig', zs3_id=ZSS3_ID,
                    input_devices=None):
        return self.with_devices({
            'name': name,
            'description': 'Fixture gig',
            'snapshot_path': SNAPSHOT_REL,
            'tracks': [
                {'name': filename, 'json_filename': 'tracks/' + filename,
                 'zs3_id': zs3_id, 'notes': 'Artist | 120 BPM'}
                for filename in filenames
            ],
        }, input_devices)

    def with_devices(self, gig, input_devices=None):
        gig = dict(gig)
        gig.setdefault('snapshot_path', SNAPSHOT_REL)
        gig['input_devices'] = (
            INPUT_DEVICES if input_devices is None else input_devices)
        return gig

    def write_image(self, root, name='imgs/riff1.svg', data=SVG_IMAGE):
        """Write an image next to the track JSONs and return its path."""
        path = root / 'live-session' / 'tracks' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def track_path(self, root, filename):
        return root / 'live-session' / 'tracks' / filename

    def config_path(self, root):
        return root / 'live-session' / 'config.json'


def import_gigs_to_pdf():
    """Import scripts/gigs_to_pdf.py by path; None when it is absent."""
    import importlib.util

    path = REPO_ROOT / 'scripts' / 'gigs_to_pdf.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('gigs_to_pdf_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module