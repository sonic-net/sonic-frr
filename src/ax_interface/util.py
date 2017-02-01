import re

from ax_interface import constants


def oid2tuple(oid_str, dot_prefix=True):
    """
    >>> oid2tuple('.1.3.6.1.4.1.6027.3.10.1.2.9')
    (1, 3, 6, 1, 4, 1, 6027, 3, 10, 1, 2, 9)
    >>> oid2tuple('1.2.3.4')
    (1, 3, 6, 1, 1, 2, 3, 4)
    >>> oid2tuple('1.2.3.4', dot_prefix=False)
    (1, 2, 3, 4)

    :param oid_str: dot-delimited OID string
    :param dot_prefix: if True, the absence of a leading dot will prepend the internet prefix to the OID.
    :return: the OID (as tuple)
    """
    if not oid_str:
        return ()

    # Validate OID before attempting to process.
    if not is_valid_oid(oid_str, dot_prefix):
        raise ValueError("Invalid OID string.")

    sub_ids = ()
    if dot_prefix:
        if oid_str.startswith('.'):
            # the OID starts with a '.' so, we will interpret it literally.
            oid_str = oid_str[1:]
        else:
            # no '.', prepend the internet prefix
            sub_ids = constants.INTERNET_PREFIX

    sub_ids += tuple(int(sub_id) for sub_id in oid_str.split('.'))

    return sub_ids


def is_valid_oid(oid_str, dot_prefix=True):
    """
    >>> is_valid_oid('2')
    True
    >>> is_valid_oid('2.')
    False
    >>> is_valid_oid('.2')
    True
    >>> is_valid_oid('.2.2')
    True
    >>> is_valid_oid('.2.2.')
    False
    >>> is_valid_oid('.2.2.3', False)
    False

    A valid OID contains:
    1. zero or one leading '.' (dot);
    2. any number of groups with variable length decimals followed by a '.' (dot);
    3. concluded by a variable length decimal.
    :param oid_str: string to validate
    :return: boolean indicating if the oid is valid.
    """
    oid_regex = r'((\d+\.)*\d+)'
    if dot_prefix:
        oid_regex = r'\.?' + oid_regex
    m = re.match(oid_regex, oid_str)
    return m is not None and m.group() == oid_str


def pad4(length):
    """
    >>> pad4(9)
    3
    >>> pad4(20)
    0

    :param length:
    :return:
    """
    return -(length % -4)


def pad4bytes(length):
    """
    >>> pad4bytes(11)
    b\'\\x00\'
    >>> pad4bytes(40)
    b\'\'

    :param length:
    :return:
    """
    return pad4(length) * constants.RESERVED_ZERO_BYTE

def mac_decimals(mac):
    """
    >>> mac_decimals("52:54:00:57:59:6A")
    (82, 84, 0, 87, 89, 106)
    """
    return tuple(int(h, 16) for h in mac.split(":"))

