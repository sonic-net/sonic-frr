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
    _instance_count = 0

    def __init__(self, *args, **kwargs):
        super(MockSocket, self).__init__(*args, **kwargs)
        MockSocket._instance_count %= 2
        MockSocket._instance_count += 1
        self.first = True

    def connect(self, *args, **kwargs):
        pass

    def send(self, *args, **kwargs):
        pass

    def recv(self, *args, **kwargs):
        if not self.first:
            return None
        self.first = False

        if MockSocket._instance_count == 1:
            filename = INPUT_DIR + '/bgpsummary_ipv4.txt'
        elif MockSocket._instance_count == 2:
            filename = INPUT_DIR + '/bgpsummary_ipv6.txt'

        ret = namedtuple('ret', ['returncode', 'stdout'])
        ret.returncode = 0
        with open(filename, 'rb') as f:
            ret = f.read()
        return ret

# Replace the function with mocked one
socket.socket = MockSocket
