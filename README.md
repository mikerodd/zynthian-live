# Zynthian Live Session

Web-based live session manager for Zynthian. Displays chord charts, notation images, keyboard splits, and loads ZS3 sub-snapshots via OSC during rehearsals and gigs.

Pages are generated dynamically for each request. The server reads `config.json` and the selected track's JSON from `/zynthian/zynthian-my-data/live-session/` and renders the content through Tornado templates; chart components such as the chord grid, keyboard SVG, and structure table are assembled server-side. Pre-generated `gigs/*.html` files are not required or served by the current application.

## Structure

```
zynthian-live/
├── lib/
│   ├── gig_handler.py     — reads config.json and track metadata from my-data
│   ├── track_renderer.py  — converts track JSON into chart HTML and SVG
│   └── zs3_handler.py     — OSC bridge to load ZS3 sub-snapshots
├── templates/             — Tornado HTML templates
├── static/                — CSS and fonts
├── live_session_server.py — Tornado web server
├── live_session.sh        — startup script
├── requirements.txt       — Python dependencies (Tornado)
└── install.sh             — deploy server code to Zynthian
```

## Desktop setup (dev / test)

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Run against the bundled test data:

```bash
ZYNTHIAN_MY_DATA_DIR=/path/to/zynthian-live/test ./venv/bin/python live_session_server.py
```

Then open `http://<desktop-ip>:8080`. Only `tornado` is required to serve
pages; `pyliblo3` (OSC) is optional and enables ZS3/snapshot loading.

## Data flow

```
$ZYNTHIAN_MY_DATA_DIR/
├── live-session/
│   ├── config.json       — gig and track definitions
│   └── tracks/
│       ├── *.json        — chart data referenced by each track
│       └── imgs/*        — optional images referenced by track JSON
└── <snapshot_path>/*.zss — snapshots referenced by each gig
        ↓ each page request
Python loaders/renderers + Tornado templates
        ↓
Complete HTML pages in the browser
```

The data directory defaults to `/zynthian/zynthian-my-data` and can be
overridden with `ZYNTHIAN_MY_DATA_DIR`. The gig list and track list use
`live-session/config.json`; chart pages read the selected track JSON and
generate their HTML, SVG, and section order at request time. Keyboard split
data is also read from the `.zss` snapshot selected by the gig.

## Images

Add `images` to the track's `display` list and provide image entries with source
paths relative to that track's JSON file:

```json
"display": ["leadsheet", "split", "structure", "images"],
"images": [
  {
    "caption": "riff1",
    "source": "imgs/riff1.svg"
  },
  {
    "caption": "riff2",
    "source": "imgs/riff2.svg"
  }
]
```

The optional `caption` is displayed to the left of its image. A plain string
path is also accepted for images without captions. SVG, PNG, JPEG, GIF, and
WebP images are supported. Images are embedded into both web pages and
generated PDFs. Missing, unsupported, or unsafe paths are logged and skipped.

## Deploy

```bash
./install.sh
```

Installs everything in one go over a single SSH connection (so the password is
asked only once):
- the server code to `/zynthian/zynthian-live`
- the systemd unit `/etc/systemd/system/zynthian-live.service` (placeholders substituted)
- runs `systemctl daemon-reload` and enables the service

Then start it with `ssh root@zynthian.local 'systemctl start zynthian-live'`.

## Usage (on Zynthian — live)

- The server reads `config.json` from `/zynthian/zynthian-my-data/live-session/`, not from this repo
- Connect your tablet/phone or computer to Zynthian WiFi AP, then open `http://<address>:8080`.
- Tap a track: the server loads its ZS3 sub-snapshot then shows the chart, in a single request
- The chart follows the `display` order and can include chord grids, keyboard splits, structure tables, and images

> **Important:** snapshot loading relies on MIDI bank/program change on the
> Zynthian **Master Channel**. This is not set by default on a clean install.
> Configure it in Zynthian webconf (Settings → MIDI → Master Channel) or bank/
> program changes will be silently ignored.


## Dependencies

- Python 3 with Tornado
- `pyliblo3` is optional and enables ZS3 snapshot loading on the Zynthian
- Works on iPad 2+ / any device with a browser
