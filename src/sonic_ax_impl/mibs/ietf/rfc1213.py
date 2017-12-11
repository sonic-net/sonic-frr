import ipaddress
import python_arptable
from enum import unique, Enum
from bisect import bisect_right

from sonic_ax_impl import mibs
from ax_interface import MIBMeta, ValueType, MIBUpdater, MIBEntry, SubtreeMIBEntry
from ax_interface.encodings import ObjectIdentifier
from ax_interface.util import mac_decimals, ip2tuple_v4


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

class ArpUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.arp_dest_map = {}
        self.arp_dest_list = []
        self.arp_dest_map = {}
        self.arp_dest_list = []

    def update_data(self):
        self.arp_dest_map = {}
        self.arp_dest_list = []
        for entry in python_arptable.get_arp_table():
            dev = entry['Device']
            mac = entry['HW address']
            ip = entry['IP address']

            if_index = mibs.get_index_from_str(dev)
            if if_index is None: continue

            mactuple = mac_decimals(mac)
            machex = ''.join(chr(b) for b in mactuple)
            # if MAC is all zero
            #if not any(mac): continue

            iptuple = ip2tuple_v4(ip)

            subid = (if_index,) + iptuple
            self.arp_dest_map[subid] = machex
            self.arp_dest_list.append(subid)
        self.arp_dest_list.sort()

    def arp_dest(self, sub_id):
        return self.arp_dest_map.get(sub_id, None)

    def get_next(self, sub_id):
        right = bisect_right(self.arp_dest_list, sub_id)
        if right >= len(self.arp_dest_list):
            return None
        return self.arp_dest_list[right]

class NextHopUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.db_conn = mibs.init_db()
        self.nexthop_map = {}
        self.route_list = []

    def update_data(self):
        """
        Update redis (caches config)
        Pulls the table references for each interface.
        """
        self.nexthop_map = {}
        self.route_list = []

        self.db_conn.connect(mibs.APPL_DB)
        route_entries = self.db_conn.keys(mibs.APPL_DB, "ROUTE_TABLE:*")
        if not route_entries:
            return

        for route_entry in route_entries:
            routestr = route_entry.decode()
            ipnstr = routestr[len("ROUTE_TABLE:"):]
            if ipnstr == "0.0.0.0/0":
                ipn = ipaddress.ip_network(ipnstr)
                ent = self.db_conn.get_all(mibs.APPL_DB, routestr, blocking=True)
                nexthops = ent[b"nexthop"].decode()
                for nh in nexthops.split(','):
                    # TODO: if ipn contains IP range, create more sub_id here
                    sub_id = ip2tuple_v4(ipn.network_address)
                    self.route_list.append(sub_id)
                    self.nexthop_map[sub_id] = ipaddress.ip_address(nh).packed
                    break # Just need the first nexthop

        self.route_list.sort()

    def nexthop(self, sub_id):
        return self.nexthop_map.get(sub_id, None)

    def get_next(self, sub_id):
        right = bisect_right(self.route_list, sub_id)
        if right >= len(self.route_list):
            return None

        return self.route_list[right]

class IpMib(metaclass=MIBMeta, prefix='.1.3.6.1.2.1.4'):
    arp_updater = ArpUpdater()
    nexthop_updater = NextHopUpdater()

    ipRouteNextHop = \
        SubtreeMIBEntry('21.1.7', nexthop_updater, ValueType.IP_ADDRESS, nexthop_updater.nexthop)

    ipNetToMediaPhysAddress = \
        SubtreeMIBEntry('22.1.2', arp_updater, ValueType.OCTET_STRING, arp_updater.arp_dest)

class InterfacesUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.db_conn = mibs.init_db()

        self.lag_name_if_name_map = {}
        self.if_name_lag_name_map = {}
        self.oid_lag_name_map = {}

        # cache of interface counters
        self.if_counters = {}
        self.if_range = []
        self.if_name_map = {}
        self.if_alias_map = {}
        self.if_id_map = {}
        self.oid_sai_map = {}
        self.oid_name_map = {}

    def reinit_data(self):
        """
        Subclass update interface information
        """
        self.if_name_map, \
        self.if_alias_map, \
        self.if_id_map, \
        self.oid_sai_map, \
        self.oid_name_map = mibs.init_sync_d_interface_tables(self.db_conn)

    def update_data(self):
        """
        Update redis (caches config)
        Pulls the table references for each interface.
        """
        self.if_counters = \
            {sai_id: self.db_conn.get_all(mibs.COUNTERS_DB, mibs.counter_table(sai_id), blocking=True)
             for sai_id in self.if_id_map}

        self.lag_name_if_name_map, \
        self.if_name_lag_name_map, \
        self.oid_lag_name_map = mibs.init_sync_d_lag_tables(self.db_conn)

        self.if_range = sorted(list(self.oid_sai_map.keys()) + list(self.oid_lag_name_map.keys()))
        self.if_range = [(i,) for i in self.if_range]

    def get_next(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the next sub id.
        """
        right = bisect_right(self.if_range, sub_id)
        if right == len(self.if_range):
            return None
        return self.if_range[right]

    def get_oid(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the interface OID.
        """
        if sub_id not in self.if_range:
            return

        return sub_id[0]

    def if_index(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the 0-based interface ID.
        """
        if sub_id:
            return self.get_oid(sub_id) - 1

    def interface_description(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the interface description (simply the name) for the respective sub_id
        """
        oid = self.get_oid(sub_id)
        if not oid:
            return

        if oid in self.oid_lag_name_map:
            return self.oid_lag_name_map[oid]

        return self.if_alias_map[self.oid_name_map[oid]]

    def _get_counter(self, oid, table_name):
        """
        :param sub_id: The interface OID.
        :param table_name: the redis table (either IntEnum or string literal) to query.
        :return: the counter for the respective sub_id/table.
        """
        sai_id = self.oid_sai_map[oid]
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

    def get_counter(self, sub_id, table_name):
        """
        :param sub_id: The 1-based sub-identifier query.
        :param table_name: the redis table (either IntEnum or string literal) to query.
        :return: the counter for the respective sub_id/table.
        """
        oid = self.get_oid(sub_id)
        if not oid:
            return

        if oid in self.oid_lag_name_map:
            counter_value = 0
            for lag_member in self.lag_name_if_name_map[self.oid_lag_name_map[oid]]:
                counter_value += self._get_counter(mibs.get_index(lag_member), table_name)

            # truncate to 32-bit counter
            return counter_value & 0x00000000ffffffff
        else:
            return self._get_counter(oid, table_name)

    def get_if_number(self):
        """
        :return: the number of interfaces.
        """
        return len(self.if_range)

    def _get_if_entry(self, sub_id):
        """
        :param oid: The 1-based sub-identifier query.
        :return: the DB entry for the respective sub_id.
        """
        oid = self.get_oid(sub_id)
        if not oid:
            return

        table = ""
        if oid in self.oid_lag_name_map:
            table = mibs.lag_entry_table(self.oid_lag_name_map[oid])
        else:
            table = mibs.if_entry_table(self.oid_name_map[oid])

        return self.db_conn.get_all(mibs.APPL_DB, table, blocking=True)

    def _get_status(self, sub_id, key):
        """
        :param sub_id: The 1-based sub-identifier query.
        :param key: Status to get (admin_state or oper_state).
        :return: state value for the respective sub_id/key.
        """
        status_map = {
            b"up": 1,
            b"down": 2
        }

        entry = self._get_if_entry(sub_id)
        if not entry:
            return

        # Note: If interface never become up its state won't be reflected in DB entry
        # If state is not in DB entry assume interface is down
        state = entry.get(key, b"down")

        return status_map.get(state, status_map[b"down"])

    def get_admin_status(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: admin state value for the respective sub_id.
        """
        return self._get_status(sub_id, b"admin_status")

    def get_oper_status(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: oper state value for the respective sub_id.
        """
        return self._get_status(sub_id, b"oper_status")

    def get_mtu(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: MTU value for the respective sub_id.
        """
        entry = self._get_if_entry(sub_id)
        if not entry:
            return

        return int(entry.get(b"mtu", 0))


class InterfacesMIB(metaclass=MIBMeta, prefix='.1.3.6.1.2.1.2'):
    """
    'interfaces' https://tools.ietf.org/html/rfc1213#section-3.5
    """

    if_updater = InterfacesUpdater()

    # (subtree, value_type, callable_, *args, handler=None)
    ifNumber = MIBEntry('1', ValueType.INTEGER, if_updater.get_if_number)

    # ifTable ::= { interfaces 2 }
    # ifEntry ::= { ifTable 1 }

    ifIndex = \
        SubtreeMIBEntry('2.1.1', if_updater, ValueType.INTEGER, if_updater.if_index)

    ifDescr = \
        SubtreeMIBEntry('2.1.2', if_updater, ValueType.OCTET_STRING, if_updater.interface_description)

    # FIXME: Placeholder
    # ethernetCsmacd(6), -- for all ethernet-like interfaces,
    #                    -- regardless of speed, as per RFC3635
    ifType = \
        SubtreeMIBEntry('2.1.3', if_updater, ValueType.INTEGER, lambda sub_id: 6)

    ifMtu = \
        SubtreeMIBEntry('2.1.4', if_updater, ValueType.INTEGER, if_updater.get_mtu)

    # FIXME Placeholder.
    #   "If the bandwidth of the interface is greater
    #   than the maximum value reportable by this object,
    #   then this object should report its maximum value
    #   (4.294,967,295) and ifHighSpeed must be used to
    #   report the interface's speed."
    ifSpeed = \
        SubtreeMIBEntry('2.1.5', if_updater, ValueType.GAUGE_32, lambda sub_id: 4294967295)

    # FIXME Placeholder.
    ifPhysAddress = \
        SubtreeMIBEntry('2.1.6', if_updater, ValueType.OCTET_STRING, lambda sub_id: '')

    ifAdminStatus = \
        SubtreeMIBEntry('2.1.7', if_updater, ValueType.INTEGER, if_updater.get_admin_status)

    ifOperStatus = \
        SubtreeMIBEntry('2.1.8', if_updater, ValueType.INTEGER, if_updater.get_oper_status)

    # FIXME Placeholder.
    ifLastChange = \
        SubtreeMIBEntry('2.1.9', if_updater, ValueType.TIME_TICKS, lambda sub_id: 0)

    ifInOctets = \
        SubtreeMIBEntry('2.1.10', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(10))

    ifInUcastPkts = \
        SubtreeMIBEntry('2.1.11', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(11))

    ifInNUcastPkts = \
        SubtreeMIBEntry('2.1.12', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(12))

    ifInDiscards = \
        SubtreeMIBEntry('2.1.13', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(13))

    ifInErrors = \
        SubtreeMIBEntry('2.1.14', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(14))

    ifInUnknownProtos = \
        SubtreeMIBEntry('2.1.15', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(15))

    ifOutOctets = \
        SubtreeMIBEntry('2.1.16', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(16))

    ifOutUcastPkts = \
        SubtreeMIBEntry('2.1.17', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(17))

    ifOutNUcastPkts = \
        SubtreeMIBEntry('2.1.18', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(18))

    ifOutDiscards = \
        SubtreeMIBEntry('2.1.19', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(19))

    ifOutErrors = \
        SubtreeMIBEntry('2.1.20', if_updater, ValueType.COUNTER_32, if_updater.get_counter,
                           DbTables(20))

    ifOutQLen = \
        SubtreeMIBEntry('2.1.21', if_updater, ValueType.GAUGE_32, if_updater.get_counter,
                           DbTables(21))

    # FIXME Placeholder
    ifSpecific = \
        SubtreeMIBEntry('2.1.22', if_updater, ValueType.OBJECT_IDENTIFIER, lambda sub_id: ObjectIdentifier.null_oid())
