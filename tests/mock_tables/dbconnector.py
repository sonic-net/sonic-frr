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
        elif db == 2:
            with open(INPUT_DIR + '/counters_db.json') as f:
                db = json.load(f)
                for h, table in db.items():
                    for k, v in table.items():
                        self.hset(h, k, v)


sswsdk.interface.DBInterface._subscribe_keyspace_notification = _subscribe_keyspace_notification
mockredis.MockRedis.config_set = config_set
redis.StrictRedis = SSWSyncClient