import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase

# noinspection PyUnresolvedReferences
import tests.mock_tables.dbconnector

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

    def test_getnextpdu_entPhysicalClass(self):
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(12, 0, 0, 0, (1, 3, 6, 1, 2, 1, 47, 1, 1, 1, 1, 5)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)

        value0 = response.values[0]
        self.assertEqual(str(value0.name), str(ObjectIdentifier(12, 0, 1, 0, (1, 3, 6, 1, 2, 1, 47, 1, 1, 1, 1, 5, 1))))
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(value0.data, 3)

    def test_getnextpdu_entPhysicalSerialNum(self):
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(20, 0, 0, 0, (1, 3, 6, 1, 2, 1, 47, 1, 1, 1, 1, 11)),
            )
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)

        value0 = response.values[0]
        self.assertEqual(str(value0.name), str(ObjectIdentifier(12, 0, 1, 0, (1, 3, 6, 1, 2, 1, 47, 1, 1, 1, 1, 11, 1))))
        self.assertEqual(value0.type_, ValueType.OCTET_STRING)
        self.assertEqual(str(value0.data), "SAMPLETESTSN")
