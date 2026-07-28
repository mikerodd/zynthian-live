# -*- coding: utf-8 -*-
import os
import json
import logging

BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
GIGS_DIR = os.path.join(BASE_DIR, 'gigs')

GIG_TRACK_LIST = os.path.join(GIGS_DIR, 'gig-track-list.json')
GIGS_BUILD_DIR = os.path.join(GIGS_DIR, 'out')
if not os.path.isdir(GIGS_BUILD_DIR):
    GIGS_BUILD_DIR = GIGS_DIR


def _load_track_list():
    if os.path.isfile(GIG_TRACK_LIST):
        with open(GIG_TRACK_LIST, 'r') as f:
            return json.load(f)
    return {}


def list_gigs():
    gigs = []
    data = _load_track_list()
    for i, gig in enumerate(data.get('gigs', [])):
        gig_id = str(i)
        gigs.append({
            'id': gig_id,
            'name': gig.get('name', gig_id),
            'description': gig.get('description', ''),
            'track_count': len(gig.get('tracks', []))
        })
    return gigs


def load_gig(gig_id):
    data = _load_track_list()
    gigs = data.get('gigs', [])
    try:
        return gigs[int(gig_id)]
    except (ValueError, IndexError):
        return None


def get_chart_path(gig_id, filename):
    fpath = os.path.join(GIGS_BUILD_DIR, filename)
    if os.path.isfile(fpath):
        return fpath
    return None


def list_charts(gig_id):
    if not os.path.isdir(GIGS_BUILD_DIR):
        return []
    return [f for f in os.listdir(GIGS_BUILD_DIR) if f.endswith(('.html', '.htm'))]
