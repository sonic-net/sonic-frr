import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase
from unittest.mock import patch, mock_open

from ax_interface.mib import MIBTable
from ax_interface.pdu import PDUHeader
from ax_interface.pdu_implementations import GetPDU, GetNextPDU
from ax_interface import ValueType
from ax_interface.encodings import ObjectIdentifier
from ax_interface.constants import PduTypes
from sonic_ax_impl.mibs.ietf import rfc4363
from sonic_ax_impl.main import SonicMIB
from sonic_ax_impl.lib.vtysh_helper import parse_bgp_summary

class TestSonicMIB(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lut = MIBTable(SonicMIB)
        for updater in cls.lut.updater_instances:
            updater.update_data()

    def test_getpdu_established(self):
        oid = ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 187, 1, 2, 5, 1, 3, 1, 4, 10, 0, 0, 61))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data, 6)

    def test_getpdu_idle(self):
        oid = ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 187, 1, 2, 5, 1, 3, 1, 4, 10, 0, 0, 65))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data, 1)

    def test_getpdu_active(self):
        oid = ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 187, 1, 2, 5, 1, 3, 2, 16, 252, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data, 3)

    def test_getpdu_disappeared(self):
        oid = ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 187, 1, 2, 5, 1, 3, 2, 16, 252, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x10))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.NO_SUCH_INSTANCE)

    def test_getpdu_ipv4_overwite_ipv6(self):
        oid = ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 187, 1, 2, 5, 1, 3, 2, 16, 252, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x72))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data, 6)

    def parse_no_bgp():
        filename = 'bgpsummary_ipv6_nobgp.txt'
        with open(filename, 'rb') as f:
            bgpsu = f.read()
        bgpsumm_ipv6 = parse_bgp_summary(bgpsu)
        self.assertEqual(bgpsumm_ipv6, [])