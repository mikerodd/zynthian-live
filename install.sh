#!/bin/bash
# Install live session server to Zynthian via SSH
# Usage: ./install.sh [host]
# Default host: zynthian.local

set -e

HOST="${1:-zynthian.local}"
DEST="/zynthian/zynthian-live"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Copying server to root@${HOST}:${DEST}..."
tar -C "${SCRIPT_DIR}" -cf - \
    lib templates static \
    live_session_server.py live_session.sh |
    ssh root@"${HOST}" "
        mkdir -p ${DEST}
        tar -C ${DEST} -xf -
        chmod +x ${DEST}/live_session_server.py
        chmod +x ${DEST}/live_session.sh
    "

echo "Done. Run: ssh root@${HOST} '${DEST}/live_session.sh'"
