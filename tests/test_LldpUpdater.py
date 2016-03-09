#!/usr/bin/env python

__author__ = "Chen Liu<liuchen@microsoft.com>"
__copyright__ = "copyrighted by Microsoft"
__contributors__ = ["Chen Liu"]
__maintainer__ = ["Chen Liu"]
__version__ = "1.0"
__team_email__ = "linuxnetdev@microsoft.com"


'''
This script implements unit tests for LldpUpdater
'''

import sys
import Queue
import unittest
import threading
import pysswsdk.dbconnector as dbconnector

from inspect import getfile, currentframe
from os.path import join, dirname, abspath
from mockredis import mock_strict_redis_client

############ Append the source code directory path of lldpsyncd to system path ##########
curr_dir_path = dirname(abspath(getfile(currentframe())))
upper_dir_path = dirname(curr_dir_path)
acs_src_dir_path = join(upper_dir_path, 'dist-packages/acs')
pyagentx_src_dir_path = join(upper_dir_path, 'dist-packages')
sys.path.append(acs_src_dir_path)
sys.path.append(pyagentx_src_dir_path)
#########################################################################################

import pyagentx
import snmpsubagent

class TestLldpUpdater(unittest.TestCase):
    '''
        Unit tests the LldpUpdater
    '''

    def get_full_path(self, file_name):
        '''
            Get the full path of File %file_name
        '''

        curr_path = dirname(abspath(getfile(currentframe())))
        file_path = join(curr_path, file_name)
        return file_path

    def setup(self, port_name_map_fname='port_name_map', suffix=None):
        '''
            Set up redis databses, snmp subagent and lldp updaters
            The testing scenarios can be changed by setting port_name_map_fname
        '''

        self.setup_dbconnector(port_name_map_fname, suffix)
        self.setup_snmpsubagent()
        self.setup_lldp_locsys_updater()
        self.setup_lldp_remsys_updater()

    def setup_dbconnector(self, file_name, suffix):
        '''
            Set up the DBconnector instance by mocking its redis client
            and load the desired port_name_map
        '''

        self.db_connector = dbconnector.DBConnector()
        ifdb_id = dbconnector.DBConnector.get_dbid(snmpsubagent.MyAgent.IF_DB)
        ifdb_client = mock_strict_redis_client(host=dbconnector.DBConnector.LOCAL_HOST,
                                               port=dbconnector.DBConnector.REDIS_PORT,
                                               db=ifdb_id)
        # load port name map to ifdb_client
        self.load_port_name_map(ifdb_client, file_name, suffix)

        lldpdb_id = dbconnector.DBConnector.get_dbid(snmpsubagent.MyAgent.LLDP_DB)
        lldpdb_client =  mock_strict_redis_client(host=dbconnector.DBConnector.LOCAL_HOST,
                                                  port=dbconnector.DBConnector.REDIS_PORT,
                                                  db=lldpdb_id)
        self.load_lldp_info(lldpdb_client)

        self.db_connector.redis_client = {snmpsubagent.MyAgent.IF_DB: ifdb_client,
                                          snmpsubagent.MyAgent.LLDP_DB: lldpdb_client}

    def setup_snmpsubagent(self):
        '''
            Initialize SNMP subagent
        '''

        snmpsubagent.MyAgent.db_connector = self.db_connector
        snmpsubagent.MyAgent.get_port_name_map(snmpsubagent.MyAgent.IF_DB)
        snmpsubagent.MyAgent.get_reverse_map()
        snmpsubagent.MyAgent.init_util_retriever(snmpsubagent.MyAgent.ACS_HW_SKU)

    def setup_lldp_locsys_updater(self):
        '''
            Initialize an lldp local system updater instance for testing
            only call the update function once
        '''

        queue = Queue.Queue(maxsize=20)
        child_abnormal_event = threading.Event()
        self.lldp_locsys_updater = snmpsubagent.LldpLocSysUpdater()
        self.lldp_locsys_updater.agent_setup(queue,
                                             snmpsubagent.MyAgent.oid.lldpRemTable,
                                             snmpsubagent.MyAgent.update_frequency)
        self.lldp_locsys_updater.add_child_abnormal_event(child_abnormal_event)

        try:
            self.lldp_locsys_updater.update()
        except Exception:
            raise

    def setup_lldp_remsys_updater(self):
        '''
            Initialize an lldp remote system updater instance for testing
            only call the update function once
        '''

        queue = Queue.Queue(maxsize=20)
        child_abnormal_event = threading.Event()
        self.lldp_remsys_updater = snmpsubagent.LldpRemSysUpdater()
        self.lldp_remsys_updater.agent_setup(queue,
                                             snmpsubagent.MyAgent.oid.lldpRemTable,
                                             snmpsubagent.MyAgent.update_frequency)
        self.lldp_remsys_updater.add_child_abnormal_event(child_abnormal_event)

        try:
            self.lldp_remsys_updater.update()
        except Exception:
            raise

    def load_port_name_map(self, client, file_name, suffix=None, table_name='port_name_map'):
        '''
            Upload the desired port_name_map to the mock redis
            The test scenario is determined by file_name
        '''

        self.sai_ids = []
        file_name = self.get_file_name(file_name, suffix)
        file_path = self.get_full_path(file_name)
        with open(file_path, 'r') as f:
            for line in f:
                (key, val) = line.strip().split(', ')
                self.sai_ids.append(val)
                client.hset(table_name, key, val)


    def load_lldp_info(self, client, suffix=None):
        '''
            Initialize lldp information in the mock redis
        '''

        for if_sid in self.sai_ids:
            file_name = self.get_file_name('lldp_'+if_sid, suffix)
            file_path = self.get_full_path(file_name)
            with open(file_path, 'r') as f:
                for line in f:
                    (key, val) = line.strip().split(', ')
                    client.hset(if_sid, key, val)

    def get_file_name(self, prefix, suffix=None):
        '''
            Compose the file name for a test case
            The suffix argument indicates of the test scenario
            When suffix is none, we use the positive scenario file
        '''

        if suffix is None:
            return prefix + '.txt'
        else:
            return prefix + '_' + suffix + '.txt'

    def compare_value(self, updater, oid, val):   
        '''
            Check whether the value set for a counter - identified by oid 
            matches its expected value-val
        '''

        flag = True
        my_oid = oid
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            my_oid = oid + '.' + str(if_index)
            my_val = updater._data[my_oid]['value']
            if my_val != val:
                self.assertFalse('Value of %s is wrongly set for interface %s', (my_oid, if_name))
                flag = False
                break
        return flag

    def compare_range(self, updater, oid, min=None, max=None):
        '''
            Check whether the value for a counter - identified by oid
            is within (min, max)
        '''

        flag = True
        my_oid = oid
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            my_oid = oid + '.' + str(if_index)
            val = updater._data[my_oid]['value']
            if min and max is None and val < min:
                self.assertFalse('Value for oid %s is less than %s for interface %s', (my_oid, min, if_name))
                flag = False
                break
            if min is None and max and val > max:
                self.assertFalse('Value for oid %s is greater than %s for interface %s', (my_oid, max, if_name))
                flag = False
                break
            if min and max and (val < min or val > max):
                self.assertFalse('Value for oid %s is not within (%s, %s) for interface %s', (my_oid, min, max, if_name))
                flag = False
                break
            if min is None and max is None:
                raise Exception('Error: compare_range, no min and max values are specified!')
        return flag

    def compare_type(self, updater, oid, type):
        '''
            Check whether the type specified for a counter - identified by oid
            matches its desired ifmib type
        '''

        flag = True
        my_oid = oid
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            my_oid = oid + '.' + str(if_index)
            my_type = updater._data[my_oid]['type']
            if my_type != type:
                self.assertFalse('Type for oid %s is wrongly set', my_oid)
                flag = False
                break
        return flag

    def test_lldpLocPortId(self):
        '''
            Test whether the type of lldplocportid is set as desired
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpLocPortId
        self.assertTrue(self.compare_type(self.lldp_locsys_updater, oid, pyagentx.TYPE_OCTETSTRING))

    def test_lldpLocPortId_value(self):
        '''
            Test whether the type of lldplocportid is set as desired
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpLocPortId
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            my_oid = oid + '.' + str(if_index)
            val = self.lldp_locsys_updater._data[my_oid]['value']
            self.assertEqual(val, if_name)

    def test_lldpRemPortIdSubtype(self):
        '''
            Test whether the type of lldpremsysportidsubtype is set as desired
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpRemPortIdSubtype
        self.assertTrue(self.compare_type(self.lldp_remsys_updater, oid, pyagentx.TYPE_INTEGER))

    def test_lldpRemPortIdSubtype_value(self):
        '''
            Test whether the value of lldpremsysportidsubtype is within the expected range
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpRemPortIdSubtype
        self.assertTrue(self.compare_range(self.lldp_remsys_updater, oid, 1, 7))

    def test_lldpRemPortId(self):
        '''
            Test whether the type of lldpremportid is set as desired
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpRemPortId
        self.assertTrue(self.compare_type(self.lldp_remsys_updater, oid, pyagentx.TYPE_OCTETSTRING))

    def test_lldpRemPortDesc(self):
        '''
            Test whether the type of lldpremsysportdesc is set as desired
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpRemPortDesc
        self.assertTrue(self.compare_type(self.lldp_remsys_updater, oid, pyagentx.TYPE_OCTETSTRING))

    def test_lldpRemSysName(self):
        '''
            Test whether the type of lldpremsysname is set as desired
        '''

        self.setup(port_name_map_fname='port_name_map_short')
        oid = snmpsubagent.MyAgent.oid.lldpRemSysName
        self.assertTrue(self.compare_type(self.lldp_remsys_updater, oid, pyagentx.TYPE_OCTETSTRING))

if __name__ == "__main__":
     unittest.main()


