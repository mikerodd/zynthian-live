# -*- coding: utf-8 -*-
"""Tests for the OSC sender used to reach spaph."""

import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))

import spaph_client


def read_osc_string(data, pos):
    end = data.index(b'\x00', pos)
    text = data[pos:end].decode('utf-8')
    pos = end + 1 + (-(end + 1 - pos) % 4)
    return text, pos


class EncodeTests(unittest.TestCase):
    def test_message_is_address_type_tag_and_string(self):
        packet = spaph_client.encode_command('backing play')
        self.assertEqual(0, len(packet) % 4)
        address, pos = read_osc_string(packet, 0)
        tags, pos = read_osc_string(packet, pos)
        text, pos = read_osc_string(packet, pos)
        self.assertEqual('/spaph/command', address)
        self.assertEqual(',s', tags)
        self.assertEqual('backing play', text)
        self.assertEqual(len(packet), pos)

    def test_names_with_spaces_and_accents_survive(self):
        packet = spaph_client.encode_command('backing load été à la mer.flac')
        _, pos = read_osc_string(packet, 0)
        _, pos = read_osc_string(packet, pos)
        text, _ = read_osc_string(packet, pos)
        self.assertEqual('backing load été à la mer.flac', text)

    def test_string_lengths_that_are_multiples_of_four_get_a_full_pad(self):
        packet = spaph_client.encode_command('abc')
        self.assertEqual(0, len(packet) % 4)


class SendTests(unittest.TestCase):
    def test_command_is_sent_as_one_datagram_to_the_configured_address(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(('127.0.0.1', 0))
        receiver.settimeout(2)
        port = receiver.getsockname()[1]
        env = {'ZYNTHIAN_SPAPH_HOST': '127.0.0.1', 'ZYNTHIAN_SPAPH_PORT': str(port)}
        try:
            with mock.patch.dict(os.environ, env):
                spaph_client.command('backing stop')
            data, _ = receiver.recvfrom(4096)
        finally:
            receiver.close()
        self.assertEqual(spaph_client.encode_command('backing stop'), data)


if __name__ == '__main__':
    unittest.main()
