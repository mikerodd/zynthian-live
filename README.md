# Zynthian Live Session

Web-based live session manager for Zynthian. Displays chord charts, keyboard splits, and loads ZS3 sub-snapshots via OSC during rehearsals and gigs.

## Structure

```
zynthian-live/
├── lib/
│   ├── gig_handler.py        — reads config.json from my-data, serves gigs/tracks
│   └── zs3_handler.py        — OSC bridge to load ZS3 sub-snapshots
├── templates/                — Tornado HTML templates
├── static/                   — CSS and JS
├── live_session_server.py    — Tornado web server
├── live_session.sh           — startup script
└── install.sh                — deploy to Zynthian

# live-session data lives on Zynthian under $ZYNTHIAN_MY_DATA_DIR/live-session/
#   config.json  — gig/snapshot/track definitions
#   gigs/        — generated chart HTML files
```

## Usage (on computer)
the html chords files are generated outside the server, on a computer. I provided some files here 

To deploy to Zynthian:

```bash
cd ../zynthian-live
./install.sh
```

## Usage (on Zynthian - live)

Connect your tablet/phone or computer  to Zynthian WiFi AP, then open `http://<address>:8080`.

- Tap a track to load its ZS3 sub-snapshot and view the chart
- The chart shows: chord grid → keyboard split → track structure table

## Dependencies

- Zynthian OS (tested)
- Python 3 with Tornado and pyliblo3
- works on iPad 2+ / any device with a browser

