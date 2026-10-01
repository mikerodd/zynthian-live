#!/bin/bash
# Install live session server to Zynthian via SSH
# Usage: ./install.sh [host]
# Default host: zynthian.local
#
# Deploys everything via SSH using a single shared connection (ControlMaster),
# so the password is only asked once:
#   - the live session app to /zynthian/zynthian-live
#   - the systemd unit to /etc/systemd/system/zynthian-live.service
#   - daemon-reload + enable the service

set -e

HOST="${1:-zynthian.local}"
DEST="/zynthian/zynthian-live"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Zynthian standard locations (overridable via env)
ZYNTHIAN_DIR="${ZYNTHIAN_DIR:-/zynthian}"
ZYNTHIAN_SYS_DIR="${ZYNTHIAN_SYS_DIR:-$ZYNTHIAN_DIR/zynthian-sys}"

# Render the systemd unit with placeholders substituted
SVC_FILE=/tmp/zynthian-live.service.deploy
sed -e "s|#ZYNTHIAN_DIR#|${ZYNTHIAN_DIR}|g" \
    -e "s|#ZYNTHIAN_SYS_DIR#|${ZYNTHIAN_SYS_DIR}|g" \
    "${SCRIPT_DIR}/../zynthian-sys/etc/systemd/zynthian-live.service" > "$SVC_FILE"

# Shared connection socket for the whole deploy (single password prompt)
SOCK="$(mktemp -u /tmp/zl-install.XXXXXX)"
CTRL_MASTER="ssh -o ControlMaster=yes -o ControlPath=$SOCK -o ControlPersist=60"
CTRL_SLAVE="ssh -o ControlPath=$SOCK"

echo "Connecting to root@${HOST} (asked for password once)..."
$CTRL_MASTER "root@$HOST" true

cleanup() {
    $CTRL_SLAVE -O exit "$HOST" 2>/dev/null || true
    rm -f "$SOCK"
}
trap cleanup EXIT

echo "Copying server to ${DEST}..."
tar -C "${SCRIPT_DIR}" -cf - \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.#*' --exclude='*~' \
    --exclude='#*#' \
    --exclude='.git' \
    lib templates static \
    live_session_server.py live_session.sh |
    $CTRL_SLAVE "$HOST" "
        mkdir -p ${DEST}
        tar -C ${DEST} -xf -
        chmod +x ${DEST}/live_session_server.py
        chmod +x ${DEST}/live_session.sh
    "

echo "Installing zynthian-live systemd unit..."
scp -o ControlPath=$SOCK "$SVC_FILE" "root@${HOST}:/etc/systemd/system/zynthian-live.service"

echo "Reloading systemd and enabling service..."
$CTRL_SLAVE "$HOST" "
    systemctl daemon-reload
    if [ \"\$(systemctl is-enabled zynthian-live)\" != \"enabled\" ]; then
        systemctl enable zynthian-live
    fi
"

rm -f "$SVC_FILE"

echo "Done."
echo "  Start now with:   ssh root@${HOST} 'systemctl start zynthian-live'"
echo "  Or run manually:  ssh root@${HOST} '${DEST}/live_session.sh'"
