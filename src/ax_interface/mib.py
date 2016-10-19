import asyncio
import bisect
import random

from . import util
from .constants import ValueType
from .encodings import ValueRepresentation

"""
Update interval between update runs (in seconds).
"""
DEFAULT_UPDATE_FREQUENCY = 5


class MIBUpdater:
    """
    Interface for developing OID handlers that require persistent (or background) execution.
    """

    def __init__(self):
        self.run_event = asyncio.Event()
        self.frequency = DEFAULT_UPDATE_FREQUENCY

    async def start(self):
        # Run the update while we are allowed
        while self.run_event.is_set():
            # run the background update task
            self.update_data()
            # wait based on our update frequency before executing again.
            # randomize to avoid concurrent update storms.
            await asyncio.sleep(self.frequency + random.randint(-2, 2))

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
        if prefix is not None:
            if not util.is_valid_oid(prefix, dot_prefix=True):
                raise ValueError("Invalid prefix '{}' for class '{}'".format(prefix, name))

            _prefix = util.oid2tuple(prefix)

            # gather all static MIB entries.
            sub_ids = {_prefix + v.sub_id: v for k, v in vars(cls).items() if type(v) is MIBEntry}

            # gather all contextual IDs for each MIB entry--and drop them into the sub-ID listing
            contextual_entries = (v for v in vars(cls).values() if type(v) is ContextualMIBEntry)
            for cme in contextual_entries:
                for sub_id in cme:
                    sub_ids.update({_prefix + sub_id: cme})

            # gather all updater instances
            updaters = set(v for k, v in vars(cls).items() if isinstance(v, MIBUpdater))

            # inherit any MIBs from base classes (if they exist)
            prefixes = [_prefix]
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
        self.sub_id = util.oid2tuple(subtree, dot_prefix=False)

    def __call__(self, sub_id=None):
        return self._callable_.__call__(*self._callable_args)


class ContextualMIBEntry(MIBEntry):
    def __init__(self, subtree, sub_ids, value_type, callable_, *args, updater=None):
        super().__init__(subtree, value_type, callable_, *args)
        self.sub_ids = sub_ids

    def __iter__(self):
        for sub_id in self.sub_ids:
            yield self.sub_id + (sub_id,)

    def __call__(self, sub_id=None):
        return self._callable_.__call__(sub_id, *self._callable_args)


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

    def start_background_tasks(self, event):
        tasks = []
        for updater in self.updater_instances:
            updater.frequency = self.update_frequency
            updater.run_event = event
            fut = event._loop.create_task(updater.start())
            tasks.append(fut)
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

    def get(self, sr, d=None):
        oid_key = sr.start.to_tuple()
        mib_entry = super().get(oid_key)
        if mib_entry is None:
            # no exact OID found
            prefix = self._find_parent_prefix(oid_key)
            if prefix is not None:
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
        else:
            oid_value = mib_entry(oid_key[-1])
            # OID found, call the OIDEntry
            vr = ValueRepresentation(
                mib_entry.value_type if oid_value is not None else ValueType.NO_SUCH_INSTANCE,
                0,  # reserved
                sr.start,
                oid_value
            )
        return vr

    def get_next(self, sr):
        start_key = sr.start.to_tuple()
        end_key = sr.end.to_tuple()
        oid_list = sorted(self.keys())
        if sr.start.include:
            # return the index of an insertion point immediately preceding any duplicate value (thereby including it)
            sorted_start_index = bisect.bisect_left(oid_list, start_key)
        else:
            # return the index of an insertion point immediately following any duplicate value (thereby excluding it)
            sorted_start_index = bisect.bisect_right(oid_list, start_key)

        # slice our MIB by the insertion point.
        remaining_oids = oid_list[sorted_start_index:]

        while remaining_oids and remaining_oids[0] < end_key:
            # we found at least one remaining oid and the first entry in the remaining oid list
            # is less than our end value--it's a match.
            oid_key = remaining_oids[0]
            mib_entry = self[oid_key]
            oid_value = mib_entry(oid_key[-1])
            if oid_value is None:
                # handler returned None, which implies there's no data, keep walking.
                remaining_oids = remaining_oids[1:]
                continue
            else:
                # found a concrete OID value--return it.
                return ValueRepresentation.from_typecast(
                    mib_entry.value_type,
                    oid_key,
                    oid_value
                )

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
