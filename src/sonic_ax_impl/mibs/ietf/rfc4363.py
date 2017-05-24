import json
from enum import unique, Enum

from sonic_ax_impl import mibs
from ax_interface import MIBMeta, ValueType, MIBUpdater, ContextualMIBEntry, SubtreeMIBEntry
from ax_interface.util import mac_decimals
from bisect import bisect_right

def fdb_vlanmac(fdb):
    return (int(fdb["vlan"]),) + mac_decimals(fdb["mac"])

class FdbUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.db_conn = mibs.init_db()
        self.reinit_data()
        # call our update method once to "seed" data before the "Agent" starts accepting requests.
        self.update_data()

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
            port_oid = ent[b"SAI_FDB_ENTRY_ATTR_PORT_ID"]
            if port_oid.startswith(b"oid:0x"):
                port_oid = port_oid[6:]

            vlanmac = fdb_vlanmac(fdb)
            self.vlanmac_ifindex_map[vlanmac] = mibs.get_index(self.if_id_map[port_oid])
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
