import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from unittest import TestCase

from ax_interface.mib import MIBTable
from ax_interface.pdu import PDU
from sonic_ax_impl.mibs import ieee802_1ab


class TestLLDPMIB(TestCase):
    @classmethod
    def setUpClass(cls):
        class LLDPMIB(ieee802_1ab.LLDPRemTable, ieee802_1ab.LLDPLocPortTable):
            pass

        cls.lut = MIBTable(LLDPMIB)

    def test_subtype(self):
        for entry in range(4, 11):
            mib_entry = self.lut[(1, 0, 8802, 1, 1, 2, 1, 4, 1, 1, entry, 1)]
            ret = mib_entry(sub_id=1)
            self.assertIsNotNone(ret)
            print(ret)

    def test_local_port_identification(self):
        mib_entry = self.lut[(1, 0, 8802, 1, 1, 2, 1, 3, 7, 1, 3, 1)]
        ret = mib_entry(sub_id=1)
        self.assertEquals(ret, b'Ethernet0')
        print(ret)

    def test_lab_breaks(self):
        break1 = b'\x01\x06\x10\x00\x00\x00\x00q\x00\x01\xd1\x02\x00\x01\xd1\x03\x00\x00\x00P\t\x00\x01\x00\x00' \
                 b'\x00\x00\x01\x00\x00\x00\x00\x00\x00"b\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02\x00' \
                 b'\x00\x00\x01\x00\x00\x00\x03\x00\x00\x00\x07\t\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00' \
                 b'\x00"b\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x03\x00' \
                 b'\x00\x00\x08'

        pdu = PDU.decode(break1)
        resp = pdu.make_response(self.lut)
        print(resp)

        break2 = b'\x01\x06\x10\x00\x00\x00\x00\x15\x00\x00\x08\x98\x00\x00\x08\x9a\x00\x00\x00P\t\x00\x01\x00' \
                 b'\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"b\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02' \
                 b'\x00\x00\x00\x01\x00\x00\x00\x04\x00\x00\x00\x01\t\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00' \
                 b'\x00\x00\x00"b\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00' \
                 b'\x04\x00\x00\x00\x02'

        pdu = PDU.decode(break2)
        resp = pdu.make_response(self.lut)
        print(resp)
