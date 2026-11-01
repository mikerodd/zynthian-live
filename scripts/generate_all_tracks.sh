#!/bin/bash

FILENAME=004-Gigs/004-set3.zss
PDFNAME=all-tracks.pdf
PORT=8000

ask_yes_no() {
    local prompt="$1"
    local answer
    read -r -p "$prompt [Y/n] " answer
    case "$answer" in
        ""|y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
}

if ask_yes_no "Download ${FILENAME} from Zynthian?"; then
    echo "downloading ${FILENAME} from Zynthian..."
    ../../zynthian-live-data/snapshots/pull_snapshot.py ${FILENAME}
else
    echo "skipping download, using existing ${FILENAME}"
fi

echo generating ${PDFNAME}
make -C ../../zynthian-live-data/live-session/tracks/imgs/lilypond/
./gigs_to_pdf.py --gigs all --config ../../zynthian-live-data/live-session/config.json --alpha --out ${PDFNAME}

if ask_yes_no "Start the web server to view the PDFs on port ${PORT}?"; then
    echo "serving $(pwd) on port ${PORT} (Ctrl+C to stop)"
    python3 -m http.server ${PORT}
fi
