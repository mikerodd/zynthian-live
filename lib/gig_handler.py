# -*- coding: utf-8 -*-
import os
import re
import json
import logging

MY_DATA_DIR = os.environ.get(
    'ZYNTHIAN_MY_DATA_DIR',
    '/zynthian/zynthian-my-data'
)
CONFIG_PATH = os.path.join(MY_DATA_DIR, 'live-session', 'config.json')
GIGS_BUILD_DIR = os.path.join(MY_DATA_DIR, 'live-session', 'gigs')


def _slug_to_name(slug):
    name = slug.replace("-", " ")
    name = re.sub(r"(?:^| )\w", lambda m: m.group().upper(), name)
    return name


def _load_track_list():
    if not os.path.isfile(CONFIG_PATH):
        return {"gigs": []}
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    tracks_by_snapshot = {}
    for entry in config.get("track_detail", []):
        snap = entry["snapshot"]
        tracks_by_snapshot.setdefault(snap, []).append(entry)

    gigs_out = []
    for ds in config.get("displayed_snapshots", []):
        zss = ds["zss_name"]
        name = ds.get("name") or _slug_to_name(
            os.path.splitext(os.path.basename(zss))[0]
        )
        description = ds.get("description", "")
        tracks = []
        for t in tracks_by_snapshot.get(zss, []):
            chart = t["html_filename"]
            if chart.startswith("gigs/"):
                chart = chart[5:]
            track_name = _slug_to_name(os.path.splitext(chart)[0])
            tracks.append({
                "name": track_name,
                "chart": chart,
                "zs3_id": t["subsnapshot"],
                "notes": t.get("notes", "")
            })
        gigs_out.append({
            "name": name,
            "description": description,
            "tracks": tracks
        })

    return {"gigs": gigs_out}


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
