import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))
import struct
from unittest import TestCase
from ax_interface.encodings import ObjectIdentifier, OctetString, SearchRange, ValueRepresentation
from ax_interface import constants


class TestPDUEncodings(TestCase):
    def test_oid_zero(self):
        null_oid_ints = (0, 0, 0, 0)
        null_oid_bytes = struct.pack('!BBBB', *null_oid_ints)

        null_oid = ObjectIdentifier.from_bytes(null_oid_bytes, '!')
        self.assertEqual(null_oid.n_subid, 0)
        self.assertEqual(null_oid.prefix_, 0)
        self.assertEqual(null_oid.include, 0)
        self.assertEqual(null_oid.reserved, 0)
        self.assertIs(null_oid.subids, ())

    def test_oid(self):
        oid1 = ObjectIdentifier(4, 2, 0, 0, (1, 1, 1, 0))
        self.assertEqual(str(oid1), '.1.3.6.1.2.1.1.1.0')
        self.assertEqual(oid1.size, 20)
        print(oid1)
        oid2 = ObjectIdentifier.from_bytes(oid1.to_bytes('!'), '!')  # round-trip
        self.assertEqual(str(oid2), '.1.3.6.1.2.1.1.1.0')
        self.assertEqual(oid2.size, 20)

        oid_literal = ObjectIdentifier(4, 0, 0, 0, (1, 2, 3, 4))
        self.assertEqual(str(oid_literal), '.1.2.3.4')
        print(oid_literal)

        oid_small = ObjectIdentifier(0, 0, 0, 0, ())
        self.assertEqual(oid_small.size, 4)

        dell_oid = ObjectIdentifier(n_subid=7, prefix_=4, include=0, reserved=0, subids=(1, 6027, 3, 10, 1, 2, 9))
        check = ObjectIdentifier.from_bytes(dell_oid.to_bytes('!'), '!')
        self.assertEqual(check, dell_oid)

    def test_from_iterable(self):
        subtree = (1, 3, 6, 1, 2, 1, 1, 1, 0)
        obj = ObjectIdentifier.from_iterable(subtree)
        self.assertEqual(str(obj), '.1.3.6.1.2.1.1.1.0')

        subtree = (1, 2, 3, 4)
        obj = ObjectIdentifier.from_iterable(subtree)
        self.assertEqual(str(obj), '.1.2.3.4')

    def test_bad_unpack(self):
        with self.assertRaises(struct.error):
            # garbage data. Don't assume '' -> 0, 0, 0...
            ObjectIdentifier.from_bytes(b'', '')

        with self.assertRaises(struct.error):
            # n_subid = 4 -> should be at least 20 bytes -> input is too short.
            ObjectIdentifier.from_bytes(b'\x04\x00\x00\x00', '!')

        with self.assertRaises(struct.error):
            # Bad format specifier.
            ObjectIdentifier.from_bytes(b'\x00\x00\x00\x00', '-')

    def test_octet_string(self):
        s = b'THIS IS A TEST OF THE EMERGENCY BROADCAST SYSTEM. This is only a test.'
        s_len = len(s)
        pad_bytes = (s_len % 4)
        string_packed_bytes = OctetString(s_len, s, b'\x00' * pad_bytes)
        # Length octet plus the string padded to within four bytes should be the same as the self-reported size.
        self.assertEqual(4 + s_len + pad_bytes, string_packed_bytes.size)

        s = s.decode('ascii')

        string_from_str = OctetString.from_string(s)
        # Both init methods should produce the same string -- assuming the padding contents are null.
        self.assertEqual(string_packed_bytes, string_from_str)
        print(string_from_str)

        self.assertEqual(  # roundtrip
            OctetString.from_bytes(string_from_str.to_bytes('!'), '!'),
            string_from_str
        )

    def test_search_range(self):
        oid_start = ObjectIdentifier(4, 2, 0, 0, (1, 1, 1, 0))
        oid_end = ObjectIdentifier(0, 0, 0, 0, ())
        sr1 = SearchRange(oid_start, oid_end)
        sr2 = SearchRange.from_bytes(oid_start.to_bytes('!') + oid_end.to_bytes('!'), '!')
        self.assertEqual(sr1, sr2)
        self.assertEqual(sr1.size, 24)
        print(sr1)

        oid_start = ObjectIdentifier(4, 2, 0, 0, (1, 1, 1, 0))
        oid_end = ObjectIdentifier(4, 2, 0, 0, (2, 2, 2, 0))
        sr1 = SearchRange(oid_start, oid_end)
        sr2 = SearchRange.from_bytes(oid_start.to_bytes('!') + oid_end.to_bytes('!'), '!')
        self.assertEqual(sr1, sr2)
        self.assertEqual(sr1.size, 40)
        print(sr1)

        self.assertEqual(SearchRange.from_bytes(sr1.to_bytes('!'), '!'), sr1)

    def test_value_representation(self):
        vr = ValueRepresentation(type_=constants.ValueType.NULL, reserved=0,
                                 name=ObjectIdentifier(n_subid=7, prefix_=4, include=0, reserved=0,
                                                       subids=(1, 6027, 3, 10, 1, 2, 9)), data=None)
        self.assertEqual(ValueRepresentation.from_bytes(vr.to_bytes('!'), '!'), vr)  # roundtrip

