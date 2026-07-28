# Zynthian Live Session

Web-based live session manager for Zynthian. Displays chord charts, keyboard splits, and loads ZS3 sub-snapshots via OSC during rehearsals and gigs.

## Structure

```
zynthian-live/
├── gigs/
│   ├── gig-track-list.json   — gig definitions and track list
│   └── *.html                — generated chart files
├── lib/
│   ├── gig_handler.py        — loads gig/track data from gig-track-list.json
│   └── zs3_handler.py        — OSC bridge to load ZS3 sub-snapshots
├── templates/                — Tornado HTML templates
├── static/                   — CSS and JS
├── live_session_server.py    — Tornado web server
├── live_session.sh           — startup script
└── install.sh                — build + deploy to Zynthian
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

