#!/bin/bash
# Build charts, refresh local gigs directory, then install to Zynthian via SSH
# Usage: ./install.sh [host]
# Default host: zynthian.local

set -e

HOST="${1:-zynthian.local}"
DEST="/zynthian/zynthian-live"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


echo "=== 3/3 Copying to root@${HOST}:${DEST}..."
tar -C "${SCRIPT_DIR}" -cf - \
    lib templates static \
    live_session_server.py live_session.sh |
    ssh root@"${HOST}" "
        mkdir -p ${DEST}
        tar -C ${DEST} -xf -
        chmod +x ${DEST}/live_session_server.py
        chmod +x ${DEST}/live_session.sh
    "

echo "Done. Files installed to ${DEST} on ${HOST}"
echo "Run: ssh root@${HOST} '${DEST}/live_session.sh'"
