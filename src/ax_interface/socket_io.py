"""
Agent-X implementation using Async-IO. Based on:
https://docs.python.org/3/library/asyncio-protocol.html#register-an-open-socket-to-wait-for-data-using-a-protocol
and
https://github.com/rayed/pyagentx
"""
import asyncio
import logging

from . import logger, constants
from .protocol import AgentX


class SocketManager:
    # TODO: parameterize
    SOCKET_CONNECT_TIMEOUT = 1  # seconds
    TRY_RETRY_INTERVAL = 3  # seconds
    RETRY_ERROR_THRESHOLD = 10  # seconds

    def __init__(self, mib_table, run_event, loop):

        self.mib_table = mib_table
        self.run_event = run_event
        self.loop = loop

        self.transport = self.ax_socket = None

    async def connection_loop(self):
        """
        Try/Retry connection coroutine to attach the socket.
        """
        failed_connections = 0

        logger.info("Connection loop starting...")
        # keep the connection alive while the agent is running
        while self.run_event.is_set():
            try:
                logger.info("Attempting AgentX socket bind...".format())

                connection_routine = self.loop.create_unix_connection(
                    protocol_factory=lambda: AgentX(self.mib_table, self.loop),
                    path=constants.AGENTX_SOCKET_PATH,
                    sock=self.ax_socket)

                # Initiate the socket connection
                self.transport, protocol = await connection_routine
                logger.info("AgentX socket connection established. Initiating opening handshake...")

                # prime a callback to execute the Opening handshake
                self.loop.call_later(1, protocol.opening_handshake)
                # connection established, wait until the transport closes (or loses connection)
                await protocol.closed.wait()
            except OSError:
                # We couldn't open the socket.
                failed_connections += 1
                # adjust the log level based on how long we've been waiting.
                log_level = logging.WARNING if failed_connections <= SocketManager.RETRY_ERROR_THRESHOLD \
                    else logging.ERROR

                logger.log(log_level, "Socket bind failed. \"Is 'snmpd' running?\". Retrying in {} seconds..." \
                           .format(SocketManager.TRY_RETRY_INTERVAL))
                # try again soon
                await asyncio.sleep(SocketManager.TRY_RETRY_INTERVAL)

        logger.info("Run disabled. Connection loop stopping...")

    def close(self):
        if self.transport is not None:
            # close the transport (it will call connection_lost() and stop the attach_socket routine)
            self.transport.close()
