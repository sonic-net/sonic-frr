#!/usr/bin/env python

__author__ = "Chen Liu<liuchen@microsoft.com>"
__copyright__ = "copyrighted by Microsoft"
__contributors__ = ["Chen Liu"]
__maintainer__ = ["Chen Liu"]
__version__ = "1.0"
__team_email__ = "linuxnetdev@microsoft.com"


'''
This script implements unit tests for InterfaceUpdater
'''

import sys
import Queue
import unittest
import threading

from inspect import getfile, currentframe
from os.path import join, dirname, abspath
from mockredis import mock_strict_redis_client

import pysswsdk.dbconnector as dbconnector
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

class TestInterfaceUpdater(unittest.TestCase):
    '''
        Unit tests for InterfaceUpdater
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
            Set up redis databses.
            The testing scenarios can be changed by setting port_name_map_fname
        '''

        self.setup_dbconnector(port_name_map_fname, suffix)
        self.setup_snmpsubagent()
        self.setup_interfaceupdater()

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
        self.load_interfaces(ifdb_client, suffix)

        lldpdb_id = dbconnector.DBConnector.get_dbid(snmpsubagent.MyAgent.LLDP_DB)
        lldpdb_client =  mock_strict_redis_client(host=dbconnector.DBConnector.LOCAL_HOST,
                                                  port=dbconnector.DBConnector.REDIS_PORT,
                                                  db=lldpdb_id)

        self.db_connector.redis_client = {snmpsubagent.MyAgent.IF_DB: ifdb_client,
                                          snmpsubagent.MyAgent.LLDP_DB: lldpdb_client}

    def setup_snmpsubagent(self):
        '''
            Initialize the snmp subagent
        '''

        self.snmp_subagent = snmpsubagent.MyAgent()
        snmpsubagent.MyAgent.db_connector = self.db_connector
        snmpsubagent.MyAgent.get_port_name_map(snmpsubagent.MyAgent.IF_DB)
        snmpsubagent.MyAgent.get_reverse_map()
        snmpsubagent.MyAgent.init_util_retriever(snmpsubagent.MyAgent.ACS_HW_SKU)

    def setup_interfaceupdater(self):
        '''
            Initialize an interface updater instance for testing
            only call the update function once
        '''

        queue = Queue.Queue(maxsize=20)
        child_abnormal_event = threading.Event()
        self.interface_updater = snmpsubagent.InterfacesUpdater()
        self.interface_updater.agent_setup(queue,
                                          snmpsubagent.MyAgent.oid.interfaces,
                                          snmpsubagent.MyAgent.update_frequency)
        self.interface_updater.add_child_abnormal_event(child_abnormal_event)
        try:
            self.interface_updater.update()
        except Exception:
            raise

    def load_port_name_map(self, client, file_name, suffix=None, table_name='port_name_map'):
        '''
            Upload the desired port_name_map to the mock redis
            The test scenario is determined by file_name
        '''

        file_name = self.get_file_name(file_name, suffix)
        file_path = self.get_full_path(file_name)
        with open(file_path, 'r') as f:
            for line in f:
                (key, val) = line.strip().split(', ')
                client.hset(table_name, key, val)


    def load_interfaces(self, client, suffix=None):
        '''
            Initialize all the interfaces in the mock redis
        '''
        for (if_name, if_sid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            file_name = self.get_file_name(if_sid, suffix)
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

    def compare_value(self, oid, val):   
        '''
            Check whether the value set for a counter - identified by oid 
            matches its expected value-val
        '''

        flag = True
        my_oid = oid
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            # ifNumber does not need if_index as a suffix
            if oid != '1.0':
                my_oid = oid + '.' + str(if_index)
            
            my_val = self.interface_updater._data[my_oid]['value']
            if my_val != val:   
                self.assertFalse('Value of %s is wrongly set for interface %s', (oid, if_name))     
                flag = False
                break
        return flag

    def compare_range(self, oid, min=None, max=None):
        '''
            Check whether the value for a counter - identified by oid
            is within (min, max)
        '''

        flag = True
        my_oid = oid
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            # ifNumber does not need if_index as a suffix
            if oid != '1.0':
                my_oid = oid + '.' + str(if_index)

            val = self.interface_updater._data[my_oid]['value']
            if min and max is None and val < min:
                self.assertFalse('Value for oid %s is less than %s for interface %s', (oid, min, if_name))
                flag = false
                break
            if min is None and max and val > max:
                self.assertFalse('Value for oid %s is greater than %s for interface %s', (oid, max, if_name))
                flag = False
                break
            if min and max and (val < min or val > max):
                self.assertFalse('Value for oid %s is not within (%s, %s) for interface %s', (oid, min, max, if_name))
                flag = False
                break
            if min is None and max is None:
                raise Exception('Error: compare_range, no min and max values are specified!')
        return flag

    def compare_type(self, oid, type):
        '''
            Check whether the type specified for a counter - identified by oid
            matches its desired ifmib type
        '''

        flag = True
        my_oid = oid
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            # ifNumber does not need if_index as a suffix
            if oid != '1.0':
                my_oid = oid + '.' + str(if_index)

            my_type = self.interface_updater._data[my_oid]['type']
            if my_type != type:
                self.assertFalse('Type for oid %s is wrongly set for interface %s', (oid, if_name))
                flag = False
                break
        return flag

    def test_ifNumber(self):
  
        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifNumber
        ifnum = len(snmpsubagent.MyAgent.port_name_map)
        self.assertTrue(self.compare_value(oid, ifnum))

    def test_ifIndex(self):
  
        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifIndex
        # Test whether ifIndex is greater than 1
        self.assertTrue(self.compare_range(oid, 1, None))

    def test_ifDescr(self):

        self.setup()
        flag = True
        # Test whether ifDescr matches ifName
        for (if_name, ifsid) in snmpsubagent.MyAgent.port_name_map.iteritems():
            if_index = snmpsubagent.get_index(if_name)
            oid = snmpsubagent.MyAgent.oid.ifDescr + '.' + str(if_index)
            if_descr = self.interface_updater._data[oid]['value']
            if if_descr != if_name:
                self.assertFalse('ifDescr does not match ifName for interface %s', if_name)
                flag = False
                break
        if flag:
            self.assertTrue('ifDescr is correctly set')


    def test_ifType(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifType
        self.assertTrue(self.compare_value(oid, 6))

    def test_ifMtu(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifMtu
        self.assertTrue(self.compare_value(oid, 9196))

    def test_ifSpeed(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifSpeed
        self.assertTrue(self.compare_value(oid, 4294967295))

    def test_ifPhysAddress(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifPhysAddress
        self.assertTrue(self.compare_value(oid, ''))

    def test_ifAdminStatus(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifAdminStatus
        self.assertTrue(self.compare_value(oid, 1))

    def test_ifLastChange(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifLastChange
        self.assertTrue(self.compare_value(oid, 0))

    def test_ifOperStatus(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOperStatus
        self.assertTrue(self.compare_range(oid, 1, 3))

    def test_ifInOctets(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifInOctets
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifInUcastPkts(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifInUcastPkts
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifInNUcastPkts(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifInNUcastPkts
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifInDiscards(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifInDiscards
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifInErrors(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifInErrors
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifInUnknownProtos(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifInUnknownProtos
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifOutOctets(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOutOctets
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifOutUcastPkts(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOutUcastPkts
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifOutNUcastPkts(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOutNUcastPkts
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32)) 

    def test_ifOutDiscards(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOutDiscards
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifOutErrors(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOutErrors
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_COUNTER32))

    def test_ifOutQlen(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifOutQLen
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_GAUGE32))

    def test_ifSpecific(self):

        self.setup()
        oid = snmpsubagent.MyAgent.oid.ifSpecific
        self.assertTrue(self.compare_value(oid, '0.0'))

if __name__ == "__main__":
     unittest.main()


