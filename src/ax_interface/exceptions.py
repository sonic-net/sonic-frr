import struct


class AgentXInterfaceError(Exception):
    """ Base exception class for the AgentX Interface """

    def __init__(self, *args, **kwargs):
        self.inner_exception = kwargs.pop('inner_exception', None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        ret = ''
        if hasattr(self, 'message'):
            ret += self.message
        if self.inner_exception is not None:
            ret += ' inner-exception: [{}]'.format(str(self.inner_exception))


class AgentError(AgentXInterfaceError):
    """ Exception throwable by the Agent class. """


class PDUError(AgentXInterfaceError):
    """ Class of errors related to PDU encoding/decoding. """


class PDUUnpackError(struct.error, PDUError):
    """ Raised when the byte string unpacking fails. """


class PDUPackError(struct.error, PDUError):
    """ Raised when the PDU Encoding (byte packing) fails. """


class UnsupportedPDUError(ValueError, PDUError):
    """ Raised when the PDU type is not a known :class:`PduType`."""
