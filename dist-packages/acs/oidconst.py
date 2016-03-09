import const

class OidConsts(const._const):

    def __init__(self):

        # The interfaces oid prefix http://www.ietf.org/rfc/rfc2233.txt
        # It is used as the prefix for 
        # the following counters
        self.interfaces = '.1.3.6.1.2.1.2'

        # The ifNumber 
        self.ifNumber = '1.0'

        # Region ifTable
        # The ifTable
        self.ifTable = '2'

        # The if entry.
        self.ifEntry = '2.1'

        # The interface index.
        self.ifIndex = '2.1.1'

        # The interface description.
        self.ifDescr = '2.1.2'

        # The interface type.
        self.ifType = '2.1.3'

        # The if mtu.
        self.ifMtu = '2.1.4'

        # The if speed.
        self.ifSpeed = '2.1.5'

        # The if phys address.
        self.ifPhysAddress = '2.1.6'

        # The interface admin status.
        self.ifAdminStatus = '2.1.7'

        # The interface operational status.
        self.ifOperStatus = '2.1.8'

        # The if last change.
        self.ifLastChange = '2.1.9'

        # The if in octets.
        self.ifInOctets = '2.1.10'

        # The interface in unicast cast packets.
        self.ifInUcastPkts = '2.1.11'

        # The if in n ucast pkts.
        self.ifInNUcastPkts = '2.1.12'

        # The if in discards.
        self.ifInDiscards = '2.1.13'

        # The interface in errors.
        self.ifInErrors = '2.1.14'

        # The if in unknown protos.
        self.ifInUnknownProtos = '2.1.15'

        # The if out octets.
        self.ifOutOctets = '2.1.16'

        # The interface out unicast cast packets.
        self.ifOutUcastPkts = '2.1.17'

        # The if out n ucast pkts.
        self.ifOutNUcastPkts = '2.1.18'

        # The if out discards.
        self.ifOutDiscards = '2.1.19'

        # The interface out errors.
        self.ifOutErrors = '2.1.20'

        # The if out q len.
        self.ifOutQLen = '2.1.21'

        # The if specific.
        self.ifSpecific = '2.1.22'

        #endregion

        # The ifMIBObjects oid prefix http://www.ietf.org/rfc/rfc2233.txt
        self.ifMIBObjects = '.1.3.6.1.2.1.31.1'

        # region ifXTable
        # The ifXTable
        self.ifXTable = '1'

        # The if x entry.
        self.ifXEntry = '1.1'

        # The interface name.
        self.ifName = '1.1.1'

        # The if in multicast pkts.
        self.ifInMulticastPkts = '1.1.2'

        # The if in broadcast pkts.
        self.ifInBroadcastPkts = '1.1.3'

        # The if out multicast pkts.
        self.ifOutMulticastPkts = '1.1.4'

        # The if out broadcast pkts.
        self.ifOutBroadcastPkts = '1.1.5'

        # The high speed interface in octets.
        self.ifHCInOctets = '1.1.6'

        # The high speed interface in unicast packets.
        self.ifHCInUcastPkts = '1.1.7'

        # The if hc in multicast pkts.
        self.ifHCInMulticastPkts = '1.1.8'

        # The if hc in broadcast pkts.
        self.ifHCInBroadcastPkts = '1.1.9'

        # The high speed interface out octets.
        self.ifHCOutOctets = '1.1.10'

        # The high speed interface out unicast packets.
        self.ifHCOutUcastPkts = '1.1.11'

        # The if hc out multicast pkts.
        self.ifHCOutMulticastPkts = '1.1.12'

        # The if hc out broadcast pkts.
        self.ifHCOutBroadcastPkts = '1.1.13'

        # The if link up down trap enable.
        self.ifLinkUpDownTrapEnable = '1.1.14'

        # The interface high speed.
        self.ifHighSpeed = '1.1.15'

        # The if promiscuous mode.
        self.ifPromiscuousMode = '1.1.16'

        # The if connector present.
        self.ifConnectorPresent = '1.1.17'

        # The if alias.
        self.ifAlias = '1.1.18'

        # The if counter discontinuity time.
        self.ifCounterDiscontinuityTime = '1.1.19'

        # end of region


        # Lldp local system counters
        self.lldpLocPortTable = '.1.0.8802.1.1.2.1.3.7'

        # Lldp local port id
        self.lldpLocPortId = '1.3'
 
        # Lldp remote system counters
        self.lldpRemTable = '.1.0.8802.1.1.2.1.4.1'

        # The lldpRemPortIdSubtype
        self.lldpRemPortIdSubtype = '1.6'

        # The lldpRemPortId
        self.lldpRemPortId = '1.7'

        # The lldpRemPortDesc
        self.lldpRemPortDesc = '1.8'

        # The lldpRemSysName
        self.lldpRemSysName = '1.9'

        # end of region
