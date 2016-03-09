import const

class DellOid(const._const):
    def __init__(self):

        # the Dell f10 chstacktable oid        
        self.chStackTable = '1.3.6.1.4.1.6027.3.10.1.2.9'

        #S-Series CPU utilization in percentage for last 5 seconds
        self.ChStackUnitCpuUtil5sec = '1.2.1'

        #S-Series CPU utilization in percentage for last 1 minute.
        self.ChStackUnitCpuUtil1Min = '1.3.1'

        # S-Series CPU utilization in percentage for last 5 minutes.
        self.ChStackUnitCpuUtil5Min = '1.4.1'

        # Stack member total memory usage in percentage
        self.ChStackUnitMemUsageUtil = '1.5.1'
