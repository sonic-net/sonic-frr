#!/usr/bin/env python

#############################################################################
# Mellanox
#
# Module contains an implementation of SONiC PSU Base API and
# provides the PSUs status for SNMP testing
#
#############################################################################

class PsuUtil():
    """PSUutil class for SNMP testing"""

    def __init__(self):
        """ For testing purpose only """
        self.num_of_psus = 2
        self.psu_status = { 1 : True, 2 : False }

    def get_num_psus(self):
        """
        Retrieves the number of PSUs available on the device

        :return: An integer, the number of PSUs available on the device
        """
        """ For testing purpose only """
        return self.num_of_psus

    def get_psu_status(self, index):
        """
        Retrieves the oprational status of power supply unit (PSU) defined
                by 1-based index <index>

        :param index: An integer, 1-based index of the PSU of which to query status
        :return: Boolean, True if PSU is operating properly, False if PSU is faulty
        """
        """ For testing purpose only """
        if not isinstance(index, int):
            return False
        elif index > 0 and index <= self.num_of_psus:
            return self.psu_status[index]
        else:
            return False

    def get_psu_presence(self, index):
        """
        Retrieves the presence status of power supply unit (PSU) defined
                by 1-based index <index>

        :param index: An integer, 1-based index of the PSU of which to query status
        :return: Boolean, True if PSU is plugged, False if not
        """
        """ For testing purpose only """
        if not isinstance(index, int):
            return False
        elif index > 0 and index <= self.num_of_psus:
            return self.psu_status[index]
        else:
            return False
