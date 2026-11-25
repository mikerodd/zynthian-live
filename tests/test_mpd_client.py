# -*- coding: utf-8 -*-
"""Tests for the MPD text-protocol client, against a fake MPD on localhost."""

import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))

import mpd_client
from mpd_client import MpdError, quote


class FakeMpd:
    """Accepts one connection, answers each command from a script."""

    def __init__(self, replies):
        self.replies = replies
        self.received = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self):
        self.sock.settimeout(0.5)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.thread.join(timeout=5)
        self.sock.close()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                f = conn.makefile('rb')
                conn.sendall(b'OK MPD 0.23.17\n')
                for raw in f:
                    command = raw.decode('utf-8').rstrip('\n')
                    self.received.append(command)
                    reply = list(self.replies.get(command, []))
                    if not reply or not reply[-1].startswith(('OK', 'ACK')):
                        reply.append('OK')
                    conn.sendall(''.join(line + '\n' for line in reply).encode('utf-8'))


class QuoteTests(unittest.TestCase):
    def test_plain_name_is_quoted(self):
        self.assertEqual('"tenessee.flac"', quote('tenessee.flac'))

    def test_spaces_stay_inside_quotes(self):
        self.assertEqual('"we are family.flac"', quote('we are family.flac'))

    def test_quotes_and_backslashes_are_escaped(self):
        self.assertEqual('"a\\"b\\\\c"', quote('a"b\\c'))


class MpdClientTests(unittest.TestCase):
    def env(self, port):
        return mock.patch.dict(os.environ, {
            'ZYNTHIAN_MPD_HOST': '127.0.0.1',
            'ZYNTHIAN_MPD_PORT': str(port),
        })

    def test_play_track_clears_adds_and_plays(self):
        fake = FakeMpd({})
        with fake, self.env(fake.port):
            mpd_client.play_track('we are family.flac')
        self.assertEqual(
            ['clear', 'add "we are family.flac"', 'play'], fake.received)

    def test_seek_sends_signed_offsets(self):
        fake = FakeMpd({})
        with fake, self.env(fake.port):
            mpd_client.seek(10)
            mpd_client.seek(-10)
        self.assertEqual(['seekcur +10', 'seekcur -10'], fake.received)

    def test_pause_stop_and_begin_commands(self):
        fake = FakeMpd({})
        with fake, self.env(fake.port):
            mpd_client.pause()
            mpd_client.stop()
            mpd_client.begin()
        self.assertEqual(['pause 1', 'stop', 'play 0'], fake.received)

    def test_state_and_file_reads_status_and_current_song(self):
        fake = FakeMpd({
            'status': ['volume: 80', 'state: pause'],
            'currentsong': ['file: tenessee.flac', 'Title: x'],
        })
        with fake, self.env(fake.port):
            self.assertEqual(('pause', 'tenessee.flac'),
                             mpd_client.state_and_file())

    def test_state_defaults_to_stop_without_current_song(self):
        fake = FakeMpd({'status': ['state: stop'], 'currentsong': []})
        with fake, self.env(fake.port):
            self.assertEqual(('stop', None), mpd_client.state_and_file())

    def test_ack_raises_mpd_error(self):
        fake = FakeMpd({'seekcur +10': ['ACK [50@0] {seekcur} Not playing']})
        with fake, self.env(fake.port):
            with self.assertRaises(MpdError) as ctx:
                mpd_client.seek(10)
        self.assertIn('Not playing', str(ctx.exception))

    def test_unreachable_host_raises_oserror(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()
        with self.env(port):
            with self.assertRaises(OSError):
                mpd_client.pause()


if __name__ == '__main__':
    unittest.main()
