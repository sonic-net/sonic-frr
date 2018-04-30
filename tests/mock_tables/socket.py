import os
from collections import namedtuple
import unittest
from unittest import TestCase, mock
from unittest.mock import patch, mock_open, MagicMock

INPUT_DIR = os.path.dirname(os.path.abspath(__file__))

import socket

# Backup original class
_socket_class = socket.socket

# Monkey patch
class MockSocket(_socket_class):

    def __init__(self, *args, **kwargs):
        super(MockSocket, self).__init__(*args, **kwargs)
        self._string_sent = b''

    def connect(self, *args, **kwargs):
        pass

    def send(self, *args, **kwargs):
        string = args[0]
        self._string_sent = string
        pass

    def recv(self, *args, **kwargs):
        if b'show ip bgp summary' in self._string_sent:
            filename = INPUT_DIR + '/bgpsummary_ipv4.txt'
        elif b'show ipv6 bgp summary' in self._string_sent:
            filename = INPUT_DIR + '/bgpsummary_ipv6.txt'
        else:
            return None

        self._string_sent = b''
        ret = namedtuple('ret', ['returncode', 'stdout'])
        ret.returncode = 0
        with open(filename, 'rb') as f:
            ret = f.read()
        return ret

# Replace the function with mocked one
socket.socket = MockSocket
