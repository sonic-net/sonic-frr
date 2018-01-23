import os
import sys

# noinspection PyUnresolvedReferences
import tests.mock_tables.dbconnector

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase

from ax_interface import ValueType
from ax_interface.pdu_implementations import GetPDU, GetNextPDU
from ax_interface.encodings import ObjectIdentifier
from ax_interface.constants import PduTypes
from ax_interface.pdu import PDU, PDUHeader
from ax_interface.mib import MIBTable
from sonic_ax_impl.mibs.vendor.cisco import ciscoSwitchQosMIB

class TestQueueCounters(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lut = MIBTable(ciscoSwitchQosMIB.csqIfQosGroupStatsTable)

        # Update MIBs
        for updater in cls.lut.updater_instances:
            updater.reinit_data()
            updater.update_data()

    def test_getQueueCounters(self):
        for counter_id in range(1, 8):
            oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5, 1, 4, 1, 2, 1, 1))
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

    def test_getNextPduForQueueCounter(self):
        oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5, 1, 4, 1, 2, 1, 1))
        expected_oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5, 1, 4, 1, 2, 1, 2))
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET_NEXT, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(str(value0.name), str(expected_oid))
        self.assertEqual(value0.data, 23492723984237432 & 0x00000000ffffffff) # Test integer truncation

    def test_getIngressQueueCounters(self):
        oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5, 1, 4, 1, 1, 1, 1))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.NO_SUCH_INSTANCE)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data, None)

    def test_getMulticastQueueCounters(self):
        oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5, 1, 4, 1, 2, 1, 3))
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)
        print(response)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.NO_SUCH_INSTANCE)
        self.assertEqual(str(value0.name), str(oid))
        self.assertEqual(value0.data, None)

    def test_getSubtreeForQueueCounters(self):
        oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5))
        expected_oid = ObjectIdentifier(8, 0, 0, 0, (1, 3, 6, 1, 4, 1, 9, 9, 580, 1, 5, 5, 1, 4, 1, 2, 1, 1))
        get_pdu = GetNextPDU(
            header=PDUHeader(1, PduTypes.GET_NEXT, 16, 0, 42, 0, 0, 0),
            oids=[oid]
        )

        encoded = get_pdu.encode()
        response = get_pdu.make_response(self.lut)

        value0 = response.values[0]
        self.assertEqual(value0.type_, ValueType.INTEGER)
        self.assertEqual(str(value0.name), str(expected_oid))
        self.assertEqual(value0.data, 1)
