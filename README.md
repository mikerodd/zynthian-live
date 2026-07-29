# Zynthian Live Session

Web-based live session manager for Zynthian. Displays chord charts, keyboard splits, and loads ZS3 sub-snapshots via OSC during rehearsals and gigs.

## Structure

```
zynthian-live/           # Server code (deployed to Zynthian)
├── lib/
│   ├── gig_handler.py   — reads config.json from my-data, serves gigs/tracks
│   └── zs3_handler.py   — OSC bridge to load ZS3 sub-snapshots
├── templates/           — Tornado HTML templates
├── static/              — CSS and JS
├── live_session_server.py  — Tornado web server
├── live_session.sh      — startup script
└── install.sh           — deploy server code to Zynthian

gigs-v2/                 # Build pipeline (runs on computer)
├── live-session/
│   ├── config.json      — gig/snapshot/track definitions (single source of truth)
│   └── gigs/            — generated chart HTML files (output of build-v2.py)
├── *.json               — per-song data (chords, structure, keyboard splits)
├── *.ly                 — LilyPond source for chord diagrams
├── build-v2.py          — generates HTML with base64-embedded SVGs
├── genkeyb2.py          — generates keyboard split SVGs
├── gen-tracklist.py     — downloads ZSS from Zynthian, outputs tracks
└── install.sh           — build charts + copy config + charts to Zynthian my-data

# On Zynthian, data lives under $ZYNTHIAN_MY_DATA_DIR/live-session/
#   config.json  — gig/snapshot/track definitions
#   gigs/        — generated chart HTML files
```

## Usage (on computer — build charts)

```bash
cd gigs-v2
# Edit config.json and song data as needed, then:
./install.sh
```

## Usage (on computer — deploy server code)

```bash
cd zynthian-live
./install.sh
```

## Usage (on Zynthian — live)

Connect your tablet/phone or computer to Zynthian WiFi AP, then open `http://<address>:8080`.

- Tap a track to load its ZS3 sub-snapshot and view the chart
- The chart shows: chord grid → keyboard split → track structure table

## Dependencies

- Zynthian OS (tested)
- Python 3 with Tornado and pyliblo3
- Works on iPad 2+ / any device with a browser
