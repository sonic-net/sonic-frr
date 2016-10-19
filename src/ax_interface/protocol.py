import asyncio

from . import logger, constants, exceptions
from .encodings import ObjectIdentifier
from .pdu import PDUHeader, PDUStream
from .pdu_implementations import RegisterPDU, ResponsePDU, OpenPDU


class AgentX(asyncio.Protocol):
    """
    RFC2741 - compliant AgentX protocol. State machine flow:
        start -> connection_made() [-> data_received() *] [-> eof_received() ?] -> connection_lost() -> end
    """
    transport = None

    def __init__(self, mib_table, loop):
        self.loop = loop
        self.session_id = -1
        self.mib_table = mib_table
        self.closed = asyncio.Event(loop=loop)
        self.counter = 0

    def send_pdu(self, pdu):
        write_bytes = pdu.encode()
        logger.debug("Sending: [{}]".format(write_bytes))
        self.transport.write(write_bytes)

    def connection_made(self, transport):
        self.transport = transport

    def opening_handshake(self):
        logger.info("Sending open...")
        open_pdu = OpenPDU(
            header=PDUHeader(
                1,  # AgentX version 1
                constants.PduTypes.OPEN,
                PDUHeader.MASK_NEWORK_BYTE_ORDER,
                0,  # reserved
                0, 0, 0, 0),  # payload length[3] is overridden by the constructor(s).
            timeout=constants.DEFAULT_PDU_TIMEOUT,
            # https://tools.ietf.org/html/rfc2741#section-6.2.1:
            #   "An Object Identifier that identifies the subagent.
            #   Subagents that do not support such a notion may
            #   send a null Object Identifier."
            oid=ObjectIdentifier.null_oid(),
            descr=constants.SNMP_SUBAGENT_NAME
        )
        self.send_pdu(open_pdu)

    def register_subtrees(self, pdu):
        self.session_id = pdu.header.session_id
        logger.info("AgentX session starting with ID: {}".format(self.session_id))

        for idx, subtree in enumerate(self.mib_table.prefixes):
            logger.debug(subtree)
            oid = ObjectIdentifier.from_iterable(subtree)
            register_pdu = RegisterPDU(
                header=pdu.header,
                timeout=constants.DEFAULT_PDU_TIMEOUT,
                priority=idx,  # Lower index in the subtree list, higher priority.
                range_subid=0,
                subtree=oid,
            )
            logger.info("Registering subID: [{}]".format(oid))
            logger.debug(repr(oid))
            self.send_pdu(register_pdu)

        logger.info("OID registration complete. Waiting to receive PDUs...")

    def parse_response(self, pdu):
        # no session established,
        if self.session_id == -1:
            if pdu.error == ResponsePDU.Errors.PARSE_ERROR:
                logger.error("Master Agent failed to parse OpenPDU, closing.")
                self.transport.close()
            elif pdu.error == ResponsePDU.Errors.OPEN_FAILED:
                logger.error("Master Agent open session, closing.")
            elif pdu.error == ResponsePDU.Errors.NO_AGENT_X_ERROR:
                # No error! Start registering our subtree(s)
                self.register_subtrees(pdu)
            else:
                raise exceptions.AgentError("Session ID uninitialized with inconsistent Response PDU [{}]".format(pdu))
        else:
            # TODO: some other administrative PDU
            logger.debug("admin_recv[{}]".format(pdu))
            pass

    def data_received(self, data):
        """
        From https://tools.ietf.org/html/rfc2741#section-7.2.2:

        -  If the received PDU is an agentx-Response-PDU:

        1) If there are any errors parsing or interpreting the PDU, it is
          silently dropped.

        2) Otherwise the response is matched to the original request via
          h.packetID, and handled in an implementation-specific manner.  For
          example, if this response indicates an error attempting to
          register a MIB region, the subagent may wish to register a
          different region, or log an error and halt, etc.

        -  If the received PDU is any other type:

        1) an agentx-Response-PDU is created whose header fields are
          identical to the received request PDU except that h.type is set to
          Response, res.error to `noError', res.index to 0, and the
          VarBindList to null.

        2) If the received PDU cannot be parsed, res.error is set to
          `parseError'.

        3) Otherwise, if h.sessionID does not correspond to a currently
          established session, res.error is set to `notOpen'.

        4) At this point, if res.error is not `noError', the received PDU is
          not processed further.  If the received PDU's header was
          successfully parsed, the AgentX-Response-PDU is sent in reply.  If
          the received PDU's header was not successfully parsed or for some
          other reason the subagent cannot send a reply, processing is
          complete.

        :param data: Socket stream data (as byte string)
        """
        self.counter += 1
        if not (self.counter % constants.REPORTING_FREQUENCY):
            # Stayin' alive...Stayin' alive...
            # Ahh, ahh, ahh, ahh
            logger.debug("Parsed {} PDUs...".format(self.counter))
        try:
            # each PDU type implements it's own subclass and will be inferred at construction.
            pdu_stream = PDUStream(data)
            for pdu in pdu_stream:
                if isinstance(pdu, ResponsePDU):
                    # parse the response
                    self.parse_response(pdu)
                else:
                    # a response will be returned if the current PDU warrants a response
                    response_pdu = pdu.make_response(self.mib_table)
                    self.transport.write(response_pdu.encode())
        except exceptions.PDUUnpackError:
            logger.exception('decode_error[{}]'.format(data))
        except exceptions.PDUPackError:
            logger.exception('encode_error[{}]'.format(data))
        except Exception:
            logger.exception("Uncaught AgentX proto error! [{}]".format(data))

    def pause_writing(self):
        logger.warning("AgentX buffer above high-water mark. Suspending PDU processing.")

    def resume_writing(self):
        logger.warning("AgentX buffer below high-water mark. Resuming PDU processing.")

    def connection_lost(self, exc):
        # The socket has been closed
        logger.info("AgentX socket connection closed.")
        if isinstance(exc, Exception):
            logger.error(exc)
        self.closed.set()
