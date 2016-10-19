import json
import logging.handlers

# path where a user may define an alias map
USER_DEFINED_ALIAS_MAP_FILEPATH = '/etc/snmp/alias_map.json'

# configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.NullHandler())

_if_alias_map = None

# open user-defined alias map first
try:
    with open(USER_DEFINED_ALIAS_MAP_FILEPATH) as f:
        _if_alias_map = json.load(f)
        _if_alias_map = {k.encode('ascii'): v.encode('ascii') for k, v in _if_alias_map.items()}
except ValueError as e:
    logger.error(
        "User map contains error(s). Ensure file is well-formed JSON. Falling back to default map. {}".format(str(e))
    )
except OSError:
    # No alias map found, error is emitted and handled in mibs/__init__.py
    logger.info("No user-defined alias map found, using default map.")
