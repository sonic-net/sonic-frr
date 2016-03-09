#!/usr/bin/env python

__author__ = "Chen Liu<liuchen@microsoft.com>"
__copyright__ = "copyrighted by Microsoft"
__contributors__ = ["Chen Liu"]
__maintainer__ = ["Chen Liu"]
__version__ = "1.0"
__team_email__ = "linuxnetdev@microsoft.com"


'''
This script implements unit tests for ChStackUnitUtilUpdater
'''

import sys
import Queue
import psutil
import unittest
import threading
import collections

from inspect import getfile, currentframe
from os.path import join, dirname, abspath

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

class TestChStackUnitUtilUpdater(unittest.TestCase):
    '''
        Unit tests for ChStackUnitUtilUpdater
    '''


    def setup(self):
        '''
            Set up redis databses.
            The testing scenarios can be changed by setting port_name_map_fname
        '''

        self.setup_snmpsubagent()
        self.setup_chstackunitutilupdater()

    def setup_snmpsubagent(self):
        '''
            Initialize the snmp subagent
        '''

        self.snmp_subagent = snmpsubagent.MyAgent()
        snmpsubagent.MyAgent.init_util_retriever(snmpsubagent.MyAgent.ACS_HW_SKU)

    def setup_chstackunitutilupdater(self):
        '''
            Initialize an ChStackUnitUtilUpdater instance for testing
            only call the update function once
        '''

        queue = Queue.Queue(maxsize=20)
        child_abnormal_event = threading.Event()
        snmpsubagent.MyAgent.util_retriever.cpuutils = collections.deque([0.9, 0.4, 0.6,
                                            0.3, 0.7, 0.2, 0.8, 0.5, 0.0, 0.0, 0.0, 0.0, 0.1,
                                            0.2, 0.4, 0.9, 0.1, 0.5, 0.4, 0.6, 0.8, 0.3, 0.7,
                                            0.2, 0.5, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.1,
                                            0.3, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0, 0.2, 0.0, 0.0,
                                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                            0.0, 0.0, 0.0, 0.0, 0.4, 0.5, 0.1], maxlen=60)
        self.ChStackUnitUtilUpdater = snmpsubagent.ChStackUnitUtilUpdater()
        self.ChStackUnitUtilUpdater.agent_setup(queue,
                                          snmpsubagent.MyAgent.oid.ifMIBObjects,
                                          snmpsubagent.MyAgent.update_frequency)
        self.ChStackUnitUtilUpdater.add_child_abnormal_event(child_abnormal_event)
        try:
            self.ChStackUnitUtilUpdater.update()
        except Exception:
            raise

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
        my_val = self.ChStackUnitUtilUpdater._data[my_oid]['value']
        if my_val != val:
            self.assertFalse('Value for oid %s is wrongly set', oid)
            flag = False
        return flag

    def compare_range(self, oid, min=None, max=None):
        '''
            Check whether the value for a counter - identified by oid
            is within (min, max)
        '''

        flag = True
        my_oid = oid
        val = self.ChStackUnitUtilUpdater._data[my_oid]['value']
        if min and max is None and val < min:
            self.assertFalse('Value for oid %s is less than %s', (oid, min))
            flag = false
        if min is None and max and val > max:
            self.assertFalse('Value for oid %s is greater than %s', (oid, max))
            flag = False
        if min and max and (val < min or val > max):
            self.assertFalse('Value for oid %s is not within (%s, %s)', (oid, min, max))
            flag = False
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
        my_type = self.ChStackUnitUtilUpdater._data[my_oid]['type']
        if my_type != type:
            self.assertFalse('Type for oid %s is wrongly set', oid)
            flag = False
        return flag

    def test_ChStackUnitCpuUtil5sec_type(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitCpuUtil5sec
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_GAUGE32))

    def test_ChStackUnitCpuUtil5sec_value(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitCpuUtil5sec
        val = snmpsubagent.MyAgent.util_retriever.get_cpuutil_5sec()
        self.assertTrue(self.compare_value(oid, val))

    def test_ChStackUnitCpuUtil1Min(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitCpuUtil1Min
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_GAUGE32))

    def test_ChStackUnitCpuUtil1Min_value(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitCpuUtil1Min
        val = snmpsubagent.MyAgent.util_retriever.get_cpuutil_1min()
        self.assertTrue(self.compare_value(oid, val))

    def test_ChStackUnitCpuUtil5Min_type(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitCpuUtil5Min
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_GAUGE32))

    def test_ChStackUnitCpuUtil5Min_value(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitCpuUtil5Min
        val = snmpsubagent.MyAgent.util_retriever.get_cpuutil_5min()
        self.assertTrue(self.compare_value(oid, val))

    def test_ChStackUnitMemUsageUtil_type(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitMemUsageUtil
        self.assertTrue(self.compare_type(oid, pyagentx.TYPE_GAUGE32))

    def test_ChStackUnitMemUsageUtil_value(self):

        self.setup()
        oid = snmpsubagent.MyAgent.dell_oid.ChStackUnitMemUsageUtil
        val = psutil.virtual_memory()[2]
        self.assertTrue(self.compare_value(oid, val))


if __name__ == "__main__":
     unittest.main()


