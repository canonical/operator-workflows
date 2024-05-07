# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""nginx-ingress-integrator charm unit tests."""
import pytest
from ops.testing import Harness

from charm import NginxIngressCharm
from tests.unit.conftest import K8sStub
from tests.unit.constants import TEST_NAMESPACE


@pytest.mark.usefixtures("patch_load_incluster_config")
def test_follower():
    """
    arrange: set up test harness in a follower unit.
    act: start the harness.
    assert: unit should enter waiting status with appropriate status message.
    """
    harness = Harness(NginxIngressCharm)
    harness.begin_with_initial_hooks()
    assert harness.charm.unit.status.name == "blocked"
    assert harness.charm.unit.status.message.startswith("this charm only supports a single unit")


def test_no_relation(harness: Harness, k8s_stub: K8sStub):
    """
    arrange: set up test harness without relations.
    act: start the harness.
    assert: unit should enter waiting status with appropriate status message.
    """
    harness.begin_with_initial_hooks()
    assert harness.charm.unit.status.name == "waiting"
    assert harness.charm.unit.status.message == "waiting for relation"
    assert k8s_stub.get_ingresses(TEST_NAMESPACE) == []
    assert k8s_stub.get_services(TEST_NAMESPACE) == []
    assert k8s_stub.get_endpoint_slices(TEST_NAMESPACE) == []


def test_incomplete_nginx_route(harness: Harness, k8s_stub: K8sStub, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: update the relation with incomplete data.
    assert: unit should enter blocked status with appropriate status message.
    """
    harness.begin_with_initial_hooks()
    assert harness.charm.unit.status.name == "waiting"
    assert harness.charm.unit.status.message == "waiting for relation"
    nginx_route_relation.update_app_data({"service-name": "app"})
    assert harness.charm.unit.status.name == "blocked"
    assert (
        harness.charm.unit.status.message
        == "Missing fields for nginx-route: service-hostname, service-port"
    )


TEST_INCOMPLETE_INGRESS_PARAMS = [
    pytest.param(
        ["service-hostname"],
        "blocked",
        "service-hostname is not set for the ingress relation, configure it using `juju config`",
        id="missing-service-hostname",
    ),
    pytest.param(["port"], "waiting", "waiting for relation", id="missing-port"),
    pytest.param(["name"], "waiting", "waiting for relation", id="missing-name"),
    pytest.param(
        ["ip"], "blocked", "no endpoints are provided in ingress relation", id="missing-ip"
    ),
]


@pytest.mark.parametrize("missing,status,message", TEST_INCOMPLETE_INGRESS_PARAMS)
def test_incomplete_ingress(
    harness: Harness, k8s_stub: K8sStub, ingress_relation, missing, status, message
):
    """
    arrange: set up test harness and ingress relation.
    act: update the relation with different incomplete data.
    assert: unit should enter blocked status with appropriate status message.
    """
    harness.begin_with_initial_hooks()

    if "service-hostname" not in missing:
        harness.update_config({"service-hostname": "example.com"})
    app_data = ingress_relation.gen_example_app_data()
    unit_data = ingress_relation.gen_example_unit_data()
    for missing_field in missing:
        if missing_field in app_data:
            del app_data[missing_field]
        if missing_field in unit_data:
            del unit_data[missing_field]

    ingress_relation.update_app_data(app_data)
    ingress_relation.update_unit_data(unit_data)

    assert harness.charm.unit.status.message == message
    assert harness.charm.unit.status.name == status
    assert k8s_stub.get_ingresses(TEST_NAMESPACE) == []


def test_no_permission(harness: Harness, k8s_stub: K8sStub, ingress_relation):
    """
    arrange: set up test harness.
    act: update kubernetes test stub to raise permission error.
    assert: unit should enter blocked status with appropriate status message.
    """
    k8s_stub.auth = False
    harness.begin_with_initial_hooks()
    assert harness.charm.unit.status.name == "blocked"
    assert (
        harness.charm.unit.status.message
        == "Insufficient permissions, try: `juju trust <nginx-ingress-integrator> --scope=cluster`"
    )


def test_two_relation(harness: Harness, k8s_stub, ingress_relation, nginx_route_relation):
    """
    arrange: set up test harness with ingress relation and nginx-route relation.
    act: none.
    assert: unit should enter blocked status with appropriate status message.
    """
    harness.begin_with_initial_hooks()
    assert harness.charm.unit.status.name == "blocked"
    assert (
        harness.charm.unit.status.message
        == "Both nginx-route and ingress relations found, please remove either one."
    )
