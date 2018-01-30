from enum import Enum, unique
from bisect import bisect_right
import subprocess

from swsssdk import SonicV2Connector
from ax_interface import MIBMeta, MIBUpdater, ValueType, SubtreeMIBEntry


@unique
class PhysicalClass(int, Enum):
    """
    Physical classes defined in RFC 2737.
    """
    OTHER = 1
    UNKNOWN = 2
    CHASSIS = 3
    BACKPLANE = 4
    CONTAINER = 5
    POWERSUPPLY = 6
    FAN = 7
    SENSOR = 8
    MODULE = 9
    PORT = 10
    STACK = 11


class PhysicalTableMIBUpdater(MIBUpdater):

    DEVICE_METADATA = "DEVICE_METADATA|localhost"
    CHASSIS_ID = 1

    def __init__(self):
        super().__init__()

        self.statedb = SonicV2Connector()
        self.statedb.connect(self.statedb.STATE_DB)

        # List of available sub IDs.
        self.physical_classes = []
        # Map sub ID to its data.
        self.physical_classes_map = {}

    def reinit_data(self):
        """
        Re-initialize all data.
        """
        device_metadata = self.statedb.get_all(self.statedb.STATE_DB, self.DEVICE_METADATA)

        # TODO: Add support for unicode in swsssdk
        chassis_serial_number = ""
        if not device_metadata or not device_metadata.get(b"chassis_serial_number"):
            chassis_serial_number = ""
        else:
            chassis_serial_number = device_metadata[b"chassis_serial_number"]
            self.physical_classes = [(self.CHASSIS_ID, )]
            self.physical_classes_map = {
                    (self.CHASSIS_ID, ): (PhysicalClass.CHASSIS, chassis_serial_number.decode("utf-8"))
                }

    def update_data(self):
        """
        Update cache.
        NOTE: Nothing to update right now. Implementation is required by framework.
        """
        pass

    def get_next(self, sub_id):
        """
        :param sub_id: The 1-based sub-identifier query.
        :return: the next sub id.
        """
        right = bisect_right(self.physical_classes, sub_id)
        if right == len(self.physical_classes):
            return None
        return self.physical_classes[right]


    def get_physical_class(self, sub_id):
        """
        Get physical class ID for specified subid.
        :param sub_id: The 1-based sub-identifier query. 
        :return: Physical class ID. 
        """
        data = self.physical_classes_map.get(sub_id)
        if not data:
            return None

        return data[0]

    def get_serial_number(self, sub_id):
        """
        Get serial number for specified subid.
        :param sub_id: The 1-based sub-identifier query. 
        :return: Serial number. 
        """
        data = self.physical_classes_map.get(sub_id)
        if not data:
            return None

        return data[1]


class PhysicalTableMIB(metaclass=MIBMeta, prefix='.1.3.6.1.2.1.47.1.1.1'):
    updater = PhysicalTableMIBUpdater()

    entPhysicalClass = \
        SubtreeMIBEntry('1.5', updater, ValueType.INTEGER, updater.get_physical_class)

    entPhysicalSerialNum = \
        SubtreeMIBEntry('1.11', updater, ValueType.OCTET_STRING, updater.get_serial_number)
