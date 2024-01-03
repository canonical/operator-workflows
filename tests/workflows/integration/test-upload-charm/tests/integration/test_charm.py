# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests."""

import asyncio

from pytest_operator.plugin import OpsTest


async def test_build_and_deploy(ops_test: OpsTest, pytestconfig):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    app_name = "test"
    assert ops_test.model
    charm = pytestconfig.getoption("--charm-file")
    resources = {"test-image": pytestconfig.getoption("--test-image")}

    await asyncio.gather(
        ops_test.model.deploy(
            f"./{charm}", resources=resources, application_name=app_name, series="jammy"
        ),
        ops_test.model.wait_for_idle(
            apps=[app_name], status="active", raise_on_blocked=True, timeout=1000
        ),
    )
