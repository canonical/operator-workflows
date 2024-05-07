# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=redefined-outer-name,unused-argument,duplicate-code

"""Integration test relation file."""

import asyncio
import json
import logging
import typing
from pathlib import Path

import pytest
import pytest_asyncio
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

LOGGER = logging.getLogger(__name__)

# Mypy can't recognize the name as a string type, so we should skip the type check.
ACTIVE_STATUS_NAME = ActiveStatus.name
PROVIDER_CHARM_DIR = "tests/integration/provider_charm"
TLS_CERTIFICATES_PROVIDER_APP_NAME = "tls-certificates-provider"
INGRESS_APP_NAME = "ingress"
ANY_APP_NAME = "any"
ANY_APP_NAME_2 = "any2"
NEW_HOSTNAME = "any.other"


def gen_src_overwrite(
    service_hostname: str = "any",
    service_name: str = "any",
    service_port: int = 8080,
    additional_hostnames: typing.Optional[str] = None,
) -> str:
    """Generate the src-overwrite config value for testing nginx-route relation.

    Args:
        service_hostname: Ingress service hostname.
        service_name: Ingress service name.
        service_port: Ingress service port
        additional_hostnames: Ingress additional hostnames

    Returns:
        written src-overwrite variable.
    """
    nginx_route_lib_path = "lib/charms/nginx_ingress_integrator/v0/nginx_route.py"
    nginx_route_lib = Path(nginx_route_lib_path).read_text(encoding="utf8")
    any_charm_script = Path("tests/integration/any_charm_nginx_route.py").read_text(
        encoding="utf8"
    )
    nginx_route_config = {
        "service_hostname": service_hostname,
        "service_name": service_name,
        "service_port": service_port,
    }
    if additional_hostnames:
        nginx_route_config["additional_hostnames"] = additional_hostnames
    any_charm_src_overwrite = {
        "any_charm.py": any_charm_script,
        "nginx_route.py": nginx_route_lib,
        "nginx_route_config.json": json.dumps(nginx_route_config),
    }
    return json.dumps(any_charm_src_overwrite)


@pytest_asyncio.fixture(scope="module")
async def build_and_deploy(
    model: Model, ops_test: OpsTest, deploy_any_charm, run_action, build_and_deploy_ingress
):
    """Build and deploy nginx-ingress-integrator charm.

    Also deploy and relate an any-charm application for test purposes.

    Returns: None.
    """
    await asyncio.gather(
        deploy_any_charm(gen_src_overwrite()),
        build_and_deploy_ingress(),
    )
    await model.wait_for_idle()
    await run_action(ANY_APP_NAME, "rpc", method="start_server")
    relation_name = f"{INGRESS_APP_NAME}:nginx-route"
    await model.add_relation(f"{ANY_APP_NAME}:nginx-route", relation_name)
    await model.wait_for_idle()
    provider_charm = await ops_test.build_charm(f"{PROVIDER_CHARM_DIR}/")
    await model.deploy(
        provider_charm,
        application_name=TLS_CERTIFICATES_PROVIDER_APP_NAME,
        series="jammy",
    )

    await model.wait_for_idle(
        apps=[TLS_CERTIFICATES_PROVIDER_APP_NAME],
        status="blocked",
        timeout=1000,
    )


@pytest.mark.usefixtures("build_and_deploy")
async def test_given_charms_deployed_when_relate_then_status_is_active(
    model: Model, ops_test: OpsTest
):
    """
    arrange: sample certificate charm has been deployed.
    act: integrate the sample certificate provider charm to the given charm.
    assert: the integration is successful.
    """
    await model.add_relation(TLS_CERTIFICATES_PROVIDER_APP_NAME, "ingress:certificates")

    await model.wait_for_idle(
        apps=[INGRESS_APP_NAME, TLS_CERTIFICATES_PROVIDER_APP_NAME],
        status="active",
        timeout=1000,
    )


@pytest.mark.usefixtures("build_and_deploy")
async def test_given_charms_deployed_when_relate_then_requirer_received_certs(
    model: Model, ops_test: OpsTest
):
    """
    arrange: given charm has been built, deployed and related to a certificate provider.
    act: get the current certificates provided.
    assert: the given charm has been provided a certificate successfully.
    """
    requirer_unit = model.units["ingress/0"]

    action = await requirer_unit.run_action(action_name="get-certificate", hostname="any")

    action_output = await model.get_action_output(action_uuid=action.entity_id, wait=60)
    assert action_output["return-code"] == 0
    assert "ca-any" in action_output and action_output["ca-any"] is not None
    assert "certificate-any" in action_output and action_output["certificate-any"] is not None
    assert "chain-any" in action_output and action_output["chain-any"] is not None


@pytest.mark.usefixtures("build_and_deploy")
async def test_given_additional_requirer_charm_deployed_when_relate_then_requirer_received_certs(
    model: Model,
    ops_test: OpsTest,
    run_action,
):
    """
    arrange: given charm has been built, deployed and integrated with a dependent application.
    act: deploy another instance of the given charm.
    assert: the process of deployment, integration and certificate provision is successful.
    """
    new_requirer_app_name = "ingress2"
    charm = await ops_test.build_charm(".")
    await model.deploy(
        str(charm), application_name=new_requirer_app_name, series="focal", trust=True
    )
    await model.deploy(
        "any-charm",
        application_name=ANY_APP_NAME_2,
        channel="beta",
        config={"src-overwrite": gen_src_overwrite()},
    )
    await model.wait_for_idle()
    await run_action(ANY_APP_NAME_2, "rpc", method="start_server")
    relation_name = f"{new_requirer_app_name}:nginx-route"
    await model.add_relation(f"{ANY_APP_NAME_2}:nginx-route", relation_name)
    await model.wait_for_idle()

    await model.add_relation(
        TLS_CERTIFICATES_PROVIDER_APP_NAME, f"{new_requirer_app_name}:certificates"
    )
    await model.wait_for_idle(
        apps=[
            TLS_CERTIFICATES_PROVIDER_APP_NAME,
            new_requirer_app_name,
        ],
        status="active",
        timeout=1000,
    )
    requirer_unit = model.units[f"{new_requirer_app_name}/0"]

    action = await requirer_unit.run_action(action_name="get-certificate", hostname="any")

    action_output = await model.get_action_output(action_uuid=action.entity_id, wait=60)
    assert action_output["return-code"] == 0
    assert "ca-any" in action_output and action_output["ca-any"] is not None
    assert "certificate-any" in action_output and action_output["certificate-any"] is not None
    assert "chain-any" in action_output and action_output["chain-any"] is not None


@pytest.mark.usefixtures("build_and_deploy")
async def test_given_enough_time_passed_then_certificate_expired(model: Model, ops_test: OpsTest):
    """
    arrange: given charm has been built, deployed and related to a certificate provider.
    act: wait until the certificate expires.
    assert: the certificate expires and the given charm waits for a new certificate.
    """
    await model.wait_for_idle(
        apps=[
            INGRESS_APP_NAME,
        ],
        status="maintenance",
        timeout=1000,
        idle_period=0,
    )
    requirer_unit = model.units["ingress/0"]

    assert requirer_unit.workload_status_message == "Waiting for new certificate"
