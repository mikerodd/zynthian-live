# -*- coding: utf-8 -*-
"""Minimal MPD client for the play-along controls.

Speaks the MPD text protocol over TCP. Each call opens a short-lived
connection with a timeout, so an unreachable MPD host fails the request
instead of hanging the page.

Environment:
    ZYNTHIAN_MPD_HOST  MPD host name or address (default: localhost)
    ZYNTHIAN_MPD_PORT  MPD port (default: 6600)
"""

import os
import socket

TIMEOUT = 3.0
SEEK_STEP = 10


class MpdError(Exception):
    """MPD answered with an ACK, for example 'Not playing'."""


def _address() -> tuple[str, int]:
    host = os.environ.get('ZYNTHIAN_MPD_HOST', 'localhost')
    port = int(os.environ.get('ZYNTHIAN_MPD_PORT', '6600'))
    return host, port


def quote(value: str) -> str:
    """Quote an argument for the MPD protocol (escape backslash and quote)."""
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _read_response(f) -> list[str]:
    lines = []
    while True:
        line = f.readline()
        if not line:
            raise OSError('connection closed by MPD')
        line = line.rstrip('\n')
        if line == 'OK':
            return lines
        if line.startswith('ACK'):
            raise MpdError(line)
        lines.append(line)


def run(commands: list[str]) -> list[list[str]]:
    """Send commands on one connection; return each command's response lines."""
    with socket.create_connection(_address(), timeout=TIMEOUT) as sock:
        f = sock.makefile('r', encoding='utf-8', newline='\n')
        greeting = f.readline()
        if not greeting.startswith('OK MPD'):
            raise OSError('not an MPD server: {!r}'.format(greeting))
        results = []
        for command in commands:
            sock.sendall((command + '\n').encode('utf-8'))
            results.append(_read_response(f))
        return results


def play_track(path: str) -> None:
    """Replace the queue with one file and start it."""
    run(['clear', 'add {}'.format(quote(path)), 'play'])


def resume() -> None:
    run(['play'])


def pause() -> None:
    run(['pause 1'])


def stop() -> None:
    run(['stop'])


def begin() -> None:
    """Restart the queued track from its beginning."""
    run(['play 0'])


def seek(seconds: int) -> None:
    run(['seekcur {:+d}'.format(seconds)])


def state_and_file() -> tuple[str, str | None]:
    """Return the playback state ('play', 'pause' or 'stop') and current file."""
    status, current = run(['status', 'currentsong'])
    state = next((line[len('state: '):] for line in status
                  if line.startswith('state: ')), 'stop')
    file = next((line[len('file: '):] for line in current
                 if line.startswith('file: ')), None)
    return state, file
