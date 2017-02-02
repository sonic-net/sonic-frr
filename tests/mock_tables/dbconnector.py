# MONKEY PATCH!!!
import json
import os

import mockredis
import sswsdk.interface
from sswsdk.interface import redis


def _subscribe_keyspace_notification(self, db_name, client):
    pass


def config_set(self, *args):
    pass


INPUT_DIR = os.path.dirname(os.path.abspath(__file__))

class SSWSyncClient(mockredis.MockRedis):
    def __init__(self, *args, **kwargs):
        super(SSWSyncClient, self).__init__(strict=True, *args, **kwargs)
        db = kwargs.pop('db')
        if db == 0:
            with open(INPUT_DIR + '/appl_db.json') as f:
                db = json.load(f)
                for h, table in db.items():
                    for k, v in table.items():
                        self.hset(h, k, v)
        elif db == 1:
            with open(INPUT_DIR + '/asic_db.json') as f:
                db = json.load(f)
                for h, table in db.items():
                    for k, v in table.items():
                        self.hset(h, k, v)
        elif db == 2:
            with open(INPUT_DIR + '/counters_db.json') as f:
                db = json.load(f)
                for h, table in db.items():
                    for k, v in table.items():
                        self.hset(h, k, v)

    # Patch mockredis/mockredis/client.py
    # The official implementation will filter out keys with a slash '/'
    # ref: https://github.com/locationlabs/mockredis/blob/master/mockredis/client.py
    def keys(self, pattern='*'):
        """Emulate keys."""
        import fnmatch
        import re

        # making sure the pattern is unicode/str.
        try:
            pattern = pattern.decode('utf-8')
            # This throws an AttributeError in python 3, or an
            # UnicodeEncodeError in python 2
        except (AttributeError, UnicodeEncodeError):
            pass

        # Make regex out of glob styled pattern.
        regex = fnmatch.translate(pattern)
        regex = re.compile(regex)

        # Find every key that matches the pattern
        return [key for key in self.redis.keys() if regex.match(key.decode('utf-8'))]


sswsdk.interface.DBInterface._subscribe_keyspace_notification = _subscribe_keyspace_notification
mockredis.MockRedis.config_set = config_set
redis.StrictRedis = SSWSyncClient
