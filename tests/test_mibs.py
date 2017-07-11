import os
import sys
from unittest import TestCase

import tests.mock_tables.dbconnector

modules_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(modules_path, 'src'))

from sonic_ax_impl import mibs

class TestGetNextPDU(TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def test_init_sync_d_lag_tables(self):
        db_conn = mibs.init_db()

        lag_name_if_name_map, \
        if_name_lag_name_map, \
        oid_lag_name_map = mibs.init_sync_d_lag_tables(db_conn)

        self.assertTrue(b"PortChannel04" in lag_name_if_name_map)
        self.assertTrue(lag_name_if_name_map[b"PortChannel04"] == [b"Ethernet124"])
        self.assertTrue(b"Ethernet124" in if_name_lag_name_map)
        self.assertTrue(if_name_lag_name_map[b"Ethernet124"] == b"PortChannel04")

        self.assertTrue(b"PortChannel_Temp" in lag_name_if_name_map)
        self.assertTrue(lag_name_if_name_map[b"PortChannel_Temp"] == [])
