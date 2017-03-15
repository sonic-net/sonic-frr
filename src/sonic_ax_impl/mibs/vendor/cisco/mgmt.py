from sonic_ax_impl.mibs.vendor import sys_util_h
from ax_interface import MIBMeta, ValueType
from ax_interface.mib import MIBEntry


class CiscoSystemExtMIB(metaclass=MIBMeta, prefix='.1.3.6.1.4.1.9.9.305'):
    """
    {iso(1) identified-organization(3) dod(6) internet(1) private(4) enterprise(1) 9 ciscoMgmt(9)
    CISCO-SYSTEM-EXT-MIB (305)}

    OID_cseSysMemoryUtilization = "1.3.6.1.4.1.9.9.305.1.1.2.0";
    OID_cseSysCPUUtilization = "1.3.6.1.4.1.9.9.305.1.1.1.0";
    """
    updater = sys_util_h

    """
    cseSysMemoryUtilization OBJECT-TYPE
    SYNTAX          Gauge32 (0..100 )
    UNITS           "%"
    MAX-ACCESS      read-only
    STATUS          current
    DESCRIPTION
        "The average utilization of memory on the active
        supervisor."
    ::= { ciscoSysInfoGroup 2 }
    """
    cseSysMemoryUtilization = MIBEntry('1.1.2.0', ValueType.GAUGE_32, sys_util_h.get_memutil)

    """
    cseSysCPUUtilization OBJECT-TYPE
    SYNTAX          Gauge32 (0..100 )
    UNITS           "%"
    MAX-ACCESS      read-only
    STATUS          current
    DESCRIPTION
        "The average utilization of CPU on the active
        supervisor."
    ::= { ciscoSysInfoGroup 1 }
    """
    cseSysCPUUtilization = MIBEntry('1.1.1.0', ValueType.GAUGE_32, sys_util_h.get_cpuutil_5sec)
