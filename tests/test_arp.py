import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase
from unittest.mock import patch, mock_open

# noinspection PyUnresolvedReferences
import tests.mock_tables.dbconnector
import tests.mock_tables.python_arptable
from ax_interface.mib import MIBTable
from ax_interface.pdu import PDUHeader
from ax_interface.pdu_implementations import GetPDU, GetNextPDU
from ax_interface import ValueType
from ax_interface.encodings import ObjectIdentifier
from ax_interface.constants import PduTypes
from sonic_ax_impl.mibs.ietf import rfc4363
from sonic_ax_impl.main import SonicMIB

class TestSonicMIB(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lut = MIBTable(SonicMIB)
        for updater in cls.lut.updater_instances:
            updater.update_data()
            updater.reinit_data()
            updater.update_data()

    # TODO: this test fails, possible reason maybe mock arptable
    # def test_update(self):
        # for updater in self.lut.updater_instances:
            # updater.update_data()
            # updater.reinit_data()
            # updater.update_data()

    def test_getpdu(self):
        oid = ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 22, 1, 2, 37, 10, 0, 0, 19))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.OCTET_STRING)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data.string, b'\x52\x54\x00\x04\x52\x5d')

    def test_getnextpdu(self):
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 22, 1, 2, 37, 10, 0, 0, 19)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.OCTET_STRING)
        self.assertEqual(value0.data.string, b'\x52\x54\x00\xd0\xa0\x8c')

    def test_getnextpdu_exactmatch(self):
        # oid.include = 1
        oid = ObjectIdentifier(20, 0, 1, 0, (1, 3, 6, 1, 2, 1, 4, 22, 1, 2, 37, 10, 0, 0, 19))
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.OCTET_STRING)
        print("test_getnextpdu_exactmatch: ", str(oid))
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data.string, b'\x52\x54\x00\x04\x52\x5d')

    def test_getpdu_noinstance(self):
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 22, 1, 2, 39)),
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
                ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 2, 1, 4, 22, 1, 3)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        n = len(response.values)
        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.END_OF_MIB_VIEW)

