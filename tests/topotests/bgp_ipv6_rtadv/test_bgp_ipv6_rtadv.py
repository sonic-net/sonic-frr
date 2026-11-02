#!/usr/bin/env python
# SPDX-License-Identifier: ISC

#
# test_bgp_ipv6_rtadv.py
# Part of NetDEF Topology Tests
#
# Copyright (c) 2019 by 6WIND
#

"""
 test_bgp_ipv6_rtadv.py: Test the FRR BGP daemon with BGP IPv6 interface
 with route advertisements on a separate netns.
"""

import os
import sys
import json
import time
from functools import partial
import pytest

# Save the Current Working Directory to find configuration files.
CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, "../"))

# pylint: disable=C0413
# Import topogen and topotest helpers
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger

# Required to instantiate the topology builder class.


pytestmark = [pytest.mark.bgpd]


def build_topo(tgen):
    "Build function"

    # Create 2 routers.
    tgen.add_router("r1")
    tgen.add_router("r2")

    switch = tgen.add_switch("s1")
    switch.add_link(tgen.gears["r1"])
    switch.add_link(tgen.gears["r2"])


def setup_module(mod):
    "Sets up the pytest environment"
    tgen = Topogen(build_topo, mod.__name__)
    tgen.start_topology()

    router_list = tgen.routers()

    for rname, router in router_list.items():
        router.load_config(
            TopoRouter.RD_ZEBRA, os.path.join(CWD, "{}/zebra.conf".format(rname))
        )
        router.load_config(
            TopoRouter.RD_BGP, os.path.join(CWD, "{}/bgpd.conf".format(rname))
        )

    # Initialize all routers.
    tgen.start_router()


def teardown_module(_mod):
    "Teardown the pytest environment"
    tgen = get_topogen()

    tgen.stop_topology()


def test_protocols_convergence():
    """
    Assert that BGP protocol has converged
    by checking the incoming BGP updates have been received.
    """
    tgen = get_topogen()
    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    # Check BGP IPv4 routing table.
    logger.info("Checking BGP IPv4 routes for convergence")
    router = tgen.gears["r1"]

    json_file = "{}/{}/bgp_ipv4_routes.json".format(CWD, router.name)
    expected = json.loads(open(json_file).read())
    test_func = partial(
        topotest.router_json_cmp,
        router,
        "show bgp ipv4 json",
        expected,
    )
    _, result = topotest.run_and_expect(test_func, None, count=160, wait=0.5)
    assertmsg = '"{}" JSON output mismatches'.format(router.name)
    assert result is None, assertmsg

    # Check BGP IPv6 routing table.
    json_file = "{}/{}/bgp_ipv6_routes.json".format(CWD, router.name)
    expected = json.loads(open(json_file).read())
    test_func = partial(
        topotest.router_json_cmp,
        router,
        "show bgp ipv6 json",
        expected,
    )
    _, result = topotest.run_and_expect(test_func, None, count=160, wait=0.5)
    assertmsg = '"{}" JSON output mismatches'.format(router.name)
    assert result is None, assertmsg


def test_route_convergence():
    """
    Assert that all protocols have converged
    statuses as they depend on it.
    """
    tgen = get_topogen()
    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    # Check IPv4 routing tables.
    logger.info("Checking IPv4 routes for convergence")
    for router in tgen.routers().values():
        json_file = "{}/{}/ipv4_routes.json".format(CWD, router.name)
        if not os.path.isfile(json_file):
            logger.info("skipping file {}".format(json_file))
            continue

        expected = json.loads(open(json_file).read())
        test_func = partial(
            topotest.router_json_cmp,
            router,
            "show ip route json",
            expected,
        )
        _, result = topotest.run_and_expect(test_func, None, count=160, wait=0.5)
        assertmsg = '"{}" JSON output mismatches'.format(router.name)
        assert result is None, assertmsg

    # Check IPv6 routing tables.
    logger.info("Checking IPv6 routes for convergence")
    for router in tgen.routers().values():
        json_file = "{}/{}/ipv6_routes.json".format(CWD, router.name)
        if not os.path.isfile(json_file):
            logger.info("skipping file {}".format(json_file))
            continue

        expected = json.loads(open(json_file).read())
        test_func = partial(
            topotest.router_json_cmp,
            router,
            "show ipv6 route json",
            expected,
        )
        _, result = topotest.run_and_expect(test_func, None, count=160, wait=0.5)
        assertmsg = '"{}" JSON output mismatches'.format(router.name)
        assert result is None, assertmsg


@pytest.mark.parametrize("recreate", [False, True])
def test_ra_interface_delete(recreate):
    """Remove RA references on deletion and preserve RA on interface recreation."""
    tgen = get_topogen()
    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    router = tgen.gears["r1"]
    interface = "ra-delete-test"
    kernel_interface = False
    configured = False

    def ra_registered():
        output = router.cmd_raises("vtysh -c 'show ipv6 nd ra-interfaces'")
        return interface in output.split()

    try:
        router.cmd_raises("ip link add {} type dummy".format(interface))
        kernel_interface = True
        old_index = json.loads(
            router.cmd_raises("ip -j link show {}".format(interface))
        )[0]["ifindex"]
        router.cmd_raises(
            "vtysh -c 'configure terminal' -c 'interface {}' "
            "-c 'no ipv6 nd suppress-ra'".format(interface)
        )
        configured = True
        _, result = topotest.run_and_expect(ra_registered, True, count=40, wait=0.1)
        assert result is True, "RA was not registered on the initially down interface"

        router.cmd_raises("ip link del {}".format(interface))
        kernel_interface = False
        _, result = topotest.run_and_expect(ra_registered, False, count=40, wait=0.1)
        assert result is False, "Deleted interface remains in the RA advertiser list"

        if recreate:
            router.cmd_raises("ip link add {} type dummy".format(interface))
            kernel_interface = True
            new_index = json.loads(
                router.cmd_raises("ip -j link show {}".format(interface))
            )[0]["ifindex"]
            assert (
                new_index != old_index
            ), "Recreation did not produce a new interface index"
            router.cmd_raises("ip link set {} up".format(interface))
            _, result = topotest.run_and_expect(ra_registered, True, count=40, wait=0.1)
            assert (
                result is True
            ), "Configured RA was not restored on the recreated interface"
    finally:
        if kernel_interface:
            router.cmd_raises("ip link del {}".format(interface))
        if configured:
            router.cmd_raises(
                "vtysh -c 'configure terminal' -c 'no interface {}'".format(interface)
            )

    # Allow a wheel revolution after freeing the configured interface object.
    time.sleep(1.2)
    assert (
        router.check_router_running() == ""
    ), "A daemon failed after RA interface deletion"


def test_memory_leak():
    "Run the memory leak test and report results."
    tgen = get_topogen()
    if not tgen.is_memleak_enabled():
        pytest.skip("Memory leak test/report is disabled")

    tgen.report_memory_leaks()


if __name__ == "__main__":
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
