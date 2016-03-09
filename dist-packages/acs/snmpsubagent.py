#!/usr/bin/env python

__author__ = "Chen Liu<liuchen@microsoft.com>"
__copyright__ = "copyrighted by Microsoft"
__contributors__ = ["Chen Liu"]
__maintainer__ = ["Chen Liu"]
__version__ = "1.0"
__team_email__ = "linuxnetdev@microsoft.com"

'''
This script implements an SNMP AgentX subagent
'''
import os
import re
import time
import redis
import getopt
import psutil
import pyagentx
import threading
import collections

import dell
import oidconst

import pysswsdk.util as util
import pysswsdk.dbconnector as dbconnector

# -------------------------- Logging --------------------------------------
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------
class RegexMatchingError(Exception):
      pass

class InterfacesUpdater(pyagentx.Updater):

    ################### Default values ################################
    # Default value for ifType before record available in Redis
    # ethernetCsmacd(6), -- for all ethernet-like interfaces,
    #                    -- regardless of speed, as per RFC3635
    IF_TYPE = 6

    # Default value for ifMtu before record available in Redis
    # ACS switches only use the MTU value of 9196
    IF_MTU = 9196

    # Default value for ifSpeed before record available in Redis
    # If the bandwidth of the interface is greater
    # than the maximum value reportable by this object,
    # then this object should report its maximum value
    # (4.294,967,295) and ifHighSpeed must be used to
    # report the interface's speed.
    IF_SPEED = 4294967295

    # Default value for ifPhysAddress before record available in Redis
    IF_PHYS_ADDRESS = ''

    # Default value for ifAdminStatus before record available in Redis
    # 1 -- up; 2 -- down; 3 -- testing
    IF_ADMIN_STATUS = 1

    # Default value for ifLastChange before record available in Redis
    IF_LAST_CHANGE = 0

    IF_SPECIFIC = '0.0'

    MASK = 0xffffffff
    ################# End of default values ############################

    def __init__(self):

        super(InterfacesUpdater, self).__init__()

        # Initialize the map between the Redis keys of ifTable counters
        # and their oids
        self.iftable_counter32_keys = {
            'OPER_STATUS':MyAgent.oid.ifOperStatus,
            'IN_OCTETS':MyAgent.oid.ifInOctets,
            'IN_UCAST_PKTS':MyAgent.oid.ifInUcastPkts,
            'IN_NON_UCAST_PKTS':MyAgent.oid.ifInNUcastPkts,
            'IN_DISCARDS':MyAgent.oid.ifInDiscards,
            'IN_ERRORS':MyAgent.oid.ifInErrors,
            'IN_UNKNOWN_PROTOS':MyAgent.oid.ifInUnknownProtos,
            'OUT_OCTETS':MyAgent.oid.ifOutOctets,
            'OUT_UCAST_PKTS':MyAgent.oid.ifOutUcastPkts,
            'OUT_NON_UCAST_PKTS':MyAgent.oid.ifOutNUcastPkts,
            'OUT_DISCARDS':MyAgent.oid.ifOutDiscards,
            'OUT_ERRORS':MyAgent.oid.ifOutErrors,
            'OUT_QLEN':MyAgent.oid.ifOutQLen
        }
    
    def init_default_vals(self, if_index):
        # Set the default value for ifType before record available in Redis
        self.set_INTEGER(MyAgent.oid.ifType + '.' + str(if_index), InterfacesUpdater.IF_TYPE)

        # Set the default value for ifMtu before record available in Redis
        self.set_INTEGER(MyAgent.oid.ifMtu + '.' + str(if_index), InterfacesUpdater.IF_MTU)

        # Set the default value for ifSpeed before record available in Redis
        self.set_GAUGE32(MyAgent.oid.ifSpeed + '.' + str(if_index), InterfacesUpdater.IF_SPEED)

        # Set the default value for ifPhysAddress before record available in Redis
        self.set_OCTETSTRING(MyAgent.oid.ifPhysAddress + '.' + str(if_index), InterfacesUpdater.IF_PHYS_ADDRESS)

        # Set the default value for ifAdminStatus before record available in Redis
        self.set_INTEGER(MyAgent.oid.ifAdminStatus + '.' + str(if_index), InterfacesUpdater.IF_ADMIN_STATUS)

        # Set the default value for ifLastChange before record available in Redis
        self.set_TIMETICKS(MyAgent.oid.ifLastChange + '.' + str(if_index), InterfacesUpdater.IF_LAST_CHANGE)

        # Set the default value for ifSpecific
        self.set_OBJECTIDENTIFIER(MyAgent.oid.ifSpecific + '.' + str(if_index),
                                  InterfacesUpdater.IF_SPECIFIC)

    def update(self):
        '''
           Update the interface counters
           esp. ifNumber and ifTable
        '''

        logger.debug("Updating the interfaces counters...")
        
        # set the value for if_number based on the number 
        # of records stored in port_name_map
        if_number = len(MyAgent.port_name_map)
        self.set_INTEGER(MyAgent.oid.ifNumber, if_number)

        # TODO - Need to retrieve switch facts relatd to interface number and sku name 
        #      - from minigraph
        if if_number != MyAgent.IF_NUM and MyAgent.hw_sku == MyAgent.ACS_HW_SKU:
            err_msg = "Expecting %s interfaces, only received %s records from redis."
            logger.warning(err_msg % {MyAgent.IF_NUM, if_number})
            # This exception will is treated as child abnormal event and call the subagent to stop
            raise Exception(err_msg % {MyAgent.IF_NUM, if_number})

        for (if_name, if_sai_id) in MyAgent.port_name_map.iteritems():
            if_counter_records = MyAgent.db_connector.get_all(MyAgent.IF_DB, if_sai_id, blocking=True)
            if if_counter_records is None:
                logger.warning('Redis has no record for interface: %s', if_name)
                continue

            logger.debug('Interface: %s', if_name)
            logger.debug('Redis record: %s', if_counter_records)

            if_index = get_index(if_name)

            # Initialize those counters that do not change with default values
            self.init_default_vals(if_index)

            # set the value for ifIndex
            self.set_INTEGER(MyAgent.oid.ifIndex + '.' + str(if_index), if_index)

            # Initialize those counters that do not change with default values
            self.init_default_vals(if_index)

            # Set the value for ifDescr
            self.set_OCTETSTRING(MyAgent.oid.ifDescr + '.' + str(if_index), if_name)

            # Retrieve the counters in self.iftable_counter32_keys map from Redis
            # and update corresponding interfaces counters
            if_counter_keys = if_counter_records.keys()
            for if_counter_key in if_counter_keys:
                if_counter_value = int(if_counter_records.get(if_counter_key))
                if if_counter_value is None:
                    logger.warning('Redis has no record for counter %s', if_counter_key)
                    if_counter_value = 0
                # All redis records are 64-bits. Needs conversion to 32 bit.
                if_counter_value32 = if_counter_value & InterfacesUpdater.MASK

                # In our Redis db, counters are named differently from IF-MIB
                # Get the corresponding 32-bit interface counter names based on
                # the Redis record keys
                if_oid = self.iftable_counter32_keys.get(if_counter_key)
                if if_oid is None:
                    # Redis db keys may belong to different mibs
                    logger.debug('%s is not a counter in ifTable, skip', if_counter_key)
                    continue

                if if_counter_key == 'OPER_STATUS':
                    self.set_INTEGER(if_oid + '.' + str(if_index), if_counter_value32)
                elif if_counter_key == 'OUT_QLEN':
                    self.set_GAUGE32(if_oid + '.' + str(if_index), if_counter_value32)
                else:
                    logger.debug('Update counter %s with value %s in ifTable',
                                 if_counter_key, if_counter_value32)
                    self.set_COUNTER32(if_oid + '.' + str(if_index), if_counter_value32)


class IfMIBObjectsUpdater(pyagentx.Updater):

    ########################## Default values ##########################

    # Default values are set based on the windows snmpd DatabaseBulder.cs
    #default value for ifLinkUpDownTrapEanble
    IF_LINK_UP_DOWN_TRAP_ENABLE = 0

    # Default value for ifHighSpeed
    IF_HIGH_SPEED = 4000

    # Default value for ifPromiscuousMode
    # 1 -- true; 2 -- falsefault value for ifPromiscuousMode
    IF_PROMISCUOUS_MODE = 1

    # Default value for ifConnectorPresent
    # 1 -- true; 2 -- false
    IF_CONNECTOR_PRESENT = 1

    # Default value for ifCounterDiscontinuityTime
    IF_COUNTER_DISCONTINUITY_TIME = 0

    MASK = 0xffffffff

    #################### End of default values ############################

    def __init__(self):

        super(IfMIBObjectsUpdater, self).__init__()

        # Initialize the map between the Redis keys for ifXtable counters
        # and their oids; We differentiate 32-bit and 64-bit counters
        self.ifxtable_counter32_keys = {
            'IN_MULTICAST_PKTS':MyAgent.oid.ifInMulticastPkts,
            'IN_BROADCAST_PKTS':MyAgent.oid.ifInBroadcastPkts,
            'OUT_MULTICAST_PKTS':MyAgent.oid.ifOutMulticastPkts,
            'OUT_BROADCAST_PKTS':MyAgent.oid.ifOutBroadcastPkts
        }

        self.ifxtable_counter64_keys = {
            'IN_OCTETS':MyAgent.oid.ifHCInOctets,
            'IN_UCAST_PKTS':MyAgent.oid.ifHCInUcastPkts,
            'IN_MULTICAST_PKTS':MyAgent.oid.ifHCInMulticastPkts,
            'IN_BROADCAST_PKTS':MyAgent.oid.ifHCInBroadcastPkts,
            'OUT_OCTETS':MyAgent.oid.ifHCOutOctets,
            'OUT_UCAST_PKTS':MyAgent.oid.ifHCOutUcastPkts,
            'OUT_MULTICAST_PKTS':MyAgent.oid.ifHCOutMulticastPkts,
            'OUT_BROADCAST_PKTS':MyAgent.oid.ifHCOutBroadcastPkts
        }

    def init_default_vals(self, if_index):
        # Set the default value for ifLinkUpDownTrapEanble
        self.set_INTEGER(MyAgent.oid.ifLinkUpDownTrapEnable + '.' + str(if_index),
                         IfMIBObjectsUpdater.IF_LINK_UP_DOWN_TRAP_ENABLE)

        # Set the default value for ifHighSpeed
        self.set_GAUGE32(MyAgent.oid.ifHighSpeed + '.' + str(if_index),
                         IfMIBObjectsUpdater.IF_HIGH_SPEED)

        # Set the default value for ifPromiscuousMode
        self.set_INTEGER(MyAgent.oid.ifPromiscuousMode + '.' + str(if_index),
                         IfMIBObjectsUpdater.IF_PROMISCUOUS_MODE)

        # Set the default value for ifConnectorPresent
        self.set_INTEGER(MyAgent.oid.ifConnectorPresent + '.' + str(if_index),
                         IfMIBObjectsUpdater.IF_CONNECTOR_PRESENT)

        # Set the default value for ifCounterDiscontinuityTime
        self.set_TIMETICKS(MyAgent.oid.ifCounterDiscontinuityTime + '.' + str(if_index),
                           IfMIBObjectsUpdater.IF_COUNTER_DISCONTINUITY_TIME)

    def update(self):
        '''
            Update the counter values in ifMIBObjects,
            esp. ifXTable
        '''

        logger.debug("Updating ifXTable...")

        for (if_name, if_sai_id) in MyAgent.port_name_map.iteritems():
            if_index = get_index(if_name)

            if_counter_records = MyAgent.db_connector.get_all(MyAgent.IF_DB, 
                                                              if_sai_id, blocking=True)
            if if_counter_records is None:
                logger.warning('Redis has no record for interface: %s', if_name)
                continue

            # Initialize those counters that do not change with default values
            self.init_default_vals(if_index)

            # Set the value of ifName
            self.set_OCTETSTRING(MyAgent.oid.ifName + '.' + str(if_index), if_name)

            # Update the ifxtable counters keyed in self.ifxtable_counter32_keys and
            # self.ifxtable_counters64_keys by retrieving their values from Redis 
            if_counter_names = if_counter_records.keys()
            for if_counter_name in if_counter_names:
                if_counter_value = int(if_counter_records.get(if_counter_name))
                if if_counter_value is None:
                    logger.warning('Redis has no record for Counter %s', if_counter_name)
                    if_counter_value = 0
                # All redis records are 64-bits. Needs conversion to 32 bit.
                if_counter_value32 = if_counter_value & IfMIBObjectsUpdater.MASK

                # In our Redis db, counters are named differently from IF-MIB
                # Get the corresponding 32-bit interface counter names based on
                # the Redis record keys
                # Set the value for 32-bit counters
                if_oid = self.ifxtable_counter32_keys.get(if_counter_name)
                if if_oid is None:
                    logger.debug('%s is not a 32-bit counter in ifXTable, skip', if_counter_name)
                else:
                    logger.debug('Update 32-bit counter %s with value %s in ifXTable',
                                 if_counter_name, if_counter_value32)
                    self.set_COUNTER32(if_oid + '.' + str(if_index), if_counter_value32)

                # Set the value for 64-bit counters
                if_oid = self.ifxtable_counter64_keys.get(if_counter_name)
                if if_oid is None:
                    logger.debug('%s is not a 64-bit counter in ifXTable, skip', if_counter_name)
                else:
                    logger.debug('Update 64-bit counter %s with value %s in ifXTable',
                                 if_counter_name, if_counter_value)
                    self.set_COUNTER64(if_oid + '.' + str(if_index), if_counter_value)

            # Set the default value for ifAlias
            self.set_OCTETSTRING(MyAgent.oid.ifAlias + '.' + str(if_index), if_name)

class ChStackUnitUtilUpdater(pyagentx.Updater):

    def update(self):
        ''' 
            Update the ChStackUnitUtilTable for ACS-S6000 
        '''

        cpuutil_5sec = MyAgent.util_retriever.get_cpuutil_5sec()
        oid_5sec = MyAgent.dell_oid.ChStackUnitCpuUtil5sec
        logger.debug('cpu utilization for the last 5 sec is %s %s', oid_5sec, cpuutil_5sec)
        self.set_GAUGE32(oid_5sec, cpuutil_5sec)

        cpuutil_1min = MyAgent.util_retriever.get_cpuutil_1min()
        oid_1min = MyAgent.dell_oid.ChStackUnitCpuUtil1Min
        logger.debug('cpu utilization for the last 1 minute is %s %s', oid_1min, cpuutil_1min)
        self.set_GAUGE32(oid_1min, cpuutil_1min)

        cpuutil_5min = MyAgent.util_retriever.get_cpuutil_5min()
        oid_5min = MyAgent.dell_oid.ChStackUnitCpuUtil5Min
        logger.debug('cpu utilization for the last 5 minute is %s %s', oid_5min, cpuutil_5min)
        self.set_GAUGE32(oid_5min, cpuutil_5min)        

        mem_util = MyAgent.util_retriever.get_memutil()
        oid_mem = MyAgent.dell_oid.ChStackUnitMemUsageUtil
        logger.debug('memory utilization is %s %s', oid_mem, mem_util)
        self.set_GAUGE32(oid_mem, mem_util)

class CpuMemUtilRetriever(threading.Thread):

    ########################## Default values ##########################

    # Default value for cpu memory retrieval frequency in seconds
    FREQ = 5

    #################### End of default values #########################

    def __init__(self):

        super(CpuMemUtilRetriever,self).__init__()
        logger.debug('Initlizing the util helper...')
        self.stop = threading.Event()
        # a sliding window of 60 contiguous 5 sec utilization
        self.cpuutils = collections.deque([0.0]*60, maxlen=60)
        self.update_util()

    def update_util(self):

        cpu_util = psutil.cpu_percent(interval=None, percpu=False)
        logger.debug('Retrieving cpu util for the last 5 second %f', cpu_util)
        self.cpuutils.append(cpu_util)

    def run(self):
        '''
            Update the util counters periodically
        '''

        while True:
            if self.stop.is_set(): break
            self.update_util()
            time.sleep(CpuMemUtilRetriever.FREQ)
        logger.info('Stopping CpuMemUtilRetriever')

    def get_cpuutil_5sec(self):

        return self.cpuutils[-1]

    def get_cpuutil_1min(self):

        return sum(list(self.cpuutils)[48:60])/12

    def get_cpuutil_5min(self):

        return sum(self.cpuutils)/len(self.cpuutils)

    def get_memutil(self):

        self.mem_util = psutil.virtual_memory()[2]
        return self.mem_util

class LldpLocSysUpdater(pyagentx.Updater):

    def __init__(self):
        super(LldpLocSysUpdater, self).__init__()
        
        # Initialize the map between Redis keys of lldp local system
        # and their oids; This list may grow
        self.lldp_key_map = {
            'LldpLocPortId': MyAgent.oid.lldpLocPortId
        }

    def update(self):

        logger.debug('Updating lldp local system counters...')

        # Get all interface SAI IDs via the command 'keys *'
        # It is possible a switch has no neighbors configured
        sai_ids = MyAgent.db_connector.keys(MyAgent.LLDP_DB, blocking=True)
        if sai_ids is None:
            return

        for sai_id in sai_ids:
            if_name = MyAgent.reverse_port_name_map.get(sai_id)
            if_index = get_index(if_name)
            oid = MyAgent.oid.lldpLocPortId + '.' + str(if_index)
            self.set_OCTETSTRING(oid, if_name)

class LldpRemSysUpdater(pyagentx.Updater):

    def __init__(self):

        super(LldpRemSysUpdater, self).__init__()

        # Initialize the map between the Redis keys of lldp counters
        # and their oids
        self.lldp_key_map = {
            'LldpRemPortIdSubtype':MyAgent.oid.lldpRemPortIdSubtype,
            'LldpRemPortID':MyAgent.oid.lldpRemPortId,
            'LldpRemPortDescr':MyAgent.oid.lldpRemPortDesc,
            'LldpRemSysName':MyAgent.oid.lldpRemSysName
        }

        # Initialize the map between subtype name and value
        self.subtype_map = {
            'ifalias':1,
            'portcomponent':2, 
            'macaddress':3,
            'networkaddress':4, 
            'ifname':5, 
            'agentcircuitid':6, 
            'local':7 
        }

    def update(self):
        ''' 
            Retrieve lldp counter info from Redis
            Update required lldp counters for snmpd
        '''

        logger.debug('Updating lldp remote system counters...')

        # Get all interface SAI IDs via the command 'keys *'
        # It is possible a switch has no neighbors configured
        sai_ids = MyAgent.db_connector.keys(MyAgent.LLDP_DB, blocking=True)
        if sai_ids is None:
            return
        
        # Retrieve and process lldp info for each interface
        for sai_id in sai_ids:
            if_name = MyAgent.reverse_port_name_map.get(sai_id)
            if_index = get_index(if_name)
            logger.debug('sai_id:%s, if_name:%s, if_index:%s' %(sai_id, if_name, if_index))
            lldp_info = MyAgent.db_connector.get_all(MyAgent.LLDP_DB, sai_id, blocking=True)
            if lldp_info is None:
                logger.warning('Redis has no lldp record for interface: %s', sai_id)
                continue

            for (key, val) in lldp_info.iteritems():
                logger.debug('lldp info key:%s, val:%s' % (key, val))
                oid = self.lldp_key_map.get(key)
                if oid is None:
                    err_msg = 'lldp key ' + key + ' does not exist!'
                    logger.warning(err_msg)
                    continue

                oid = oid + '.' + str(if_index) 
                if key == 'LldpRemPortIdSubtype':
                    try:
                        sub_type = self.get_subtype(val)
                    except RegexMatchingError:
                        continue
                    logger.debug('Set lldpRemPortIdSubtype for oid:%s to %s' % (oid, sub_type)) 
                    self.set_INTEGER(oid, sub_type)
                else:
                    logger.debug('Set oid:%s to %s' % (oid, val))
                    self.set_OCTETSTRING(oid, val)

    def get_subtype(self, val):
        '''
            Map subtype name to its value
        '''

        # Need to double check whether subtypes names are standardized
        # so far I have seen ifname, macaddress, local being used

        # Possible subtype spelling can be ifalias, ifAlias
        # interfacealias, interfaceAlias etc.
        match = re.match('^i[a-z]*(a|A)lias$', val)
        if match:
            return self.subtype_map.get('ifalias')

        match = re.match('^p[a-z]*(c|C)omponent$', val)
        if match:
            return self.subtype_map.get('portcomponent')

        match = re.match('^m[a-z]*(a|A)ddress$', val)
        if match:
            return self.subtype_map.get('macaddress')

        # Possible subtype spelling includes netaddress, netAddress
        # networkaddress, networkAddress etc. 
        match = re.match('^n[a-z]+(a|A)ddress$', val)
        if match:
            return self.subtype_map.get('networkaddress')

        match = re.match('^i[a-z]*(n|N)ame$', val)
        if match:
            return self.subtype_map.get('ifname')

        match = re.match('^a[a-z]*(c|C)[a-z]*(i|I)d$', val)
        if match:
            return self.subtype_map.get('agentcircuitid')

        match = re.match('^local$', val)
        if match:
            return self.subtype_map.get('local')

        
        err_msg = 'lldpRemPortIdSubtype ' + val + ' does not match any known pattern'
        logger.warning(err_msg)
        raise RegexMatchingError(err_msg)

class MyAgent(pyagentx.Agent):

    ########################## Default values ##########################

    # Default update frequency in seconds
    FREQ = 10

    # Redis database names
    IF_DB = 'IF_COUNTER_DB'
    LLDP_DB = 'LLDP_COUNTER_DB'

    # Define the hw_sku name and number of interfaces statically here for now
    # TODO - retrieve sku name dynamically from minigraph
    ACS_HW_SKU = 'ACS-S6000'
    IF_NUM = 32

    #################### End of default values #########################

    ########################## Static variables ##########################
    update_frequency = FREQ

    dbconnector.DBConnector.setup()
    db_connector = dbconnector.DBConnector()
    oid = oidconst.OidConsts()
    
    # This map includes the mapping between interface name and SAI ID
    port_name_map = {}

    # In order to retrieve interface name based on SAI ID
    # We keep another map between SAI ID and interface name
    reverse_port_name_map = {} 

    # TODO - retrieve HwSku from minigraph
    hw_sku = None
    util_retriever = None
    dell_oid = None

    #################### End of static variables #########################

    @staticmethod
    def connect_to_redis(db_list):
        '''
            Connect to Redis databases  via dbconnector
        '''

        logger.info('Connect to Redis databases %s' %db_list)

        for db_name in db_list:
            MyAgent.db_connector.connect(db_name)

    @staticmethod
    def get_port_name_map(db_name):
        '''
            Retrieving the port_name_map from Redis
        '''

        MyAgent.port_name_map = MyAgent.db_connector.get_all(db_name,
                                                             'port_name_map',
                                                             blocking=True)

    @staticmethod
    def get_reverse_map():

        logger.debug('Initialize the reversed port_name_map')
        for (name, sai_id) in MyAgent.port_name_map.iteritems():
            MyAgent.reverse_port_name_map[sai_id] = name

        logger.debug('reverse_map:%s' % str(MyAgent.reverse_port_name_map))

    @staticmethod
    def init_util_retriever(hw_sku):
        
        MyAgent.hw_sku = hw_sku

        if hw_sku == MyAgent.ACS_HW_SKU:
            logger.info('hw_sku: %s', hw_sku)
            MyAgent.dell_oid = dell.DellOid()
            MyAgent.util_retriever = CpuMemUtilRetriever()
        
    def register_chstackunitutiltable_updater(self):
        
        cpumem_table_oid = MyAgent.dell_oid.chStackTable
        logger.debug("register_chstackunitutiltable_updater %s %s", MyAgent.hw_sku, cpumem_table_oid)
        MyAgent.util_retriever.start()
        self.register(cpumem_table_oid, ChStackUnitUtilUpdater, MyAgent.update_frequency)

    def setup(self):
        '''
            Register ifmib handlers
        '''
        
        self.register(MyAgent.oid.interfaces, InterfacesUpdater, MyAgent.update_frequency)
        self.register(MyAgent.oid.ifMIBObjects, IfMIBObjectsUpdater, MyAgent.update_frequency)
        self.register_chstackunitutiltable_updater()
        self.register(MyAgent.oid.lldpLocPortTable, LldpLocSysUpdater, MyAgent.update_frequency)
        self.register(MyAgent.oid.lldpRemTable, LldpRemSysUpdater, MyAgent.update_frequency)

    def stop(self):
        ''' 
            wrapped the base stop function to also stop MyAgent.util_retriever
        '''
        
        super(MyAgent,self).stop()
        MyAgent.util_retriever.stop.set()
        MyAgent.util_retriever.join()

def get_index(if_name):
    '''
        index patterns:
        ifIndex cannot be 0
        Ethernet N = N + 1
        portchannel N = 1000000 + N
        Vlan N = 2000000 + N
        Management N = 3000000 + N
        Management N/M = 3000000 + N * 1000 + M
        Loopback N = 4000000 + N
        Loopback N/M = 4000000 + 1000 * N + M
    '''

    match = re.match("^Ethernet(\d+)$", if_name)
    if match:
        n = match.group(1)
        return int(n) + 1

    logger.exception('Unable to match interface name %s to known pattern', if_name)
    # This event is not handled in the update function and will be treated as
    # a childAbonormalEvent, and cause the subagent to stop
    raise Exception('Unable to match interface name %s to known pattern', if_name)


def main():

    util.setup_logging('data.acssnmpsubagent_logger.json')

    snmp_subagent = None

    try:
        args = util.process_options(os.path.basename(__file__))
        
        snmp_subagent = MyAgent()

        log_level = args.get('log_level')
        update_frequency = args.get('update_frequency')
        if log_level:
            snmp_subagent.logger.setLevel(log_level)
        if update_frequency:
            snmp_subagent.update_frequency = update_frequency

        db_list = [MyAgent.IF_DB, MyAgent.LLDP_DB]
        MyAgent.connect_to_redis(db_list)
        MyAgent.get_port_name_map(MyAgent.IF_DB)
        MyAgent.get_reverse_map()
        MyAgent.init_util_retriever(MyAgent.ACS_HW_SKU)

        logger.info('Start snmpsubagent...')
        snmp_subagent.start()
    except getopt.GetoptError as e:
        logger.error(e)
    except KeyboardInterrupt:
        snmp_subagent.stop()
    except Exception as e:
        logger.exception('Unhandled exception:%s', e)
        snmp_subagent.stop()

if __name__=="__main__":

    main()

