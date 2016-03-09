#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -------------------------- Logging --------------------------------------
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

import sys
import time
import threading
import Queue

import pyagentx


class Updater(threading.Thread):

    def add_child_abnormal_event(self, event):
        ''' Add the child abnormal event '''
        logger.info('Add the child abnormal event')
        self.child_abnormal_event = event

    def notify(self):
        ''' Notify the main process the child abnormal event occurred '''
        logger.info('The child_abnormal_event occurred, notify to stop the subagent')
        self.child_abnormal_event.set()

    def agent_setup(self, queue, oid, freq):
        self.stop = threading.Event()
        self._queue = queue
        self._oid = oid
        self._freq = freq
        self._data = {}

    def run(self):
        start_time = 0
        logger.info("Starting an updater ...")
        while True:
            if self.stop.is_set(): break
            now = time.time()
            if now - start_time > self._freq:
                logger.debug('Updating : %s (%s)' % (self.__class__.__name__, self._oid))
                start_time = now
                self._data = {}
                try:
                    self.update()
                    self._queue.put_nowait({'oid': self._oid,
                                            'data':self._data})
                except Queue.Full:
                    logger.error('Queue full')
                    time.sleep(5)
                except:
                    logger.exception('Unhandled update exception')
                    self.notify()
                    
            time.sleep(0.1)
        logger.info('Updating stopped ...')

    # Override this
    def update(self):
        pass

    def set_INTEGER(self, oid, value):
        logger.debug('Setting INTEGER %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_INTEGER, 'value':value}

    def set_OCTETSTRING(self, oid, value):
        logger.debug('Setting OCTETSTRING %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_OCTETSTRING, 'value':value}

    def set_OBJECTIDENTIFIER(self, oid, value):
        logger.debug('Setting OBJECTIDENTIFIER %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_OBJECTIDENTIFIER, 'value':value}

    def set_IPADDRESS(self, oid, value):
        logger.debug('Setting IPADDRESS %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_IPADDRESS, 'value':value}

    def set_COUNTER32(self, oid, value):
        logger.debug('Setting COUNTER32 %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_COUNTER32, 'value':value}

    def set_GAUGE32(self, oid, value):
        logger.debug('Setting GAUGE32 %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_GAUGE32, 'value':value}

    def set_TIMETICKS(self, oid, value):
        logger.debug('Setting TIMETICKS %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_TIMETICKS, 'value':value}

    def set_OPAQUE(self, oid, value):
        logger.debug('Setting OPAQUE %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_OPAQUE, 'value':value}

    def set_COUNTER64(self, oid, value):
        logger.debug('Setting COUNTER64 %s = %s' % (oid, value))
        self._data[oid] = {'name': oid, 'type':pyagentx.TYPE_COUNTER64, 'value':value}


