# -*- coding: utf-8 -*-
"""OSC helpers for talking to the Zynthian UI.

The module keeps a small singleton :class:`OSCClient` so callers can keep
using the historical module-level functions, while new code can hold an
explicit client instance.
"""

import logging
import os
from typing import Any

try:
    import pyliblo3 as liblo
    LIBLO_AVAILABLE = True
except ImportError:
    try:
        import liblo
        LIBLO_AVAILABLE = True
    except ImportError:
        liblo = None
        LIBLO_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class OSCClient:
    """Thin wrapper around a liblo OSC destination."""

    def __init__(self, host: str = 'localhost', port: int = 1370) -> None:
        self.available: bool = False
        self.addr: Any = None
        if not LIBLO_AVAILABLE:
            LOGGER.warning('pyliblo3/liblo not available, OSC disabled')
            return
        try:
            self.addr = liblo.Address(host, port, liblo.UDP)
            self.available = True
            LOGGER.info('OSC initialized: %s:%s', host, port)
        except Exception as exc:  # pragma: no cover - depends on liblo
            LOGGER.warning('OSC not available: %s', exc)

    def send_zs3(self, zs3_id: str) -> bool:
        if not self.available or self.addr is None:
            LOGGER.warning("OSC not initialized, cannot load ZS3 '%s'", zs3_id)
            return False
        try:
            liblo.send(self.addr, '/CUIA/ZS3_LOAD', ('s', str(zs3_id)))
            LOGGER.info('Sent ZS3_LOAD: %s', zs3_id)
            return True
        except Exception as exc:
            LOGGER.error("Failed to send ZS3_LOAD '%s': %s", zs3_id, exc)
            return False

    def send_snapshot(self, bank: int, program: int,
                      master_chan: int | None = None) -> bool:
        if not self.available or self.addr is None:
            LOGGER.warning(
                'OSC not initialized, cannot load snapshot bank=%s program=%s',
                bank, program)
            return False
        if master_chan is None:
            master_chan = _get_master_chan()
        try:
            liblo.send(self.addr, '/CUIA/ZYN_CC', master_chan, _get_bank_cc(), bank)
            import time
            time.sleep(0.05)
            liblo.send(self.addr, '/CUIA/PROGRAM_CHANGE', program, master_chan)
            LOGGER.info(
                'Sent bank=%s program=%s on master channel', bank, program)
            return True
        except Exception as exc:
            LOGGER.error(
                'Failed to send snapshot bank=%s program=%s: %s',
                bank, program, exc)
            return False


# Module-level singleton used by the legacy helpers below.
osc_client: OSCClient = OSCClient()


# Backwards-compatible alias for older callers/tests.
ZYNTHIAN_UI_OSC_ADDR: Any = osc_client.addr


def init_osc(host: str = 'localhost', port: int = 1370) -> None:
    global osc_client, ZYNTHIAN_UI_OSC_ADDR
    osc_client = OSCClient(host, port)
    ZYNTHIAN_UI_OSC_ADDR = osc_client.addr


def load_zs3(zs3_id: Any) -> bool:
    return osc_client.send_zs3(str(zs3_id))


def _get_master_chan() -> int:
    val = os.environ.get('ZYNTHIAN_MIDI_MASTER_CHANNEL', '16')
    return int(val) - 1


def _get_bank_cc() -> int:
    raw = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM', '0')
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        LOGGER.warning('Invalid ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM %r: %s; defaulting to 0', raw, exc)
        return 0


def load_snapshot(bank: int, program: int) -> bool:
    return osc_client.send_snapshot(bank, program)
