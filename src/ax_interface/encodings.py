"""
'AgentX Encodings' as described in https://tools.ietf.org/html/rfc2741#section-5
"""

import struct
from collections import namedtuple

from . import constants, util


class ObjectIdentifier(
    namedtuple('_ObjectIdentifier', ('n_subid', 'prefix_', 'include', 'reserved', 'subids'))
):
    """
    From https://tools.ietf.org/html/rfc2741#section-5.1:

    An object identifier is encoded as a 4-byte header, followed by a
    variable number of contiguous 4-byte fields representing sub-
    identifiers.
    """
    __slots__ = ()

    @property
    def prefix(self):
        """
        An unsigned value used to reduce the length of object
        identifier encodings.  A non-zero value "x" is interpreted as
        the first sub-identifier after "internet" (1.3.6.1), and
        indicates an implicit prefix "internet.x" to the actual sub-
        identifiers encoded in the Object Identifier.  For example, a
        prefix field value 2 indicates an implicit prefix "1.3.6.1.2".
        A value of 0 in the prefix field indicates there is no prefix
        to the sub-identifiers.
        """
        if not self.prefix_:
            return ()
        else:
            return constants.INTERNET_PREFIX + (self.prefix_,)

    def __str__(self):
        subid_strs = [str(subid) for subid in self.to_tuple()]
        return '.' + '.'.join(subid_strs) if subid_strs else ''

    @property
    def size(self):
        return 4 + 4 * self.n_subid

    def to_tuple(self):
        return self.prefix + self.subids

    def to_bytes(self, endianness):
        format_string = endianness + 'BBBB' + str(len(self.subids)) + 'L'
        return struct.pack(format_string, self.n_subid, self.prefix_, self.include, self.reserved, *self.subids)

    def inc(self):
        """
        Returns a new object identifier with last subid increased by one
        """
        newsubids = self.subids[:-1] + (self.subids[-1] + 1,)
        return self._replace(subids = newsubids)

    @classmethod
    def null_oid(cls):
        return cls(0, 0, 0, 0, ())

    @classmethod
    def from_iterable(cls, subids):
        prefix = 0
        if tuple(subids[:4]) == constants.INTERNET_PREFIX:
            prefix = subids[4]
            subids = subids[5:]
        return cls(len(subids), prefix, 0, 0, subids)

    @classmethod
    def from_bytes(cls, byte_string, endianness):
        """
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |  n_subid      |  prefix       |    include    |  <reserved>   |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             subidentifier #1                                  |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        ...                                                             |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |             subidentifier #n_subid                            |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

        :param byte_string: string to unpack
        :param endianness: '!' or '<' (big/little endian)
        :return: n-oids, does not modify the original buffer and the index following the end of the OID
        """
        oid_attributes = (n_subid, prefix, _, reserved) = struct.unpack(endianness + 'BBBB', byte_string[:4])
        start_offset = 4
        end_offset = start_offset + n_subid * 4
        subids = struct.unpack(endianness + n_subid * 'L', byte_string[start_offset:end_offset])

        # oid = (n_subid, prefix, _, reserved, (subid1, subid2, ...))
        return cls(*oid_attributes, subids)


class SearchRange(namedtuple('_SearchRange', ('start', 'end'))):
    """
    From https://tools.ietf.org/html/rfc2741#section-5.2:

    A SearchRange consists of two Object Identifiers.  In its
    communication with a subagent, the master agent uses a SearchRange to
    identify a requested variable binding, and, in GetNext and GetBulk
    operations, to set an upper bound on the names of managed object
    instances the subagent may send in reply.
    """
    __slots__ = ()

    def __str__(self):
        end_str = str(self.end)
        ret = str(self.start)
        ret += ' --> ' + str(self.end) if end_str else ' (unbounded)'
        return ret

    @property
    def size(self):
        return self.start.size + self.end.size

    def to_bytes(self, endianness):
        return self.start.to_bytes(endianness) + self.end.to_bytes(endianness)

    @classmethod
    def from_bytes(cls, byte_string, endianness):
        # unpack the first OID
        start = ObjectIdentifier.from_bytes(byte_string, endianness)
        # unpack the second OID (resume at the end of the first)
        end = ObjectIdentifier.from_bytes(byte_string[start.size:], endianness)
        # compose our SearchRange tuple
        return cls(start, end)


class OctetString(namedtuple('_OctetString', ('length', 'string', 'padding'))):
    """
    https://tools.ietf.org/html/rfc2741#section-5.3
    """
    __slots__ = ()

    @property
    def size(self):
        return 4 + self.length + util.pad4(self.length)

    def __str__(self):
        return self.string.decode('ascii')

    @classmethod
    def from_string(cls, string):
        length = len(string)
        _string = bytes(string, 'ascii') if type(string) is str else string
        return cls(length, _string, util.pad4bytes(len(_string)))

    def to_bytes(self, endianness):
        fmt = endianness + 'L{}s{}s'.format(self.length, util.pad4(self.length))
        return struct.pack(fmt, self.length, self.string, self.padding)

    @classmethod
    def from_bytes(cls, byte_string, endianness):
        """
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                     Octet String Length (L)                   |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |  Octet 1      |  Octet 2      |   Octet 3     |   Octet 4     |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |  Octet L - 1  |  Octet L      |       Padding (as required)   |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

        :param byte_string: string to unpack.
        :param endianness: '!' or '<' (big/little endian)
        :return: octet string tuple, new offset. does not modify the original buffer.
        """
        # read the length string
        string_length_bytes = byte_string[:4]
        # look ahead to the length value
        string_length = struct.unpack(endianness + 'L', string_length_bytes)[0]
        # strings are padded to 4 bytes.
        padding_length = util.pad4(string_length)

        # E.g. !L101s3s -> (length[long], string, padding[string])
        fmt = '{}L{}s{}s'.format(endianness, string_length, padding_length)
        # calculate offset
        size = struct.calcsize(fmt)
        # format the context string
        return cls(*struct.unpack(fmt, byte_string[:size]))


class ValueRepresentation(namedtuple('_ValueRepresentation', ('type_', 'reserved', 'name', 'data'))):
    """
    https://tools.ietf.org/html/rfc2741#section-5.4

    Variable bindings may be encoded within the variable-length portion
    of some PDUs.  The representation of a variable binding (termed a
    VarBind) consists of a 2-byte type field, a name (Object Identifier),
    and the actual value data.
    """
    __slots__ = ()

    FOUR_BYTE_TYPES = [
        constants.ValueType.INTEGER,
        constants.ValueType.COUNTER_32,
        constants.ValueType.GAUGE_32,
        constants.ValueType.TIME_TICKS,
        # Four total
    ]

    OCTET_STRINGS = [
        constants.ValueType.IP_ADDRESS,
        constants.ValueType.OPAQUE,
        constants.ValueType.OCTET_STRING,
        # Three total
    ]

    EMPTY_TYPES = [
        constants.ValueType.NULL,
        constants.ValueType.NO_SUCH_OBJECT,
        constants.ValueType.NO_SUCH_INSTANCE,
        constants.ValueType.END_OF_MIB_VIEW,
        # Four total
    ]

    # 2 + 4 + 3 + 4 = 13. All types accounted for.

    @property
    def size(self):
        size = 4 + self.name.size
        typed_bind = constants.ValueType(self.type_)
        if typed_bind in self.FOUR_BYTE_TYPES:
            size += 4
        elif typed_bind == constants.ValueType.COUNTER_64:
            size += 8
        elif typed_bind == constants.ValueType.OBJECT_IDENTIFIER or typed_bind in self.OCTET_STRINGS:
            size += self.data.size
        elif typed_bind in self.EMPTY_TYPES:
            # _size += 0
            pass
        return size

    @classmethod
    def from_typecast(cls, type_, oid_iter_or_obj, data):
        oid = ObjectIdentifier.from_iterable(oid_iter_or_obj) \
            if type(oid_iter_or_obj) is not ObjectIdentifier else oid_iter_or_obj
        if type_ == constants.ValueType.OCTET_STRING:
            _data = OctetString.from_string(data)
        elif type_ == constants.ValueType.OBJECT_IDENTIFIER:
            _data = ObjectIdentifier.from_iterable(data) if type(data) is not ObjectIdentifier else data
        elif type_ in cls.EMPTY_TYPES:
            _data = None
        else:
            _data = data

        return cls(type_, 0, oid, _data)

    @classmethod
    def _unpack_data(cls, type_, byte_string, endianness):
        """
        -  Integer, Counter32, Gauge32, and TimeTicks are encoded as 4
        contiguous bytes, according to the header's
        NETWORK_BYTE_ORDER bit.

        -  Counter64 is encoded as 8 contiguous bytes, according to
        the header's NETWORK_BYTE_ORDER bit.

        -  Object Identifiers are encoded as described in section 5.1,
        Object Identifier.

        -  IpAddress, Opaque, and Octet String are all octet strings
        and are encoded as described in section 5.3, "Octet
        String", Octet String.  Note that the octets used to
        represent IpAddress are always ordered most significant to
        least significant.

        Value data always follows v.name whenever v.type is one of
        the above types.  These data bytes are present even if they
        will not be used (as, for example, in certain types of
        index allocation).

        -  Null, noSuchObject, noSuchInstance, and endOfMibView do not
        contain any encoded value.  Value data never follows v.name
        in these cases.

        :param type_: type integer
        :param byte_string:  byte stream
        """
        typed_bind = constants.ValueType(type_)
        if typed_bind in cls.FOUR_BYTE_TYPES:
            data = struct.unpack(endianness + 'L', byte_string[:4])[0]
            size = 4
        elif typed_bind == constants.ValueType.COUNTER_64:
            data = struct.unpack(endianness + 'Q', byte_string[:8])[0]
            size = 8
        elif typed_bind == constants.ValueType.OBJECT_IDENTIFIER:
            data = ObjectIdentifier.from_bytes(byte_string, endianness)
            size = data.size
        elif typed_bind in cls.OCTET_STRINGS:
            data = OctetString.from_bytes(byte_string, endianness)
            size = data.size
        elif typed_bind in cls.EMPTY_TYPES:
            data = None
            size = 0
        else:
            raise ValueError("Unknown bound type.")

        return data, size

    def to_bytes(self, endianness):
        fmt = endianness + 'HH'
        byte_string = struct.pack(fmt, self.type_, self.reserved)
        byte_string += self.name.to_bytes(endianness)

        typed_bind = constants.ValueType(self.type_)
        if typed_bind in self.FOUR_BYTE_TYPES:
            byte_string += struct.pack(endianness + 'L', self.data)
        elif typed_bind == constants.ValueType.COUNTER_64:
            byte_string += struct.pack(endianness + 'Q', self.data)
        elif typed_bind == constants.ValueType.OBJECT_IDENTIFIER or typed_bind in self.OCTET_STRINGS:
            byte_string += self.data.to_bytes(endianness)
        elif typed_bind in self.EMPTY_TYPES:
            # ret += b''
            pass
        return byte_string

    @classmethod
    def from_bytes(cls, byte_string, endianness):
        """
        VarBind

        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |          v.type               |          <reserved>           |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

        (v.name)
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |  n_subid      |  prefix       |      0        |       0       |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                       sub-identifier #1                       |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                       sub-identifier #n_subid                 |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

        (v.data)
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                       data                                    |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                       data                                    |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

        :param byte_string: Stream of bytes from which to unpack the VR
        :param endianness: big/little endian format specifier.
        :return: an instance of ValueRepresentation.
        """
        type_, reserved = struct.unpack(endianness + 'HH', byte_string[:4])
        name = ObjectIdentifier.from_bytes(byte_string[4:], endianness)
        offset = 4 + name.size
        data, offset = cls._unpack_data(type_, byte_string[offset:], endianness)
        vr = cls(constants.ValueType(type_), reserved, name, data)
        return vr
