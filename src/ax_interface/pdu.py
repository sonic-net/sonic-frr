"""
PDU object implementation per https://www.ietf.org/rfc/rfc2741.txt
"""

import struct
from collections import namedtuple

from . import constants, logger, exceptions
from .constants import PduTypes
from .encodings import OctetString

supported_pdus = {}
_ignored_pdus = {}
"""
Listing of supported PDUs. Self-populating. See PDU.__metaclass__
"""


class PDUHeaderTags(namedtuple('_PDUHeaderTags', ('version', 'type_', 'flags', 'reserved'))):
    """
    https://tools.ietf.org/html/rfc2741#section-6.1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |   h.version   |    h.type     |    h.flags    |  <reserved>   |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    __slots__ = ()

    MASK_INSTANCE_REGISTRATION = 0x01
    MASK_NEW_INDEX = 0x02
    MASK_ANY_INDEX = 0x04
    MASK_NON_DEFAULT_CONTEXT = 0x08
    MASK_NEWORK_BYTE_ORDER = 0x10

    @property
    def flag__instance_registration(self):
        """
        The INSTANCE_REGISTRATION bit is used only within the agentx-Register-PDU.
        """
        return bool(self.flags & PDUHeaderTags.MASK_INSTANCE_REGISTRATION)

    @property
    def flag__new_index(self):
        """
        The NEW_INDEX and ANY_INDEX bits are used only within the agentx-IndexAllocate-, and -IndexDeallocate-PDUs.
        """
        return bool(self.flags & PDUHeaderTags.MASK_NEW_INDEX)

    @property
    def flag__any_index(self):
        """
        The NEW_INDEX and ANY_INDEX bits are used only within the agentx-IndexAllocate-, and -IndexDeallocate-PDUs.
        """
        return bool(self.flags & PDUHeaderTags.MASK_ANY_INDEX)

    @property
    def flag__non_default_context(self):
        """
        If the NON_DEFAULT_CONTEXT bit in the AgentX header field h.flags is clear, then there is no context field in
        the PDU, and the operation refers to the default context.  (This does not mean there is a zero-length Octet
        String, it means there is no Octet String present.) If the NON_DEFAULT_CONTEXT bit is set, then a context field
        immediately follows the AgentX header, and the operation refers to that specific context.  The context is
        represented as an Octet String. There are no constraints on its length or contents.
        """
        return bool(self.flags & PDUHeaderTags.MASK_NON_DEFAULT_CONTEXT)

    @property
    def flag__network_byte_order(self):
        """
        The NETWORK_BYTE_ORDER bit applies to all AgentX PDUs.
        """
        return bool(self.flags & PDUHeaderTags.MASK_NEWORK_BYTE_ORDER)

    @property
    def endianness(self):
        """
        '<' little-endian
        '!' Network-byte-order (big-endian)
        https://docs.python.org/3.5/library/struct.html#format-strings

         From the RFC:
         The NETWORK_BYTE_ORDER bit applies to all multi-byte integer
         values in the entire AgentX packet, including the remaining
         header fields.  If set, then network byte order (most
         significant byte first; "big endian") is used.  If not set,
         then least significant byte first ("little endian") is used.
        """
        return '!' if self.flag__network_byte_order else '<'

    @classmethod
    def from_bytes(cls, byte_string):
        return cls(*struct.unpack('!BBBB', byte_string[:4]))


PDUIdentifiers = namedtuple('PDUIdentifiers', ('session_id', 'transaction_id', 'packet_id', 'payload_length'))


class PDUHeader(namedtuple('_PDUHeader', PDUHeaderTags._fields + PDUIdentifiers._fields), PDUHeaderTags):
    """
    The AgentX PDU header is a fixed-format, 20-octet structure:

       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |   h.version   |    h.type     |    h.flags    |  <reserved>   |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                          h.sessionID                          |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                        h.transactionID                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                          h.packetID                           |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                        h.payload_length                       |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    __slots__ = ()

    def to_bytes(self):
        ret = struct.pack('!BBBB', self.version, self.type_, self.flags, self.reserved)
        fmt = self.endianness + 'LLLL'
        ret += struct.pack(fmt, self.session_id, self.transaction_id, self.packet_id, self.payload_length)
        return ret

    @classmethod
    def from_bytes(cls, byte_string):
        pdu_info = PDUHeaderTags.from_bytes(byte_string)
        """
        Four remaining longs makeup the identifiers. Combine the two based on parsed flags.

        The NETWORK_BYTE_ORDER bit applies to all multi-byte integer
        values in the entire AgentX packet, including the remaining
        header fields.
        """
        try:
            header = cls(
                *pdu_info,
                *PDUIdentifiers(
                    *struct.unpack(pdu_info.endianness + '4L', byte_string[4:constants.AGENTX_HEADER_LENGTH])
                )
            )
            return header
        except struct.error as e:
            raise exceptions.PDUUnpackError("Failed to unpack PDUHeader", inner_exception=e)


class RegisteredPDU(type):
    def __new__(mcs, name, bases, attributes):
        cls = type.__new__(mcs, name, bases, attributes)
        try:
            # Test against PDU enum class

            supported_pdus.update({PduTypes(cls.header_type_): cls})
        except ValueError:
            # h_type wasn't included in our enumeration --> not a valid PDU type
            logger.debug("Ignoring PDU instance '{}' -- invalid PDU 'header_type_' field. "
                         "No RFC-compliant PDU types should emit this error!".format(name))
            _ignored_pdus.update({name: cls})
        return cls


class PDUStream:
    """
    Contiguous PDU bytestream constructor.
    """

    def __init__(self, data):
        self.data = data

    def __iter__(self):
        _data = self.data
        while _data:
            pdu = PDU.decode(_data)
            yield pdu
            _data = pdu._trailing_bytes


class PDU(object, metaclass=RegisteredPDU):
    header_type_ = -1
    """
    type_ is used as a hint to the class factory method regarding what PDU class to instantiate. Subclasses
    override this value with the PDU type described in https://tools.ietf.org/html/rfc2741#section-6.1. Valid values
    range from 1-18, inclusive. h_type attributes outside this range will be ignored.
    """

    def __new__(cls, *args, **kwargs):
        if cls in (PDU, ContextOptionalPDU):
            raise TypeError("Abstract classes may not be instantiated.")
        return object.__new__(cls)

    def __init__(self, header, payload=None, **kwargs):
        if (kwargs and payload is not None) or payload is None and any(arg is None for arg in kwargs.values()):
            raise ValueError("Payload and PDU fields are mutually exclusive.")

        self.header = header._replace(type_=self.header_type_)
        self._trailing_bytes = payload or b''

    def __str__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    @staticmethod
    def decode(byte_string):
        if len(byte_string) < constants.AGENTX_MINIMUM_PDU_SIZE:
            # if we can't even unpack a header, we can't continue.
            raise exceptions.PDUUnpackError("Minimum PDU size is [{}], received [{}] bytes.".format(
                constants.AGENTX_MINIMUM_PDU_SIZE,
                len(byte_string)
            ))

        # Parse the header to infer the type.
        header = PDUHeader.from_bytes(byte_string)

        # based on the type field, find the appropriate class and instantiate it.
        try:
            return supported_pdus[header.type_](
                payload=byte_string[constants.AGENTX_HEADER_LENGTH:],
                header=header)
        except KeyError:
            raise exceptions.UnsupportedPDUError("PDU Type [{}] is not supported".format(header.type_))
        except (struct.error, ValueError) as e:
            raise exceptions.PDUUnpackError("Failed to unpack PDU.", inner_exception=e)

    def encode(self):
        try:
            return self.header.to_bytes()
        except (struct.error, ValueError) as e:
            raise exceptions.PDUPackError("Failed to pack PDU.", inner_exception=e)

    def make_response(self, lut):
        raise NotImplementedError("Child PDUs must create response objects.")

    @property
    def payload_length(self):
        return len(self.encode()) - constants.AGENTX_HEADER_LENGTH


class ContextOptionalPDU(PDU):
    """
    An optional context field may be present in the agentx-Register-,
    UnRegister-, AddAgentCaps-, RemoveAgentCaps-, Get-, GetNext-,
    GetBulk-, IndexAllocate-, IndexDeallocate-, Notify-, TestSet-, and
    Ping- PDUs.
    """

    def __init__(self, header, context=None, payload=None):
        super().__init__(header=header, payload=payload)
        self.context = context
        if self.header.flag__non_default_context:
            # Optional context is present, process it.
            self.context = OctetString.from_bytes(self._trailing_bytes, self.header.endianness)
            # chomp the context block from unprocessed bytes
            self._trailing_bytes = self._trailing_bytes[self.context.size:]

    def encode(self):
        ret = super().encode()
        if self.context is not None:
            ret += self.context.to_bytes(self.header.endianness)
        return ret


# noinspection PyUnresolvedReferences
from . import pdu_implementations
