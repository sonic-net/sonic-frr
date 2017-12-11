import os
import sys
import ipaddress

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase

import tests.mock_tables.dbconnector

from ax_interface.mib import MIBTable
from ax_interface.pdu import PDUHeader
from ax_interface.pdu_implementations import GetPDU, GetNextPDU
from ax_interface import ValueType
from ax_interface.encodings import ObjectIdentifier
from ax_interface.constants import PduTypes
from sonic_ax_impl.mibs.ietf import rfc4363
from sonic_ax_impl.main import SonicMIB

class TestForwardMIB(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lut = MIBTable(SonicMIB)

    def test_update(self):
        for updater in self.lut.updater_instances:
            updater.update_data()
            updater.reinit_data()
            updater.update_data()

    def test_network_order(self):
        ip = ipaddress.ip_address("0.1.2.3")
        ipb = ip.packed
        ips = ".".join(str(int(x)) for x in list(ipb))
        self.assertEqual(ips, "0.1.2.3")

    def test_getnextpdu_first(self):
        # oid.include = 1
        oid = ObjectIdentifier(10, 0, 1, 0, (1, 3, 6, 1, 2, 1, 4, 24, 4, 1))
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        # self.assertEqual(n, 7)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.IP_ADDRESS)
        self.assertEqual(str(value0.name), '.1.3.6.1.2.1.4.24.4.1.1.0.0.0.0.0.0.0.0.0.10.0.0.1')
        self.assertEqual(str(value0.data), ipaddress.ip_address("0.0.0.0").packed.decode())

    def test_getpdu(self):
        oid = ObjectIdentifier(24, 0, 1, 0, (1, 3, 6, 1, 2, 1, 4, 24, 4, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 15))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.IP_ADDRESS)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(str(value0.data), ipaddress.ip_address("0.0.0.0").packed.decode())

    def test_getnextpdu(self):
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(21, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 24, 4, 1, 1, 0)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.IP_ADDRESS)
        self.assertEqual(str(value0.data), ipaddress.ip_address("0.0.0.0").packed.decode())

    def test_getnextpdu_exactmatch(self):
        oid = ObjectIdentifier(24, 0, 1, 0, (1, 3, 6, 1, 2, 1, 4, 24, 4, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 17))
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.IP_ADDRESS)
        print("test_getnextpdu_exactmatch: ", str(oid))
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(str(value0.data), ipaddress.ip_address("0.0.0.0").packed.decode())

    def test_getpdu_noinstance(self):
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 24, 4, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.NO_SUCH_INSTANCE)

    def test_getnextpdu_empty(self):
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(12, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 24, 4, 1, 1, 1)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.END_OF_MIB_VIEW)

