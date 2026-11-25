# -*- coding: utf-8 -*-
"""Send console commands to spaph over OSC.

spaph listens for OSC messages on /spaph/command with one string argument, the same text
the spaph console accepts (for example "backing play"). Replies are not sent back, so a
command either reaches spaph or raises OSError here.

Environment:
    ZYNTHIAN_SPAPH_HOST  spaph host name or address (default: winthian.local)
    ZYNTHIAN_SPAPH_PORT  spaph OSC port (default: 9000)
"""

import os
import socket

ADDRESS = '/spaph/command'


def _osc_string(text: str) -> bytes:
    """An OSC string: UTF-8, NUL-terminated, padded to a multiple of four bytes."""
    data = text.encode('utf-8') + b'\x00'
    return data + b'\x00' * (-len(data) % 4)


def encode_command(text: str) -> bytes:
    return _osc_string(ADDRESS) + _osc_string(',s') + _osc_string(text)


def _address() -> tuple[str, int]:
    host = os.environ.get('ZYNTHIAN_SPAPH_HOST', 'winthian.local')
    port = int(os.environ.get('ZYNTHIAN_SPAPH_PORT', '9000'))
    return host, port


def command(text: str) -> None:
    """Send one console command to spaph."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(encode_command(text), _address())
