from bisect import bisect_right
from sonic_ax_impl import mibs
from sonic_ax_impl.lib import vtysh_helper
from ax_interface import MIBMeta, ValueType, MIBUpdater, SubtreeMIBEntry
from ax_interface.mib import MIBEntry

class BgpSessionUpdater(MIBUpdater):
    def __init__(self):
        super().__init__()
        self.update_data()

    def update_data(self):
        self.session_status_map = {}
        self.session_status_list = []

        try:
            sessions = vtysh_helper.union_bgp_sessions()
        except RuntimeError as e:
            mibs.logger.error("Failed to union bgp sessions: {}.".format(e))
            return

        for nei, ses in sessions.items():
            oid, status = vtysh_helper.bgp_peer_tuple(ses)
            if oid is None: continue
            self.session_status_list.append(oid)
            self.session_status_map[oid] = status

        self.session_status_list.sort()

    def sessionstatus(self, sub_id):
        return self.session_status_map.get(sub_id, None)

    def get_next(self, sub_id):
        right = bisect_right(self.session_status_list, sub_id)
        if right >= len(self.session_status_list):
            return None

        return self.session_status_list[right]


class CiscoBgp4MIB(metaclass=MIBMeta, prefix='.1.3.6.1.4.1.9.9.187'):
    bgpsession_updater = BgpSessionUpdater()

    cbgpPeer2State = SubtreeMIBEntry('1.2.5.1.3', bgpsession_updater, ValueType.INTEGER, bgpsession_updater.sessionstatus)
