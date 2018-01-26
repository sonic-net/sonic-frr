import pprint
import re

from swsssdk import SonicV2Connector
from swsssdk import port_util
from swsssdk.port_util import get_index, get_index_from_str
from sonic_ax_impl import logger, _if_alias_map

COUNTERS_PORT_NAME_MAP = b'COUNTERS_PORT_NAME_MAP'
COUNTERS_QUEUE_NAME_MAP = b'COUNTERS_QUEUE_NAME_MAP'
LAG_TABLE = b'LAG_TABLE'
LAG_MEMBER_TABLE = b'LAG_MEMBER_TABLE'
APPL_DB = 'APPL_DB'
ASIC_DB = 'ASIC_DB'
COUNTERS_DB = 'COUNTERS_DB'

redis_kwargs = {'unix_socket_path': '/var/run/redis/redis.sock'}

def counter_table(sai_id):
    """
    :param if_name: given sai_id to cast.
    :return: COUNTERS table key.
    """
    return b'COUNTERS:oid:0x' + sai_id

def queue_table(sai_id):
    """
    :param sai_id: given sai_id to cast.
    :return: COUNTERS table key.
    """
    return b'COUNTERS:' + sai_id

def queue_key(port_index, queue_index):
    return str(port_index) + ':' + str(queue_index)


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
    if_name_map, if_id_map = port_util.get_interface_oid_map(db_conn)
    logger.debug("Port name map:\n" + pprint.pformat(if_name_map, indent=2))
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
            .format(port_util.SONIC_ETHERNET_RE_PATTERN)
        logger.error(message)
        raise RuntimeError(message)
    elif len(if_id_map) < len(if_name_map) or len(oid_sai_map) < len(if_name_map):
        # a length mismatch indicates a bad interface name
        logger.warning("SyncD database contains incoherent interface names. Interfaces must match pattern '{}'"
                       .format(port_util.SONIC_ETHERNET_RE_PATTERN))
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
        # TODO: db_conn.keys() should really return [] instead of None
        if lag_members is None:
            lag_members = []

        def member_name_str(val, lag_name):
            return val[len(b"LAG_MEMBER_TABLE:%s:" % lag_name):]

        lag_member_names = [member_name_str(m, lag_name) for m in lag_members]
        lag_name_if_name_map[lag_name] = lag_member_names
        for lag_member_name in lag_member_names:
            if_name_lag_name_map[lag_member_name] = lag_name

    for if_name in lag_name_if_name_map.keys():
        idx = get_index(if_name)
        if idx:
            oid_lag_name_map[idx] = if_name

    return lag_name_if_name_map, if_name_lag_name_map, oid_lag_name_map

def init_sync_d_queue_tables(db_conn):
    """
    Initializes queue maps for SyncD-connected MIB(s).
    :return: tuple(port_queues_map, queue_stat_map)
    """

    # Make sure we're connected to COUNTERS_DB
    db_conn.connect(COUNTERS_DB)

    # { Port index : Queue index (SONiC) -> sai_id }
    # ex: { "1:2" : "1000000000023" }
    queue_name_map = db_conn.get_all(COUNTERS_DB, COUNTERS_QUEUE_NAME_MAP, blocking=True)
    logger.debug("Queue name map:\n" + pprint.pformat(queue_name_map, indent=2))

    # Parse the queue_name_map and create the following maps:
    # port_queues_map -> {"if_index : queue_index" : sai_oid}
    # queue_stat_map -> {queue stat table name : {counter name : value}}
    # port_queue_list_map -> {if_index: [sorted queue list]}
    port_queues_map = {}
    queue_stat_map = {}
    port_queue_list_map = {}

    for queue_name, sai_id in queue_name_map.items():
        port_name, queue_index = queue_name.decode().split(':')
        queue_index = ''.join(i for i in queue_index if i.isdigit())
        port_index = get_index_from_str(port_name)
        key = queue_key(port_index, queue_index)
        port_queues_map[key] = sai_id

        queue_stat_name = queue_table(sai_id)
        queue_stat = db_conn.get_all(COUNTERS_DB, queue_stat_name, blocking=False)
        if queue_stat is not None:
            queue_stat_map[queue_stat_name] = queue_stat

        if not port_queue_list_map.get(int(port_index)):
            port_queue_list_map[int(port_index)] = [int(queue_index)]
        else:
            port_queue_list_map[int(port_index)].append(int(queue_index))

    # SyncD consistency checks.
    if not port_queues_map:
        # In the event no queue exists that follows the SONiC pattern, no OIDs are able to be registered.
        # A RuntimeError here will prevent the 'main' module from loading. (This is desirable.)
        logger.error("No queues found in the Counter DB. SyncD database is incoherent.")
        raise RuntimeError('The port_queues_map is not defined')
    elif not queue_stat_map:
        logger.error("No queue stat counters found in the Counter DB. SyncD database is incoherent.")
        raise RuntimeError('The queue_stat_map is not defined')

    for queues in port_queue_list_map.values():
        queues.sort()

    return port_queues_map, queue_stat_map, port_queue_list_map

