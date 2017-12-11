import sys
import asyncio
import bisect
import random
import logging

from . import util
from . import logger

from .constants import ValueType
from .encodings import ValueRepresentation

"""
Update interval between update runs (in seconds).
"""
DEFAULT_UPDATE_FREQUENCY = 5

"""
Interval between reinit runs (in seconds).
"""
DEFAULT_REINIT_RATE = 60

class MIBUpdater:
    """
    Interface for developing OID handlers that require persistent (or background) execution.
    """

    def __init__(self):
        self.run_event = asyncio.Event()
        self.frequency = DEFAULT_UPDATE_FREQUENCY
        self.reinit_rate = DEFAULT_REINIT_RATE // DEFAULT_UPDATE_FREQUENCY
        self.update_counter = self.reinit_rate + 1 # reinit_data when init

    async def start(self):
        # Run the update while we are allowed
        while self.run_event.is_set():
            # reinit internal structures
            if self.update_counter > self.reinit_rate:
                self.reinit_data()
                self.update_counter = 0
            else:
                self.update_counter += 1
            # run the background update task
            try:
                self.update_data()
            except Exception:
                # Any other exception or error, log it and keep running
                logger.exception("MIBUpdater.start() caught an unexpected exception")

            # wait based on our update frequency before executing again.
            # randomize to avoid concurrent update storms.
            await asyncio.sleep(self.frequency + random.randint(-2, 2))

    def reinit_data(self):
        """
        Reinit task. Children may override this method.
        """
        return

    def update_data(self):
        """
        Background task. Children must override this method.
        """
        raise NotImplementedError()


class MIBMeta(type):
    KEYSTORE = '__subids__'
    PREFIXES = '__subtrees__'
    UPDATERS = '__updaters__'

    def __new__(mcs, name, bases, attributes, prefix=None):
        cls = type.__new__(mcs, name, bases, attributes)

        # each object-type, ie. MIBEntry will has a prefix
        # ref: https://tools.ietf.org/html/rfc2741#section-2.1
        prefixes = []

        if prefix is not None:
            if not util.is_valid_oid(prefix, dot_prefix=True):
                raise ValueError("Invalid prefix '{}' for class '{}'".format(prefix, name))

            _prefix = util.oid2tuple(prefix)
            _prefix_len = len(_prefix)
            for me in vars(cls).values():
                if isinstance(me, MIBEntry):
                    setattr(me, MIBEntry.PREFIXLEN, _prefix_len + len(me.subtree))

            sub_ids = {}

            # gather all static MIB entries.
            static_entries = (v for v in vars(cls).values() if type(v) is MIBEntry)
            for me in static_entries:
                sub_ids.update({_prefix + me.subtree: me})
                prefixes.append(_prefix + me.subtree)

            # gather all subtree IDs
            # to support dynamic sub_id in the subtree, not to pour leaves into dictionary
            subtree_entries = (v for v in vars(cls).values() if type(v) is SubtreeMIBEntry)
            for sme in subtree_entries:
                sub_ids.update({_prefix + sme.subtree: sme})
                prefixes.append(_prefix + sme.subtree)

            # gather all updater instances
            updaters = set(v for k, v in vars(cls).items() if isinstance(v, MIBUpdater))

        else:
            # wrapper classes should omit the prefix.
            sub_ids = {}
            updaters = set()
            prefixes = []

        for base_cls in bases:
            # Gather any inherited MIBs
            sub_ids.update(getattr(base_cls, MIBMeta.KEYSTORE, {}))
            # Python multiple-inheritance is processed right-to-left.
            # "Pushing" to the front of the subtree list ensures that the "priority"
            # is ordered left-to-right.
            prefixes = getattr(base_cls, MIBMeta.PREFIXES, []) + prefixes
            updaters |= getattr(base_cls, MIBMeta.UPDATERS, set())

        # attach the MIB mappings
        setattr(cls, MIBMeta.KEYSTORE, sub_ids)
        setattr(cls, MIBMeta.PREFIXES, prefixes)
        setattr(cls, MIBMeta.UPDATERS, updaters)
        # class construction complete.
        return cls

    def __init__(cls, name, bases, attributes, prefix=None):
        # type only expects three arguments, '__init__' must be implemented to "pop" 'prefix'.
        type.__init__(cls, name, bases, attributes)


class MIBEntry:
    PREFIXLEN = '__prefixlen__'

    def __init__(self, subtree, value_type, callable_, *args):
        """
        MIB Entry namespace container. Associates a particular OID subtree to a ValueType return and a callable
        object that provides the given information. Optionally, a persistent updater may be specified if the
        data objects require caching.

        :param subtree:
        :param value_type:
        :param callable_:
        :param args:
        :param updater:
        """
        if not util.is_valid_oid(subtree):
            raise ValueError("Invalid sub identifier: '{}'".format(subtree))
        if type(value_type) is not ValueType:
            raise ValueError("Second argument expected 'ValueType'")
        if not callable(callable_):
            raise ValueError("Third argument must be a callable object--got literal instead.")
        self._callable_ = callable_
        self._callable_args = args
        self.subtree = subtree
        self.value_type = value_type
        self.subtree = util.oid2tuple(subtree, dot_prefix=False)

    def __iter__(self):
        yield ()

    def __call__(self, sub_id=None):
        return self._callable_.__call__(*self._callable_args)

    def get_sub_id(self, oid_key):
        return oid_key[getattr(self, MIBEntry.PREFIXLEN):]

    def replace_sub_id(self, oid_key, sub_id):
        return oid_key[:getattr(self, MIBEntry.PREFIXLEN)] + sub_id

    def get_next(self, sub_id):
        return None

class SubtreeMIBEntry(MIBEntry):
    def __init__(self, subtree, iterator, value_type, callable_, *args, updater=None):
        super().__init__(subtree, value_type, callable_, *args)
        self.iterator = iterator

    def __iter__(self):
        sub_id = ()
        while True:
            sub_id = self.iterator.get_next(sub_id)
            if sub_id is None:
                break
            yield sub_id

    def __call__(self, sub_id):
        assert isinstance(sub_id, tuple)
        return self._callable_.__call__(sub_id, *self._callable_args)

    def get_next(self, sub_id):
        return self.iterator.get_next(sub_id)


class MIBTable(dict):
    """
    Simplistic LUT for Get/GetNext OID. Interprets iterables as keys and implements the same interfaces as dict's.
    """

    def __init__(self, mib_cls, update_frequency=DEFAULT_UPDATE_FREQUENCY):
        if type(mib_cls) is not MIBMeta:
            raise ValueError("Supplied object is not a MIB class instance.")
        super().__init__(getattr(mib_cls, MIBMeta.KEYSTORE))
        self.update_frequency = update_frequency
        self.updater_instances = getattr(mib_cls, MIBMeta.UPDATERS)
        self.prefixes = getattr(mib_cls, MIBMeta.PREFIXES)

    def _done_background_task_callback(fut):
        ex = fut.exception()
        if ex is not None:
            exstr = "MIBTable background task caught an unexpected exception: {}".format(str(ex))
            logger.error(exstr)

    def start_background_tasks(self, event):
        tasks = []
        for updater in self.updater_instances:
            updater.frequency = self.update_frequency
            updater.run_event = event
            fut = asyncio.ensure_future(updater.start())
            fut.add_done_callback(MIBTable._done_background_task_callback)
            task = event._loop.create_task(fut)
            tasks.append(task)
        return asyncio.gather(*tasks, loop=event._loop)

    def _find_parent_prefix(self, item):
        oids = sorted(self.prefixes)
        left_insert_index = bisect.bisect(oids, item)
        preceding_oids = oids[:left_insert_index]
        if not preceding_oids:
            return None
        if preceding_oids[-1] == item[:len(preceding_oids[-1])]:
            return preceding_oids[-1]
        else:
            return None

    def _find_parent_oid_key(self, oid_key):
        oids = sorted(self)

    def _get_value(self, mib_entry, oid_key):
        sub_id = mib_entry.get_sub_id(oid_key)
        oid_value = mib_entry(sub_id)
        if oid_value is None:
            return None
        # OID found, call the OIDEntry
        vr = ValueRepresentation.from_typecast(mib_entry.value_type, oid_key, oid_value)
        return vr

    def _get_nextvalue(self, mib_entry, oid_key):
        sub_id = mib_entry.get_sub_id(oid_key)
        key1 = mib_entry.get_next(sub_id)
        if key1 is None:
            return None
        val1 = mib_entry(key1)
        if val1 is None:
            return None
        oid1 = mib_entry.replace_sub_id(oid_key, key1)
        # OID found, call the OIDEntry
        vr = ValueRepresentation.from_typecast(mib_entry.value_type, oid1, val1)
        return vr

    def get(self, sr, d=None):
        oid_key = sr.start.to_tuple()

        # find the best match prefix, either a exact match or a parent prefix
        prefix = self._find_parent_prefix(oid_key)
        if prefix is not None:
            parent_mib_entry = super().get(prefix)
            vr = self._get_value(parent_mib_entry, oid_key)
            if vr is not None:
                return vr
            # we found a prefix. E.g. (1,2,3) is a prefix to OID (1,2,3,1)
            value_type = ValueType.NO_SUCH_INSTANCE
        else:
            # couldn't find the exact OID, or a valid prefix
            value_type = ValueType.NO_SUCH_OBJECT

        vr = ValueRepresentation(
            value_type,
            0,  # reserved
            sr.start,
            None,  # null value
        )
        return vr

    def get_next(self, sr):
        start_key = sr.start.to_tuple()
        end_key = sr.end.to_tuple()
        oid_list = sorted(self.prefixes)

        # find the best match prefix, either a exact match or a parent prefix
        prefix = self._find_parent_prefix(start_key)
        if prefix is not None:
            parent_mib_entry = super().get(prefix)

            if sr.start.include:
                vr = self._get_value(parent_mib_entry, start_key)
                if vr is not None:
                    return vr

            vr = self._get_nextvalue(parent_mib_entry, start_key)
            if vr is not None:
                return vr

        # return the index of an insertion point immediately following any duplicate value (thereby excluding it)
        sorted_start_index = bisect.bisect_right(oid_list, start_key)

        # slice our MIB by the insertion point.
        remaining_oids = oid_list[sorted_start_index:]

        while remaining_oids and remaining_oids[0] < end_key:
            # we found at least one remaining oid and the first entry in the remaining oid list
            # is less than our end value--it's a match.
            oid_key = remaining_oids[0]
            mib_entry = self[oid_key]
            try:
                key1 = next(iter(mib_entry)) # get the first sub_id from the mib_etnry
            except StopIteration:
                # handler returned None, which implies there's no data, keep walking.
                remaining_oids = remaining_oids[1:]
                continue

            val1 = mib_entry(key1)
            if val1 is None:
                logger.error('MIBTable.get_next found an invalid key: {}+{}'.format(mib_entry.subtree, key1))
                remaining_oids = remaining_oids[1:]
                continue

            oid1 = mib_entry.replace_sub_id(oid_key, key1)

            # found a concrete OID value--return it.
            vr = ValueRepresentation.from_typecast(
                mib_entry.value_type,
                oid1,
                val1
            )
            return vr

        # exhausted all remaining OID options--we're at the end of the MIB view.
        return ValueRepresentation(
            ValueType.END_OF_MIB_VIEW,
            0,  # reserved
            sr.start,
            None,  # null value
        )

    def __setitem__(self, key, value):
        if not hasattr(value, '__iter__'):
            raise ValueError("Invalid key '{}'. All keys must be iterable types.".format(key))
        super().__setitem__(key, value)
