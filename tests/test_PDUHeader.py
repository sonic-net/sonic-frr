import os
import sys

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

import struct
import pprint
from unittest import TestCase
from ax_interface.pdu import PDU, PDUHeader, PDUHeaderTags, supported_pdus, ContextOptionalPDU, _ignored_pdus, PDUStream
from ax_interface.pdu_implementations import OpenPDU, ResponsePDU, RegisterPDU, GetPDU
from ax_interface import exceptions
from ax_interface.encodings import ObjectIdentifier
from ax_interface.constants import PduTypes
from ax_interface.mib import MIBTable
from sonic_ax_impl.mibs.vendor.dell import force10


class TestPDUHeader(TestCase):
    def test_endianness(self):
        """
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |    h.version   |    h.type     |    h.flags    |  <reserved>   |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        """

        one = 1
        one_little_endian = one.to_bytes(4, 'little')
        one_big_endian = one.to_bytes(4, 'big')

        # flag unset
        pdu_little_endian = PDUHeader.from_bytes(b'\x00\x00\x00\x00' + one_little_endian * 4)
        self.assertEqual(pdu_little_endian.session_id, 1)
        self.assertEqual(pdu_little_endian.transaction_id, 1)
        self.assertEqual(pdu_little_endian.packet_id, 1)
        self.assertEqual(pdu_little_endian.payload_length, 1)
        print(pdu_little_endian)

        nbo_set = struct.pack('!BBBB', 0, 0, 0 | PDUHeaderTags.MASK_NEWORK_BYTE_ORDER, 0)

        # network byte flag set
        pdu_big_endian = PDUHeader.from_bytes(nbo_set + one_big_endian * 4)
        self.assertEqual(pdu_big_endian.session_id, 1)
        self.assertEqual(pdu_big_endian.transaction_id, 1)
        self.assertEqual(pdu_big_endian.packet_id, 1)
        self.assertEqual(pdu_big_endian.payload_length, 1)
        print(pdu_big_endian)

    def test_bad_unpack(self):
        with self.assertRaises(exceptions.PDUUnpackError):
            # missing IDs
            PDUHeader.from_bytes(b'\x00\x00\x00\x00')

        with self.assertRaises(exceptions.PDUUnpackError):
            # missing payload length
            PDUHeader.from_bytes(b'\x00\x00\x00\x00' * 3)


class TestPDU(TestCase):
    def test_PDU_autodiscover(self):
        self.assertTrue(supported_pdus, msg="No PDU implementations found.")
        self.assertTrue(all(issubclass(inst, PDU) for inst in supported_pdus.values()))
        self.assertIn(PDU, _ignored_pdus.values())
        self.assertNotIn(PDU, supported_pdus.values())
        self.assertIn(ContextOptionalPDU, _ignored_pdus.values())
        self.assertNotIn(ContextOptionalPDU, supported_pdus.values())
        pprint.pprint(supported_pdus)

    def test_factory(self):
        with self.assertRaises(exceptions.UnsupportedPDUError):
            # type 0
            PDU.decode(b'\x00\x00\x00\x00' * 5)

        with self.assertRaises(exceptions.UnsupportedPDUError):
            # type 19
            PDU.decode(b'\x00\x13\x00\x00' * 5)

        with self.assertRaisesRegex(TypeError, r'Abstract'):
            # Abstract -- not allowed.
            PDU(None)

        with self.assertRaisesRegex(TypeError, r'Abstract'):
            # Abstract -- not allowed.
            ContextOptionalPDU(None)


class TestOpenPDU(TestCase):
    def test_roundtrip(self):
        open_pdu = OpenPDU(
            header=PDUHeader(1, 1, 16, 0, 0, 0, 0, 0),
            timeout=42,
            oid=ObjectIdentifier(4, 2, 0, 0, (1, 1, 1, 0)),
            descr="HOWDY-HO, NEIGHBOR!"
        )

        encoded = open_pdu.encode()
        decoded = PDU.decode(encoded)

        self.assertEqual(decoded.header.type_, PduTypes.OPEN)
        self.assertIsInstance(open_pdu, OpenPDU)
        self.assertEqual(open_pdu, decoded)
        print(open_pdu)


class TestResponsePDU(TestCase):
    def test_OpenPDU_response(self):
        resp = b'\x01\x12\x10\x00\x00\x00\x00\x0e\x00\x00\x00\x00\x00\x00\x00\x00' \
               b'\x00\x00\x00@\x00\x02h\x8b\x00\x00\x00\x00\x00\x04\x00\x00\x02\x00' \
               b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00$Azure Cloud ' \
               b'Switch -- SNMP sub-agent'
        resp1 = PDU.decode(resp)
        resp2 = PDU.decode(resp1.encode())
        self.assertEqual(resp1, resp2)

    def test_roundtrip(self):
        response_pdu = ResponsePDU(
            header=PDUHeader(1, 18, 16, 0, 42, 0, 0, 8),
            sys_up_time=0,
            error=0,
            index=0,
        )

        encoded = response_pdu.encode()
        decoded = PDU.decode(encoded)

        self.assertEqual(decoded.header.type_, PduTypes.RESPONSE)
        self.assertIsInstance(response_pdu, ResponsePDU)
        self.assertEqual(response_pdu, decoded)
        print(response_pdu)


class TestRegisterPDU(TestCase):
    def test_roundtrip(self):
        """
        1.3.6.1.2.1.2.2.1.[1-22].7

        index 10
        6,2,2,0,(1,2,2,1,1,7)
        upper bound 22

        :return:
        """
        register = RegisterPDU(
            header=PDUHeader(1, PduTypes.REGISTER, 16, 0, 42, 0, 0, 0),
            timeout=40,
            priority=50,
            range_subid=6,
            subtree=ObjectIdentifier(4, 2, 0, 0, (1, 1, 1, 0)),
            upper_bound=7
        )

        encoded = register.encode()
        decoded = PDU.decode(encoded)

        self.assertEqual(decoded.header.type_, PduTypes.REGISTER)
        self.assertIsInstance(register, RegisterPDU)
        self.assertEqual(register, decoded)
        print(register)

    def test_register_response(self):
        resp = b'\x01\x12\x10\x00\x00\x00\x00"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00,\x00\x0eL\xb5\x01\x07\x00' \
               b'\x00\x00\x05\x00\x00\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n' \
               b'\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t'

        pdu = PDU.decode(resp)
        self.assertEqual(PDU.decode(pdu.encode()), pdu)

    def test_register_prep(self):
        reg = b'\x01\x03\x10\x00\x00\x00\x00\x1e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00$\x05\x00\x00\x00\x07\x04' \
              b'\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00' \
              b'\x02\x00\x00\x00\t'
        pdu = PDU.decode(reg)
        self.assertEqual(PDU.decode(pdu.encode()), pdu)

    def test_register_interfaces(self):
        """
        Incoming bytes may contain /multiple/ consecutive PDUs!
        \x01\x12 marks the beginning of a new response PDU, below contains two.
        """
        resp = b'\x01\x12\x10\x00\x00\x00\x00M\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00,\x01\xcdL{\x00\x00\x00\x00' \
               b'\x00\x05\x00\x00\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00' \
               b'\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t\x01\x12\x10\x00\x00\x00\x00M\x00\x00\x00\x00\x00\x00' \
               b'\x00\x00\x00\x00\x00\x18\x01\xcdL|\x00\x00\x00\x00\x00\x05\x00\x00\x02\x02\x00\x00\x00\x00\x00' \
               b'\x01\x00\x00\x00\x02'
        ps = PDUStream(resp)
        for pdu in ps:
            print(pdu)

    def test_truncated_stream(self):
        """
        Incoming bytes may contain /multiple/ consecutive PDUs!
        \x01\x12 marks the beginning of a new response PDU, below contains two.
        """
        resp = b'\x01\x12\x10\x00\x00\x00\x00M\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00,\x01\xcdL{\x00\x00\x00\x00' \
               b'\x00\x05\x00\x00\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00' \
               b'\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t\x01\x12\x10\x00\x00\x00\x00M\x00\x00\x00\x00\x00\x00' \
               b'\x00\x00\x00\x00\x00\x18\x01\xcdL|\x00\x00\x00\x00\x00\x05\x00\x00\x02\x02\x00\x00\x00\x00\x00' \
               # b'\x01\x00\x00\x00\x02'
        ps = PDUStream(resp)

        try:
            for pdu in ps:
                print(pdu)
        except exceptions.PDUUnpackError:
            self.failIf('pdu' not in locals())

    def test_openPDU_stream(self):
        resp = b'\x01\x12\x10\x00\x00\x00\x00\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00`\x00\x00\x00\xfe\x00\x00\x00\x00\x00\x04\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00CSoftware for Open Networking in the Cloud (SONiC) -- SNMP sub-agent\x00'
        ps = PDUStream(resp)
        try:
            for pdu in ps:
                print(pdu)
        except exceptions.PDUUnpackError:
            self.failIf('pdu' not in locals())


class TestGetPDU(TestCase):
    def test_roundtrip(self):
        get_pdu = GetPDU(
            header=PDUHeader(1, PduTypes.GET, 16, 0, 42, 0, 0, 0),
            oids=(
                ObjectIdentifier(4, 2, 0, 0, (1, 1, 1, 0)),
                ObjectIdentifier(4, 2, 0, 0, (2, 2, 2, 0)),
            )
        )

        encoded = get_pdu.encode()
        decoded = PDU.decode(encoded)

        self.assertEqual(decoded.header.type_, PduTypes.GET)
        self.assertIsInstance(get_pdu, GetPDU)
        self.assertEqual(get_pdu, decoded)
        print(get_pdu)


class TestGetNextPDU(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lut = MIBTable(force10.SSeriesMIB)

    def test_make_response(self):
        # start of .2.9
        # get_bytes = b'\x01\x06\x10\x00\x00\x00\x00\x0b\x00\x00\x00\x8e\x00\x00\x00\x8f\x00\x00\x00@\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\n'
        # end of mib
        get_bytes = b'\x01\x06\x10\x00\x00\x00\x00\x0f\x00\x00\x01\x11\x00\x00\x01\x12\x00\x00\x00H\t\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t\x00\x00\x00\x01\x00\x00\x00\x05\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\n'
        #  snmpwalk -c strcommunity -v2c 10.3.147.172 .1.3.6.1.4.1.6027.3.10.1.2.9.5
        get_bytes = b'\x01\x06\x10\x00\x00\x00\x00\x1d\x00\x00\x03\xbc\x00\x00\x03\xbd\x00\x00\x00D\x08\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t\x00\x00\x00\x05\x07\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\n'
        get_bytes2 = b'\x01\x05\x10\x00\x00\x00\x00\x1d\x00\x00\x03\xbe\x00\x00\x03\xbf\x00\x00\x00(\x08\x04\x00\x00\x00\x00\x00\x01\x00\x00\x17\x8b\x00\x00\x00\x03\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\t\x00\x00\x00\x05\x00\x00\x00\x00'

        get_pdu = PDU.decode(get_bytes)
        get_pdu.make_response(self.lut)
