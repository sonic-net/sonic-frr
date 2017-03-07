import collections
import time

import psutil

from ax_interface import MIBUpdater
from sonic_ax_impl import logger


class SystemUtilizationHandler(MIBUpdater):
    def __init__(self):
        super().__init__()
        # From the psutil documentation https://pythonhosted.org/psutil/#psutil.cpu_percent:
        #
        #    Warning the first time this function is called
        #    with interval = 0.0 or None it will return a
        #    meaningless 0.0 value which you are supposed
        #    to ignore.
        psutil.cpu_percent()
        # '...is recommended for accuracy that this function be called with at least 0.1 seconds between calls.'
        time.sleep(0.1)
        # a sliding window of 60 contiguous 5 sec utilization (up to five minutes)
        self.cpuutils = collections.deque([psutil.cpu_percent()], maxlen=60)
        self.system_virtual_memory = psutil.virtual_memory()

        logger.debug('System Utilization handler initialized.')

    def get_cpuutil_5sec(self):
        """
        :return: Last polled CPU utilization.
        """
        return int(self.cpuutils[-1])

    def get_cpuutil_1min(self):
        """
        :return: Up to one minute's worth of average CPU utilization.
        """
        past_utilization = list(self.cpuutils)[-12:]
        return int(sum(past_utilization) / len(past_utilization))

    def get_cpuutil_5min(self):
        """
        :return: Up to five minute's worth of average CPU utilization.
        """
        return int(sum(self.cpuutils) / len(self.cpuutils))

    def get_memutil(self):
        """
        :return: The current memory utilization (as a percent integer)
        """
        return int(self.system_virtual_memory.percent)

    def update_data(self):
        """
        Background task to add CPU Utilization sample / refresh memory utilization.
        """
        cpu_util = psutil.cpu_percent()
        self.cpuutils.append(cpu_util)
        self.system_virtual_memory = psutil.virtual_memory()

        logger.debug('Updating CPU/Mem Utilization with: {}% / {}%'.format(cpu_util, self.get_memutil()))


sys_util_h = SystemUtilizationHandler()
