import pprint
import re

from swsssdk import SonicV2Connector

from sonic_ax_impl import logger, _if_alias_map

COUNTERS_PORT_NAME_MAP = b'COUNTERS_PORT_NAME_MAP'
LAG_TABLE = b'LAG_TABLE'
LAG_MEMBER_TABLE = b'LAG_MEMBER_TABLE'
SONIC_ETHERNET_RE_PATTERN = "^Ethernet(\d+)$"
SONIC_PORTCHANNEL_RE_PATTERN = "^PortChannel(\d+)$"
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


def if_entry_table(if_name):
    """
    :param if_name: given interface to cast.
    :return: PORT_TABLE key.
    """
    return b'PORT_TABLE:' + if_name


def lag_entry_table(lag_name):
    """
    :param lag_name: given lag to cast.
    :return: LAG_TABLE key.
    """
    return b'LAG_TABLE:' + lag_name


def get_index(if_name):
    """
    OIDs are 1-based, interfaces are 0-based, return the 1-based index
    Ethernet N = N + 1
    PortChannel N = N + 1000
    """
    return get_index_from_str(if_name.decode())


def get_index_from_str(if_name):
    """
    OIDs are 1-based, interfaces are 0-based, return the 1-based index
    Ethernet N = N + 1
    PortChannel N = N + 1000
    """
    patterns = {
        SONIC_ETHERNET_RE_PATTERN: 1,
        SONIC_PORTCHANNEL_RE_PATTERN: 1000
    }

    for pattern, baseidx in patterns.items():
        match = re.match(pattern, if_name)
        if match:
            return int(match.group(1)) + baseidx


def config(**kwargs):
    global redis_kwargs
    redis_kwargs = {k:v for (k,v) in kwargs.items() if k in ['unix_socket_path', 'host', 'port']}

def init_db():
    """
    Connects to DB
    :return: db_conn
    """
    # SyncD database connector. THIS MUST BE INITIALIZED ON A PER-THREAD BASIS.
    # Redis PubSub objects (such as those within swsssdk) are NOT thread-safe.
    db_conn = SonicV2Connector(**redis_kwargs)

    return db_conn


def init_sync_d_interface_tables(db_conn):
    """
    Initializes interface maps for SyncD-connected MIB(s).
    :return: tuple(if_name_map, if_id_map, oid_map, if_alias_map)
    """

    # Make sure we're connected to COUNTERS_DB
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

    return if_name_map, if_alias_map, if_id_map, oid_sai_map, oid_name_map


def init_sync_d_lag_tables(db_conn):
    """
    Helper method. Connects to and initializes LAG interface maps for SyncD-connected MIB(s).
    :param db_conn: database connector
    :return: tuple(lag_name_if_name_map, if_name_lag_name_map, oid_lag_name_map)
    """
    # { lag_name (SONiC) -> [ lag_members (if_name) ] }
    # ex: { "PortChannel0" : [ "Ethernet0", "Ethernet4" ] }
    lag_name_if_name_map = {}
    # { if_name (SONiC) -> lag_name }
    # ex: { "Ethernet0" : "PortChannel0" }
    if_name_lag_name_map = {}
    # { OID -> lag_name (SONiC) }
    oid_lag_name_map = {}

    db_conn.connect(APPL_DB)

    lag_entries = db_conn.keys(APPL_DB, b"LAG_TABLE:*")

    if not lag_entries:
        return lag_name_if_name_map, if_name_lag_name_map, oid_lag_name_map

    for lag_entry in lag_entries:
        lag_name = lag_entry[len(b"LAG_TABLE:"):]
        lag_members = db_conn.keys(APPL_DB, b"LAG_MEMBER_TABLE:%s:*" % lag_name)

        def member_name_str(val, lag_name):
            return val[len(b"LAG_MEMBER_TABLE:%s:" % lag_name):]

        lag_name_if_name_map[lag_name] = [member_name_str(m, lag_name) for m in lag_members]
        for key, val in lag_name_if_name_map.items():
            if_name_lag_name_map[key] = val

    for if_name in lag_name_if_name_map.keys():
        idx = get_index(if_name)
        if idx:
            oid_lag_name_map[idx] = if_name

    return lag_name_if_name_map, if_name_lag_name_map, oid_lag_name_map
