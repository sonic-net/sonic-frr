import re
import ipaddress
import socket

HOST = '127.0.0.1'
PORT = 2605

def union_bgp_sessions():
    bgpsumm_ipv4 = show_bgp_summary('ip')
    sessions_ipv4 = parse_bgp_summary(bgpsumm_ipv4)

    bgpsumm_ipv6 = show_bgp_summary('ipv6')
    sessions_ipv6 = parse_bgp_summary(bgpsumm_ipv6)

    # Note: sessions_ipv4 will overwrite sessions_ipv6 if key is the same
    sessions = {}
    for ses in sessions_ipv6 + sessions_ipv4:
        nei = ses['Neighbor']
        sessions[nei] = ses
    return sessions

def vtysh_run(command):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))

    cmd = b"zebra\n" + command.encode() + b"\nexit\n"
    s.send(cmd)

    acc = b""
    while True:
        data = s.recv(1024)
        if not data:
            break
        acc += data

    s.close()
    return acc.decode('ascii', 'ignore')

def show_bgp_summary(ipver):
    assert(ipver in ['ip', 'ipv6'])
    try:
        result = vtysh_run('show %s bgp summary' % ipver)

    except ConnectionRefusedError as e:
        raise RuntimeError('Failed to connect quagga socket') from e
    except OSError as e:
        raise RuntimeError('Socket error when talking with quagga') from e
    return result

def parse_bgp_summary(summ):
    ls = summ.splitlines()
    bgpinfo = []

    ## Read until the table header
    n = len(ls)
    li = 0
    while li < n:
        l = ls[li]
        if l.startswith('Neighbor        '): break
        if l.startswith('No IPv'): # eg. No IPv6 neighbor is configured
            return bgpinfo
        if l.endswith('> exit'): # last command in the lines
            return bgpinfo
        li += 1

    ## Read and store the table header
    if li >= n:
        raise ValueError('No table header found')
    hl = ls[li]
    li += 1
    ht = re.split('\s+', hl.rstrip())
    hn = len(ht)

    ## Read rows in the table
    while li < n:
        l = ls[li]
        li += 1
        if l == '': break

        ## Handle line wrap
        ## ref: bgp_show_summary in https://github.com/Azure/sonic-quagga/blob/debian/0.99.24.1/bgpd/bgp_vty.c
        if ' ' not in l:
            ## Read next line
            if li >= n:
                raise ValueError('Unexpected line wrap')
            l += ls[li]
            li += 1

        ## Note: State/PfxRcd field may be 'Idle (Admin)'
        lt = re.split('\s+', l.rstrip(), maxsplit = hn - 1)
        if len(lt) != hn:
            raise ValueError('Unexpected row in the table')
        dic = dict(zip(ht, lt))
        bgpinfo.append(dic)
    return bgpinfo

STATE_CODE = {
    "Idle": 1,
    "Idle (Admin)": 1,
    "Connect": 2,
    "Active": 3,
    "OpenSent": 4,
    "OpenConfirm": 5,
    "Established": 6
};

def bgp_peer_tuple(dic):
    nei = dic['Neighbor']
    ver = dic['V']
    sta = dic['State/PfxRcd']

    # prefix '*' appears if the entry is a dynamic neighbor
    nei = nei[1:] if nei[0] == '*' else nei
    ip = ipaddress.ip_address(nei)
    if type(ip) is ipaddress.IPv4Address:
        oid_head = (1, 4)
    else:
        oid_head = (2, 16)

    oid_ip = tuple(i for i in ip.packed)

    if sta.isdigit():
        status = 6
    elif sta in STATE_CODE:
        status = STATE_CODE[sta]
    else:
        return None, None

    return oid_head + oid_ip, status

