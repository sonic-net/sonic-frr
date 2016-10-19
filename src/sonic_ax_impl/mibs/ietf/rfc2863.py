from enum import Enum, unique

from sonic_ax_impl import mibs
from ax_interface import MIBMeta, MIBUpdater, ValueType, ContextualMIBEntry


@unique
class DbTables32(int, Enum):
    """
    Maps database tables names to SNMP sub-identifiers.
    https://tools.ietf.org/html/rfc2863#section-6

    REDIS_TABLE_NAME = (RFC1213 OID NUMBER)
    """

    # ifInMulticastPkts ::= { ifXEntry 2 }
    SAI_PORT_STAT_IF_IN_MULTICAST_PKTS = 2
    # ifInBroadcastPkts ::= { ifXEntry 3 }
    SAI_PORT_STAT_IF_IN_BROADCAST_PKTS = 3
    # ifOutMulticastPkts ::= { ifXEntry 4 }
    SAI_PORT_STAT_IF_OUT_MULTICAST_PKTS = 4
    # ifOutBroadcastPkts ::= { ifXEntry 5 }
    SAI_PORT_STAT_IF_OUT_BROADCAST_PKTS = 5


@unique
class DbTables64(int, Enum):
    # ifHCInOctets ::= { ifXEntry 6 }
    SAI_PORT_STAT_IF_IN_OCTETS = 6
    # ifHCInUcastPkts ::= { ifXEntry 7 }
    SAI_PORT_STAT_IF_IN_UCAST_PKTS = 7
    # ifHCInMulticastPkts ::= { ifXEntry 8 }
    SAI_PORT_STAT_IF_IN_MULTICAST_PKTS = 8
    # ifHCInBroadcastPkts ::= { ifXEntry 9 }
    SAI_PORT_STAT_IF_IN_BROADCAST_PKTS = 9
    # ifHCOutOctets ::= { ifXEntry 10 }
    SAI_PORT_STAT_IF_OUT_OCTETS = 10
    # ifHCOutUcastPkts ::= { ifXEntry 11 }
    SAI_PORT_STAT_IF_OUT_UCAST_PKTS = 11
    # ifHCOutMulticastPkts ::= { ifXEntry 12 }
    SAI_PORT_STAT_IF_OUT_MULTICAST_PKTS = 12
    # ifHCOutBroadcastPkts ::= { ifXEntry 13 }
    SAI_PORT_STAT_IF_OUT_BROADCAST_PKTS = 13


class InterfaceMIBUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()

        self.db_conn, \
        self.if_name_map, \
        self.if_alias_map, \
        self.if_id_map, \
        self.oid_sai_map, \
        self.oid_name_map = mibs.init_sync_d_interface_tables()

        self.if_counters = {}
        self.update_data()

    def update_data(self):
        """
        Update redis (caches config)
        Pulls the table references for each interface.
        """
        self.if_counters = {
            sai_id: self.db_conn.get_all(mibs.COUNTERS_DB, mibs.counter_table(sai_id), blocking=True)
            for sai_id in self.if_id_map}

    def interface_name(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the interface description (simply the chassis name) for the respective sub_id.
        """
        return self.if_alias_map[self.oid_name_map[sub_id]]

    def interface_alias(self, sub_id):
        """
        ifAlias specific - this is not the "Alias map". This simply returns the SONiC name.
        :param sub_id: The 1-based sub-identifier query.
        :return: The  SONiC name.
        """
        return self.oid_name_map[sub_id]

    def get_counter32(self, sub_id, table_name):
        return self._get_counter(sub_id, table_name, 0x00000000ffffffff)

    def get_counter64(self, sub_id, table_name):
        return self._get_counter(sub_id, table_name, 0xffffffffffffffff)

    def _get_counter(self, sub_id, table_name, mask):
        """
        :param sub_id: The 1-based sub-identifier query.
        :param table_name: the redis table (either IntEnum or string literal) to query.
        :param mask: mask to apply to counter
        :return: the counter for the respective sub_id/table.
        """
        sai_id = self.oid_sai_map[sub_id]
        # Enum.name or table_name = 'name_of_the_table'
        _table_name = bytes(getattr(table_name, 'name', table_name), 'utf-8')
        try:
            counter_value = self.if_counters[sai_id][_table_name]
            # truncate to 32-bit counter (database implements 64-bit counters)
            counter_value = int(counter_value) & mask
            # done!
            return counter_value
        except KeyError as e:
            mibs.logger.warning("SyncD 'COUNTERS_DB' missing attribute '{}'.".format(e))
            return None


class InterfaceMIBObjects(metaclass=MIBMeta, prefix='.1.3.6.1.2.1.31.1'):
    """
    'ifMIBObjects' https://tools.ietf.org/html/rfc2863#section-6
    """
    if_updater = InterfaceMIBUpdater()
    _ifNumber = len(if_updater.if_name_map)

    # OID sub-identifiers are 1-based, while the actual interfaces are zero-based.
    # offset the interface range when registering the OIDs
    if_range = if_updater.oid_sai_map.keys()

    # ifXTable = '1'
    # ifXEntry = '1.1'

    ifName = \
        ContextualMIBEntry('1.1.1', if_range, ValueType.OCTET_STRING, if_updater.interface_name)

    ifInMulticastPkts = \
        ContextualMIBEntry('1.1.2', if_range, ValueType.COUNTER_32, if_updater.get_counter32,
                           DbTables32(2))

    ifInBroadcastPkts = \
        ContextualMIBEntry('1.1.3', if_range, ValueType.COUNTER_32, if_updater.get_counter32,
                           DbTables32(3))

    ifOutMulticastPkts = \
        ContextualMIBEntry('1.1.4', if_range, ValueType.COUNTER_32, if_updater.get_counter32,
                           DbTables32(4))

    ifOutBroadcastPkts = \
        ContextualMIBEntry('1.1.5', if_range, ValueType.COUNTER_32, if_updater.get_counter32,
                           DbTables32(5))

    ifHCInOctets = \
        ContextualMIBEntry('1.1.6', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(6))

    ifHCInUcastPkts = \
        ContextualMIBEntry('1.1.7', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(7))

    ifHCInMulticastPkts = \
        ContextualMIBEntry('1.1.8', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(8))

    ifHCInBroadcastPkts = \
        ContextualMIBEntry('1.1.9', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(9))

    ifHCOutOctets = \
        ContextualMIBEntry('1.1.10', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(10))

    ifHCOutUcastPkts = \
        ContextualMIBEntry('1.1.11', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(11))

    ifHCOutMulticastPkts = \
        ContextualMIBEntry('1.1.12', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(12))

    ifHCOutBroadcastPkts = \
        ContextualMIBEntry('1.1.13', if_range, ValueType.COUNTER_64, if_updater.get_counter64,
                           DbTables64(13))

    """
    ifLinkUpDownTrapEnable  OBJECT-TYPE
        SYNTAX      INTEGER { enabled(1), disabled(2) }
        MAX-ACCESS  read-write
        STATUS      current
        DESCRIPTION
                "Indicates whether linkUp/linkDown traps should be generated
                for this interface.

                By default, this object should have the value enabled(1) for
                interfaces which do not operate on 'top' of any other
                interface (as defined in the ifStackTable), and disabled(2)
                otherwise."
    """  # FIXME: Placeholder (original impl reported 0)
    ifLinkUpDownTrapEnable = ContextualMIBEntry('1.1.14', if_range, ValueType.INTEGER, lambda sub_id: 2)

    # FIXME: Placeholder
    ifHighSpeed = ContextualMIBEntry('1.1.15', if_range, ValueType.GAUGE_32, lambda sub_id: 40000)

    """
    ifPromiscuousMode  OBJECT-TYPE
        SYNTAX      TruthValue
        MAX-ACCESS  read-write
        STATUS      current
        DESCRIPTION
                "This object has a value of false(2) if this interface only
                accepts packets/frames that are addressed to this station.
                This object has a value of true(1) when the station accepts
                all packets/frames transmitted on the media.  The value
                true(1) is only legal on certain types of media.  If legal,
                setting this object to a value of true(1) may require the
                interface to be reset before becoming effective.

                The value of ifPromiscuousMode does not affect the reception
                of broadcast and multicast packets/frames by the interface."
    """  # FIXME: Placeholder
    ifPromiscuousMode = ContextualMIBEntry('1.1.16', if_range, ValueType.INTEGER, lambda sub_id: 1)

    """
    ifConnectorPresent   OBJECT-TYPE
        SYNTAX      TruthValue
        MAX-ACCESS  read-only
        STATUS      current
        DESCRIPTION
                "This object has the value 'true(1)' if the interface
                sublayer has a physical connector and the value 'false(2)'
                otherwise."
    """  # FIXME: Placeholder
    ifConnectorPresent = ContextualMIBEntry('1.1.17', if_range, ValueType.INTEGER, lambda sub_id: 1)

    ifAlias = ContextualMIBEntry('1.1.18', if_range, ValueType.OCTET_STRING, if_updater.interface_alias)

    """
    ifCounterDiscontinuityTime OBJECT-TYPE
    SYNTAX      TimeStamp
    MAX-ACCESS  read-only
    STATUS      current
    DESCRIPTION
            "The value of sysUpTime on the most recent occasion at which
            any one or more of this interface's counters suffered a
            discontinuity.  The relevant counters are the specific
            instances associated with this interface of any Counter32 or
            Counter64 object contained in the ifTable or ifXTable.  If
            no such discontinuities have occurred since the last re-
            initialization of the local management subsystem, then this
            object contains a zero value."
    """  # FIXME: Placeholder
    ifCounterDiscontinuityTime = ContextualMIBEntry('1.1.19', if_range, ValueType.TIME_TICKS, lambda sub_id: 0)
