#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -------------------------- Logging --------------------------------------
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

import sys
import time
import Queue
import inspect
import threading

import pyagentx
from pyagentx.updater import Updater
from pyagentx.network import Network



class AgentError(Exception):
    pass

class Agent(object):

    def __init__(self):
        self.child_abnormal_event = threading.Event()
        self._updater_list = []
        self._sethandlers = {}
        self._threads = []

    def wait_children(self):
        ''' wait for a child abnormal event, the trigger to stop the subagent '''
        logger.info('Waiting for the child abnormal event to stop the subagent')
        self.child_abnormal_event.wait()
        logger.info('event received - about to stop the subagent')
        self.stop()

    def register(self, oid, class_, freq=10):
        if Updater not in inspect.getmro(class_):
            raise AgentError('Class given isn\'t an updater')
        # cleanup and test oid
        try:
            oid = oid.strip(' .')
            [int(i) for i in oid.split('.')]
        except ValueError:
            logger.error('OID isn\'t valid')
            raise AgentError('OID isn\'t valid')
        self._updater_list.append({'oid':oid, 'class':class_, 'freq':freq})

    def register_set(self, oid, class_):
        if pyagentx.SetHandler not in class_.__bases__:
            logger.error('Class given isn\'t a SetHandler')
            raise AgentError('Class given isn\'t a SetHandler')
        # cleanup and test oid
        try:
            oid = oid.strip(' .')
            [int(i) for i in oid.split('.')]
        except ValueError:
            logger.error('OID isn\'t valid')
            raise AgentError('OID isn\'t valid')
        self._sethandlers[oid] = class_()

    def setup(self):
        # Override this
        pass

    def start(self):
        logger.info("Starting the agent...")
        queue = Queue.Queue(maxsize=20)
        self.setup()
        # Start Updaters
        for u in self._updater_list:
            logger.debug('Starting updater [%s]' % u['oid'])
            t = u['class']()
            t.agent_setup(queue, u['oid'], u['freq'])
            t.add_child_abnormal_event(self.child_abnormal_event)
            t.start()
            self._threads.append(t)

        # Start Network
        logger.debug("Starting the network...")
        oid_list = [u['oid'] for u in self._updater_list]
        t = Network(queue, oid_list, self._sethandlers)
        t.start()
        self._threads.append(t)

        # Do nothing ... just wait for someone to stop you
        self.wait_children()

    def stop(self):
        logger.debug('Stop threads')
        for t in self._threads:
            t.stop.set()
        logger.debug('Wait for updater')
        for t in self._threads:
            t.join()
