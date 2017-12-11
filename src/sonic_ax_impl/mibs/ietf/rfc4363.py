import json
from enum import unique, Enum

from sonic_ax_impl import mibs
from swsssdk import port_util
from ax_interface import MIBMeta, ValueType, MIBUpdater, SubtreeMIBEntry
from ax_interface.util import mac_decimals
from bisect import bisect_right

def fdb_vlanmac(fdb):
    return (int(fdb["vlan"]),) + mac_decimals(fdb["mac"])

class FdbUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.db_conn = mibs.init_db()

        self.prev_if_id_map = {}
        self.if_name_map = {}
        self.if_alias_map = {}
        self.if_id_map = {}
        self.oid_sai_map = {}
        self.oid_name_map = {}
        self.vlanmac_ifindex_map = {}
        self.vlanmac_ifindex_list = []
        self.if_bpid_map = {}

    def reinit_data(self):
        """
        Subclass update interface information
        """
        self.if_name_map, \
        self.if_alias_map, \
        self.if_id_map, \
        self.oid_sai_map, \
        self.oid_name_map = mibs.init_sync_d_interface_tables(self.db_conn)

        ## Note: if if_id_map update, invalid_port_oids should be initialized to empty set
        if self.prev_if_id_map != self.if_id_map:
            self.prev_if_id_map = self.if_id_map
            self.invalid_port_oids = set()

        self.if_bpid_map = port_util.get_bridge_port_map(self.db_conn)


    def update_data(self):
        """
        Update redis (caches config)
        Pulls the table references for each interface.
        """
        self.db_conn.connect(mibs.ASIC_DB)
        self.vlanmac_ifindex_map = {}
        self.vlanmac_ifindex_list = []

        fdb_strings = self.db_conn.keys(mibs.ASIC_DB, "ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:*")
        if not fdb_strings:
            return

        for s in fdb_strings:
            fdb_str = s.decode()
            try:
                fdb = json.loads(fdb_str.split(":", maxsplit=2)[-1])
            except ValueError as e:  # includes simplejson.decoder.JSONDecodeError
                mibs.logger.error("SyncD 'ASIC_DB' includes invalid FDB_ENTRY '{}': {}.".format(fdb_str, e))
                break

            ent = self.db_conn.get_all(mibs.ASIC_DB, s, blocking=True)
            # Example output: oid:0x3a000000000608
            bridge_port_id = ent[b"SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID"][6:]
            if bridge_port_id not in self.if_bpid_map:
                continue
            port_id = self.if_bpid_map[bridge_port_id]

            vlanmac = fdb_vlanmac(fdb)
            self.vlanmac_ifindex_map[vlanmac] = mibs.get_index(self.if_id_map[port_id])
            self.vlanmac_ifindex_list.append(vlanmac)
        self.vlanmac_ifindex_list.sort()

    def fdb_ifindex(self, sub_id):
        return self.vlanmac_ifindex_map.get(sub_id, None)

    def get_next(self, sub_id):
        right = bisect_right(self.vlanmac_ifindex_list, sub_id)
        if right >= len(self.vlanmac_ifindex_list):
            return None

        return self.vlanmac_ifindex_list[right]

class QBridgeMIBObjects(metaclass=MIBMeta, prefix='.1.3.6.1.2.1.17.7.1'):
    """
    'Forwarding Database' https://tools.ietf.org/html/rfc4363
    """

    fdb_updater = FdbUpdater()

    dot1qTpFdbPort = \
        SubtreeMIBEntry('2.2.1.2', fdb_updater, ValueType.INTEGER, fdb_updater.fdb_ifindex)
