## SNMP Subagent

[AgentX](https://www.ietf.org/rfc/rfc2741.txt) implementation for SONiC Switch State Service. See the [SONiC website](http://azure.github.io/SONiC/) for more information on the SONiC project.

MIB implementations included:

* [RFC 1213](https://www.ietf.org/rfc/rfc1213.txt) MIB-II
* [RFC 2863](https://www.ietf.org/rfc/rfc2863.txt) Interfaces MIB
* [RFC 4292](https://tools.ietf.org/html/rfc4292) ipCidrRouteDest table in IP Forwarding Table MIB
* [RFC 4363](https://tools.ietf.org/html/rfc4363) dot1qTpFdbPort in Q-BRIDGE-MIB
* [IEEE 802.1 AB](http://www.ieee802.org/1/files/public/MIBs/LLDP-MIB-200505060000Z.txt) LLDP-MIB

To install:
```
$ python3.5 setup.py install
```

To run the daemon:
```
$ python3.5 -m sonic_ax_impl [-d 10]
```

