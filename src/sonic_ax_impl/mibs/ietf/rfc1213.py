from enum import unique, Enum

from sonic_ax_impl import mibs
from ax_interface import MIBMeta, ValueType, MIBUpdater, MIBEntry, ContextualMIBEntry
from ax_interface.encodings import ObjectIdentifier


@unique
class DbTables(int, Enum):
    """
    Maps database tables names to SNMP sub-identifiers.
    https://tools.ietf.org/html/rfc1213#section-6.4

    REDIS_TABLE_NAME = (RFC1213 OID NUMBER)
    """

    # ifOperStatus ::= { ifEntry 8 }
    # ifLastChange :: { ifEntry 9 }
    # ifInOctets ::= { ifEntry 10 }
    SAI_PORT_STAT_IF_IN_OCTETS = 10
    # ifInUcastPkts ::= { ifEntry 11 }
    SAI_PORT_STAT_IF_IN_UCAST_PKTS = 11
    # ifInNUcastPkts ::= { ifEntry 12 }
    SAI_PORT_STAT_IF_IN_NON_UCAST_PKTS = 12
    # ifInDiscards ::= { ifEntry 13 }
    SAI_PORT_STAT_IF_IN_DISCARDS = 13
    # ifInErrors ::= { ifEntry 14 }
    SAI_PORT_STAT_IF_IN_ERRORS = 14
    # ifInUnknownProtos ::= { ifEntry 15 }
    SAI_PORT_STAT_IF_IN_UNKNOWN_PROTOS = 15
    # ifOutOctets  ::= { ifEntry 16 }
    SAI_PORT_STAT_IF_OUT_OCTETS = 16
    # ifOutUcastPkts ::= { ifEntry 17 }
    SAI_PORT_STAT_IF_OUT_UCAST_PKTS = 17
    # ifOutNUcastPkts ::= { ifEntry 18 }
    SAI_PORT_STAT_IF_OUT_NON_UCAST_PKTS = 18
    # ifOutDiscards ::= { ifEntry 19 }
    SAI_PORT_STAT_IF_OUT_DISCARDS = 19
    # ifOutErrors ::= { ifEntry 20 }
    SAI_PORT_STAT_IF_OUT_ERRORS = 20
    # ifOutQLen ::= { ifEntry 21 }
    SAI_PORT_STAT_IF_OUT_QLEN = 21


class InterfacesUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.db_conn, \
        self.if_name_map, \
        self.if_alias_map, \
        self.if_id_map, \
        self.oid_sai_map, \
        self.oid_name_map = mibs.init_sync_d_interface_tables()
        # cache of interface counters
        self.if_counters = {}
        # call our update method once to "seed" data before the "Agent" starts accepting requests.
        self.update_data()

    def update_data(self):
        """
        Update redis (caches config)
        Pulls the table references for each interface.
        """
        self.if_counters = \
            {sai_id: self.db_conn.get_all(mibs.COUNTERS_DB, mibs.counter_table(sai_id), blocking=True)
             for sai_id in self.if_id_map}

    def interface_description(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the interface description (simply the name) for the respective sub_id
        """
        return self.if_alias_map[self.oid_name_map[sub_id]]

    def get_counter(self, sub_id, table_name):
        """
        :param sub_id: The 1-based sub-identifier query.
        :param table_name: the redis table (either IntEnum or string literal) to query.
        :return: the counter for the respective sub_id/table.
        """

        sai_id = self.oid_sai_map[sub_id]
        # Enum.name or table_name = 'name_of_the_table'
        _table_name = bytes(getattr(table_name, 'name', table_name), 'utf-8')

        try:
            counter_value = self.if_counters[sai_id][_table_name]
            # truncate to 32-bit counter (database implements 64-bit counters)
            counter_value = int(counter_value) & 0x00000000ffffffff
            # done!
            return counter_value
        except KeyError as e:
            mibs.logger.warning("SyncD 'COUNTERS_DB' missing attribute '{}'.".format(e))
            return None


class InterfacesMIB(metaclass=MIBMeta, prefix='.1.3.6.1.2.1.2'):
    """
    'interfaces' https://tools.ietf.org/html/rfc1213#section-3.5
    """

    if_updater = InterfacesUpdater()
    _ifNumber = len(if_updater.if_name_map)

    # OID sub-identifiers are 1-based, while the actual interfaces are zero-based.
    # offset the interface range when registering the OIDs
    if_range = if_updater.oid_sai_map.keys()

    # (subtree, value_type, callable_, *args, handler=None)
    ifNumber = MIBEntry('1', ValueType.INTEGER, lambda: InterfacesMIB._ifNumber)

    # ifTable ::= { interfaces 2 }
    # ifEntry ::= { ifTable 1 }

    ifIndex = \
        ContextualMIBEntry('2.1.1', if_range, ValueType.INTEGER, lambda sub_id: sub_id - 1)

    ifDescr = \
        ContextualMIBEntry('2.1.2', if_range, ValueType.OCTET_STRING, if_updater.interface_description)

    # FIXME: Placeholder
    # ethernetCsmacd(6), -- for all ethernet-like interfaces,
    #                    -- regardless of speed, as per RFC3635
    ifType = \
        ContextualMIBEntry('2.1.3', if_range, ValueType.INTEGER, lambda sub_id: 6)

    # FIXME Placeholder. ACS switches only use the MTU value of 9196
    ifMtu = \
        ContextualMIBEntry('2.1.4', if_range, ValueType.INTEGER, lambda sub_id: 9196)

    # FIXME Placeholder.
    #   "If the bandwidth of the interface is greater
    #   than the maximum value reportable by this object,
    #   then this object should report its maximum value
    #   (4.294,967,295) and ifHighSpeed must be used to
    #   report the interface's speed."
    ifSpeed = \
        ContextualMIBEntry('2.1.5', if_range, ValueType.GAUGE_32, lambda sub_id: 4294967295)

    # FIXME Placeholder.
    ifPhysAddress = \
        ContextualMIBEntry('2.1.6', if_range, ValueType.OCTET_STRING, lambda sub_id: '')

    # FIXME Placeholder. 1 -- up; 2 -- down; 3 -- testing
    ifAdminStatus = \
        ContextualMIBEntry('2.1.7', if_range, ValueType.INTEGER, lambda sub_id: 1)

    # FIXME Placeholder. 1 -- up; 2 -- down; 3 -- testing
    ifOperStatus = \
        ContextualMIBEntry('2.1.8', if_range, ValueType.INTEGER, lambda sub_id: 1)

    # FIXME Placeholder.
    ifLastChange = \
        ContextualMIBEntry('2.1.9', if_range, ValueType.TIME_TICKS, lambda sub_id: 0)

    ifInOctets = \
        ContextualMIBEntry('2.1.10', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(10))

    ifInUcastPkts = \
        ContextualMIBEntry('2.1.11', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(11))

    ifInNUcastPkts = \
        ContextualMIBEntry('2.1.12', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(12))

    ifInDiscards = \
        ContextualMIBEntry('2.1.13', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(13))

    ifInErrors = \
        ContextualMIBEntry('2.1.14', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(14))

    ifInUnknownProtos = \
        ContextualMIBEntry('2.1.15', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(15))

    ifOutOctets = \
        ContextualMIBEntry('2.1.16', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(16))

    ifOutUcastPkts = \
        ContextualMIBEntry('2.1.17', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(17))

    ifOutNUcastPkts = \
        ContextualMIBEntry('2.1.18', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(18))

    ifOutDiscards = \
        ContextualMIBEntry('2.1.19', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(19))

    ifOutErrors = \
        ContextualMIBEntry('2.1.20', if_range, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(20))

    ifOutQLen = \
        ContextualMIBEntry('2.1.21', if_range, ValueType.GAUGE_32, if_updater.get_counter,
                           DbTables(21))

    # FIXME Placeholder
    ifSpecific = \
        ContextualMIBEntry('2.1.22', if_range, ValueType.OBJECT_IDENTIFIER, lambda sub_id: ObjectIdentifier.null_oid())
