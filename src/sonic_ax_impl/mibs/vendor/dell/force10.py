from ax_interface import MIBMeta, ValueType
from ax_interface.mib import MIBEntry
from sonic_ax_impl.mibs.vendor import sys_util_h


class SSeriesMIB(metaclass=MIBMeta, prefix='.1.3.6.1.4.1.6027.3.10.1.2.9'):
    """
    -- .iso.org.dod.internet.private.enterprises
    .force10.f10Mgmt.f10ChassisMib.f10ChassisMibObject
    .chRpmObjects.chRpmUtilTable.chRpmUtilEntry.chRpmCpuUtil5Min
    """
    updater = sys_util_h

    # S-Series CPU utilization in percentage for last 5 seconds
    chStackUnitCpuUtil5sec = MIBEntry('1.2.1', ValueType.GAUGE_32, sys_util_h.get_cpuutil_5sec)

    # S-Series CPU utilization in percentage for last 1 minute.
    chStackUnitCpuUtil1Min = MIBEntry('1.3.1', ValueType.GAUGE_32, sys_util_h.get_cpuutil_1min)

    # S-Series CPU utilization in percentage for last 5 minutes.
    chStackUnitCpuUtil5Min = MIBEntry('1.4.1', ValueType.GAUGE_32, sys_util_h.get_cpuutil_5min)

    # Stack member total memory usage in percentage
    chStackUnitMemUsageUtil = MIBEntry('1.5.1', ValueType.GAUGE_32, sys_util_h.get_memutil)
