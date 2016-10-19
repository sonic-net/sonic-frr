#! /usr/bin/python -u
#################################################################################
# Copyright 2016 Cumulus Networks LLC, all rights reserved
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston,
# MA 02111-1307, USA.
#################################################################################
# This is a simple pass through script that
# returns only one OID, the Linux Distribution and Kernel Version
# as the systemDescription.
#
# To activate, you would need to place this
# script in /usr/share/snmp/sysDescr_pass.py
# and include this path along with the following
# in /etc/snmp/snmpd.conf (note the -p 10 to raise the priority)
#    pass -p 10 .1.3.6.1.2.1.1.1 /usr/share/snmp/sysDescr_pass.py
#
# snmpd will call this script with either -g or -n and an OID
# This can be tested simply by calling the script
#
# ./sysDescr_pass.py -g .1.3.6.1.2.1.1.1.0
# ./sysDescr_pass.py -n .1.3.6.1.2.1.1.1
#
# should return meaningful information.  Everything
# should return nothing.
#
# When tested on a recent Debian system, we get this:
#
# # snmpget  -v2c -cpublic localhost .1.3.6.1.2.1.1.1
# SNMPv2-MIB::sysDescr.0 = STRING: Debian 8.4 (Linux Kernel 3.16.7-ckt25-1)
#
#

import sys
import logging
import traceback

# configure logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

# this is the one oid
myoid = '.1.3.6.1.2.1.1.1.0'
# and the version without the .0
myoidsub1 = '.1.3.6.1.2.1.1.1'

if len(sys.argv) < 3:
    # we must be called with either -g or -n
    # and an oid
    sys.stdout.flush()
    sys.exit()

command = sys.argv[1]
oid = sys.argv[2]


if command == '-n' and oid != myoidsub1:
    # after our OID, there is nothing
    sys.stdout.flush()
    sys.exit()

elif command == '-s':
    logger.error("set: oid not writeable")
    sys.stdout.flush()
    sys.exit()

elif command == '-g' and oid != myoid:
    sys.stdout.flush()
    sys.exit()

filepath = "/etc/ssw/sysDescription"
sysDescription = "SONiC (unknown version) - HwSku (unknown) - Distribution (unknown) - Kernel (unknown)"

try:
    with open(filepath) as f:
        lines = f.readlines()

    sysDescription = lines[0]

except (OSError, IOError):
    logger.exception("Unable to access file {}".format(filepath))
except IndexError:
    logger.exception("unable to read lines from {}, possible empty file?".format(filepath))
except Exception:
    logger.exception("Uncaught exception in {}".format(filepath))
    logger.error(repr(traceback.extract_stack()))


# We simply have only have one object to print.
# we are passed a -g or -n for get or getnext
# snmpd will not call us with a get unless the oid
# is correct (the .0 on the end can be ignored).
# also, when called with a getnext, we checked the oid
# above so we know it is myoidsub1 for the getnext.

print("%s\nSTRING\n%s" % (myoid, sysDescription))

sys.stdout.flush()
