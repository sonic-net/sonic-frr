import pprint
import re

from sswsdk import SonicV2Connector

from sonic_ax_impl import logger, _if_alias_map

COUNTERS_PORT_NAME_MAP = b'COUNTERS_PORT_NAME_MAP'
SONIC_ETHERNET_RE_PATTERN = "^Ethernet(\d+)$"
APPL_DB = 'APPL_DB'
ASIC_DB = 'ASIC_DB'
COUNTERS_DB = 'COUNTERS_DB'

redis_kwargs = {'unix_socket_path': '/var/run/redis/redis.sock'}

def counter_table(sai_id):
    """
    :param if_name: given sai_id to cast.
    :return: COUNTERS table key.
    """
    return b'COUNTERS:' + sai_id


def lldp_entry_table(if_name):
    """
    :param if_name: given interface to cast.
    :return: LLDP_ENTRY_TABLE key.
    """
    return b'LLDP_ENTRY_TABLE:' + if_name


def get_index(if_name):
    """
    OIDs are 1-based, interfaces are 0-based, return the 1-based index
    Ethernet N = N + 1
    """
    match = re.match(SONIC_ETHERNET_RE_PATTERN, if_name.decode())
    if match:
        n = match.group(1)
        return int(n) + 1


def config(**kwargs):
    global redis_kwargs
    redis_kwargs = {k:v for (k,v) in kwargs.items() if k in ['unix_socket_path', 'host', 'port']}

def init_sync_d_interface_tables():
    """
    DRY helper method. Connects to and initializes interface maps for SyncD-connected MIB(s).
    :return: tuple(db_conn, if_name_map, if_id_map, oid_map, if_alias_map)
    """
    # SyncD database connector. THIS MUST BE INITIALIZED ON A PER-THREAD BASIS.
    # Redis PubSub objects (such as those within sswsdk) are NOT thread-safe.
    db_conn = SonicV2Connector(**redis_kwargs)
    db_conn.connect(COUNTERS_DB)

    # { if_name (SONiC) -> sai_id }
    # ex: { "Ethernet76" : "1000000000023" }
    if_name_map = db_conn.get_all(COUNTERS_DB, COUNTERS_PORT_NAME_MAP, blocking=True)
    logger.debug("Port name map:\n" + pprint.pformat(if_name_map, indent=2))

    # { sai_id -> if_name (SONiC) }
    if_id_map = {sai_id: if_name for if_name, sai_id in if_name_map.items()
                 # only map the interface if it's a style understood to be a SONiC interface.
                 if get_index(if_name) is not None}
    logger.debug("Interface name map:\n" + pprint.pformat(if_id_map, indent=2))

    # { OID -> sai_id }
    oid_sai_map = {get_index(if_name): sai_id for if_name, sai_id in if_name_map.items()
                   # only map the interface if it's a style understood to be a SONiC interface.
                   if get_index(if_name) is not None}
    logger.debug("OID sai map:\n" + pprint.pformat(oid_sai_map, indent=2))

    # { OID -> if_name (SONiC) }
    oid_name_map = {get_index(if_name): if_name for if_name in if_name_map
                    # only map the interface if it's a style understood to be a SONiC interface.
                    if get_index(if_name) is not None}

    logger.debug("OID name map:\n" + pprint.pformat(oid_name_map, indent=2))

    # SyncD consistency checks.
    if not oid_sai_map:
        # In the event no interface exists that follows the SONiC pattern, no OIDs are able to be registered.
        # A RuntimeError here will prevent the 'main' module from loading. (This is desirable.)
        message = "No interfaces found matching pattern '{}'. SyncD database is incoherent." \
            .format(SONIC_ETHERNET_RE_PATTERN)
        logger.error(message)
        raise RuntimeError(message)
    elif len(if_id_map) < len(if_name_map) or len(oid_sai_map) < len(if_name_map):
        # a length mismatch indicates a bad interface name
        logger.warning("SyncD database contains incoherent interface names. Interfaces must match pattern '{}'"
                       .format(SONIC_ETHERNET_RE_PATTERN))
        logger.warning("Port name map:\n" + pprint.pformat(if_name_map, indent=2))

    # { SONiC name -> optional rename }
    if_alias_map = _if_alias_map
    logger.debug("Chassis name map:\n" + pprint.pformat(if_alias_map, indent=2))
    if if_alias_map is None or len(if_alias_map) == 0:
        logger.warning("No alias map found--port names will use SONiC names.")
        if_alias_map = dict(zip(if_name_map.keys(), if_name_map.keys()))

    return db_conn, if_name_map, if_alias_map, if_id_map, oid_sai_map, oid_name_map
