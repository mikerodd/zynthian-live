#!/bin/bash
# Zynthian Live Session Server (zynthian-live)
# Starts a Tornado web server for live gig management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


# Default port
export LIVE_SESSION_PORT="${LIVE_SESSION_PORT:-8080}"

cd "$SCRIPT_DIR"
./live_session_server.py
