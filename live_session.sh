#!/bin/bash
# Zynthian Live Session Server (zynthian-live)
# Starts a Tornado web server for live gig management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source Zynthian environment (needed for Python packages like tornado)
if [ -f /zynthian/zynthian-sys/scripts/zynthian_envars_extended.sh ]; then
    source /zynthian/zynthian-sys/scripts/zynthian_envars_extended.sh
fi

# Default port
export LIVE_SESSION_PORT="${LIVE_SESSION_PORT:-8080}"

cd "$SCRIPT_DIR"
exec ./live_session_server.py
