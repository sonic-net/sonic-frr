import asyncio

from .mib import MIBTable, MIBMeta
from .socket_io import SocketManager

# how long to wait before forcibly killing background task(s) during the shutdown procedure.
BACKGROUND_WAIT_TIMEOUT = 10  # seconds


class Agent:
    def __init__(self, mib_cls, update_frequency, loop):
        if not type(mib_cls) is MIBMeta:
            raise ValueError("Expected a class with type: {}".format(MIBMeta))

        self.loop = loop

        # synchronization events
        self.run_enabled = asyncio.Event(loop=loop)
        self.oid_updaters_enabled = asyncio.Event(loop=loop)
        self.stopped = asyncio.Event(loop=loop)

        # Initialize our MIB
        self.mib_table = MIBTable(mib_cls, update_frequency)

        # containers
        self.socket_mgr = SocketManager(self.mib_table, self.run_enabled, self.loop)

    async def run_in_event_loop(self):
        # starting up, set the enabled signals for the Agent and background tasks
        self.run_enabled.set()
        self.oid_updaters_enabled.set()
        self.stopped.clear()

        # run while
        while self.run_enabled.is_set():
            # start the MIB updater(s) and remember the future obj.
            background_task = self.mib_table.start_background_tasks(self.oid_updaters_enabled)
            # wait for the socket manager to close
            await self.socket_mgr.connection_loop()

            #
            # Main thread will block here until the connection closes.
            # When this await is passed, we enter the shutdown phase.
            #

            # signal background tasks to halt
            self.oid_updaters_enabled.clear()
            # wait for handlers to come back
            await asyncio.wait_for(background_task, BACKGROUND_WAIT_TIMEOUT, loop=self.loop)

        # signal that we're done!
        self.stopped.set()

    async def shutdown(self):
        # allow the agent to quit
        self.run_enabled.clear()
        # close the socket
        self.socket_mgr.close()
        # wait for the agent to signal back
        await self.stopped.wait()
