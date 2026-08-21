# -*- coding: utf-8 -*-
"""Load gig/track configuration for the live session server.

Config format (v2):
{
  "gigs": [
    {
      "name": "Gig Name",
      "description": "...",
      "snapshot_path": "path/to/snapshot.zss",
      "tracks": [
        {
          "name": "Song Title",
          "json_filename": "tracks/song.json",
          "txt_filename": "tracks/song.txt",
          "zs3_id": "zs3-10",
          "notes": "Artist | 120 BPM"
        }
      ]
    }
  ]
}
"""
import os
import json
import logging

MY_DATA_DIR = os.environ.get(
    'ZYNTHIAN_MY_DATA_DIR',
    '/zynthian/zynthian-my-data'
)
CONFIG_PATH = os.path.join(MY_DATA_DIR, 'live-session', 'config.json')


def _load_config():
    if not os.path.isfile(CONFIG_PATH):
        return {'gigs': []}
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def _base_dir():
    return os.path.dirname(CONFIG_PATH)


def _parse_bank_program(snapshot_path):
    """Extract bank and program numbers from a snapshot path like '.../004-Gigs/002-set2.zss'."""
    try:
        basename = os.path.basename(snapshot_path)
        parent = os.path.basename(os.path.dirname(snapshot_path))
        bank = int(parent[:3])
        program = int(basename[:3])
        return bank, program
    except (ValueError, IndexError):
        return None, None


def _resolve(path):
    """Resolve a config-relative path to an absolute path."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(_base_dir(), path))


def list_gigs():
    config = _load_config()
    gigs = []
    for i, gig in enumerate(config.get('gigs', [])):
        snap = os.path.join(MY_DATA_DIR, gig.get('snapshot_path', ''))
        bank, program = _parse_bank_program(snap)
        gigs.append({
            'id': str(i),
            'name': gig.get('name', 'Gig {}'.format(i + 1)),
            'description': gig.get('description', ''),
            'track_count': len(gig.get('tracks', [])),
            'bank': bank,
            'program': program,
        })
    return gigs


def load_gig(gig_id):
    config = _load_config()
    gigs = config.get('gigs', [])
    try:
        return gigs[int(gig_id)]
    except (ValueError, IndexError):
        return None


def get_track_paths(gig_id, track_idx):
    """Return resolved absolute paths for a track's files.

    Returns dict with keys: json_path, txt_path, snapshot_path.
    Missing files are None.
    """
    gig = load_gig(gig_id)
    if gig is None:
        return None
    try:
        track = gig['tracks'][int(track_idx)]
    except (KeyError, IndexError, ValueError):
        return None

    snapshot_path = os.path.normpath(os.path.join(MY_DATA_DIR, gig.get('snapshot_path', '')))
    json_path = _resolve(track.get('json_filename', ''))

    return {
        'json_path': json_path if os.path.isfile(json_path) else None,
        'snapshot_path': snapshot_path if os.path.isfile(snapshot_path) else None,
        'zs3_id': track.get('zs3_id'),
        'name': track.get('name', ''),
        'notes': track.get('notes', ''),
        'input_devices': gig.get('input_devices', []),
    }
