#!/bin/bash
# Build charts, refresh local gigs directory, then install to Zynthian via SSH
# Usage: ./install.sh [host]
# Default host: zynthian.local

set -e

HOST="${1:-zynthian.local}"
DEST="/zynthian/zynthian-live"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIGS_V2_DIR="$(cd "${SCRIPT_DIR}/../gigs-v2" && pwd)"

echo "=== 1/3 Building charts from gigs-v2/..."
(cd "${GIGS_V2_DIR}" && python3 build-v2.py)

echo "=== 2/3 Refreshing gigs/ directory..."
cp "${GIGS_V2_DIR}/gig-track-list.json" "${SCRIPT_DIR}/gigs/"
cp "${GIGS_V2_DIR}/out/"*.html "${SCRIPT_DIR}/gigs/"

echo "=== 3/3 Copying to root@${HOST}:${DEST}..."
tar -C "${SCRIPT_DIR}" -cf - \
    gigs lib templates static \
    live_session_server.py live_session.sh |
    ssh root@"${HOST}" "
        mkdir -p ${DEST}
        tar -C ${DEST} -xf -
        chmod +x ${DEST}/live_session_server.py
        chmod +x ${DEST}/live_session.sh
    "

echo "Done. Files installed to ${DEST} on ${HOST}"
echo "Run: ssh root@${HOST} '${DEST}/live_session.sh'"
