from enum import Enum, unique

AGENTX_SOCKET_PATH = '/var/agentx/master'

# https://tools.ietf.org/html/rfc2741#section-6.1 -- PDU Header definition
# Headers are fixed at 20 bytes.
AGENTX_HEADER_LENGTH = 20

# https://tools.ietf.org/html/rfc2741#section-6.2.9
# The smallest possible PDU is header only.
AGENTX_MINIMUM_PDU_SIZE = AGENTX_HEADER_LENGTH

# from http://net-snmp.sourceforge.net/dev/agent/snmp__api_8h_source.html
# 00122 #define SNMP_MAX_MSG_SIZE          1472 /* ethernet MTU minus IP/UDP header */
SNMP_MAX_MSG_SIZE = 1472

# 1.3.6.1
INTERNET_PREFIX = (1, 3, 6, 1)

# From https://tools.ietf.org/html/rfc2741#section-5::
#
#    Fields marked "<reserved>" are reserved for future use and must be
#    zero-filled.
RESERVED_ZERO_BYTE = b'\x00'

# Subagent description string (used in some messages in Net-SNMP)
SNMP_SUBAGENT_NAME = "Software for Open Networking in the Cloud (SONiC) -- SNMP sub-agent"

# How often PDU processing counts are emitted in logs. Debug only.
REPORTING_FREQUENCY = 1000


@unique
class ValueType(int, Enum):
    """
    Value Representation enumerated types as found in Section 5.4:
    https://tools.ietf.org/html/rfc2741#section-5.4
    """

    INTEGER = 2
    OCTET_STRING = 4
    NULL = 5
    OBJECT_IDENTIFIER = 6  # unique category
    IP_ADDRESS = 64
    COUNTER_32 = 65
    GAUGE_32 = 66
    TIME_TICKS = 67
    OPAQUE = 68
    COUNTER_64 = 70  # unique category
    NO_SUCH_OBJECT = 128
    NO_SUCH_INSTANCE = 129
    END_OF_MIB_VIEW = 130
    # Thirteen total with two unique types.


@unique
class PduTypes(int, Enum):
    """
    PDU enumerated types as found in (https://www.ietf.org/rfc/rfc2741.txt) Section 6.2:

    _The set of PDU types for "administrative processing" are 1-4
    and 12-17.  The set of PDU types for "SNMP request
    processing" are 5-11._

    """
    # "administrative processing"
    EMPTY = 0
    OPEN = 1
    CLOSE = 2
    REGISTER = 3
    UNREGISTER = 4
    # "SNMP request processing"
    GET = 5
    GET_NEXT = 6
    GET_BULK = 7
    TEST_SET = 8
    COMMIT_SET = 9
    UNDO_SET = 10
    CLEANUP_SET = 11
    # "administrative processing"
    NOTIFY = 12
    PING = 13
    INDEX_ALLOCATE = 14
    INDEX_DEALLOCATE = 15
    ADD_AGENT_CAPS = 16
    REMOVE_AGENT_CAPS = 17
    # Response is a unique type
    RESPONSE = 18


DEFAULT_PDU_TIMEOUT = 5
