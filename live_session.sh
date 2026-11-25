#!/bin/bash
# Zynthian Live Session Server (zynthian-live)
# Starts a Tornado web server for live gig management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source Zynthian environment (needed for Python packages like tornado)
if [ -f /zynthian/zynthian-sys/scripts/zynthian_envars_extended.sh ]; then
    source /zynthian/zynthian-sys/scripts/zynthian_envars_extended.sh
fi

# Load the MIDI profile too, like zynthian.sh, so the configured master
# MIDI channel and bank-change CC number reach this service.
if [ -z "$ZYNTHIAN_SCRIPT_MIDI_PROFILE" ]; then
    if [ -f "$ZYNTHIAN_MY_DATA_DIR/midi-profiles/default.sh" ]; then
        source "$ZYNTHIAN_MY_DATA_DIR/midi-profiles/default.sh"
    fi
elif [ -f "$ZYNTHIAN_SCRIPT_MIDI_PROFILE" ]; then
    source "$ZYNTHIAN_SCRIPT_MIDI_PROFILE"
fi

if [ -f "$ZYNTHIAN_CONFIG_DIR/zynthian_custom_config.sh" ]; then
    source "$ZYNTHIAN_CONFIG_DIR/zynthian_custom_config.sh"
fi

# Default port
export LIVE_SESSION_PORT="${LIVE_SESSION_PORT:-8080}"

cd "$SCRIPT_DIR"
exec ./live_session_server.py
