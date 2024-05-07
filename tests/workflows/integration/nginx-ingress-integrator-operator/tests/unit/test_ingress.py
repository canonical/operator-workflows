# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""nginx-ingress-integrator charm unit tests."""

from ops.testing import Harness

from consts import CREATED_BY_LABEL
from tests.unit.conftest import K8sStub
from tests.unit.constants import TEST_NAMESPACE


def test_basic(k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation.
    act: update the ingress relation with basic data.
    assert: validate ingress, service and endpoint slice are created appropriately.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com"})

    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 1
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.labels[CREATED_BY_LABEL] == harness.charm.app.name
    assert ingress.spec.rules[0].host == "example.com"

    assert len(k8s_stub.get_services(TEST_NAMESPACE)) == 1
    service = k8s_stub.get_services(TEST_NAMESPACE)[0]
    assert service.spec.selector is None
    assert service.spec.cluster_ip == "None"
    assert len(service.spec.ports) == 1
    assert service.spec.ports[0].port == 8080
    assert service.spec.ports[0].target_port == 8080

    assert len(k8s_stub.get_endpoint_slices(TEST_NAMESPACE)) == 1
    endpoint_slice = k8s_stub.get_endpoint_slices(TEST_NAMESPACE)[0]
    assert endpoint_slice.address_type == "IPv4"
    assert endpoint_slice.endpoints[0].addresses == ["10.0.0.1"]
    assert endpoint_slice.metadata.labels["kubernetes.io/service-name"] == service.metadata.name

    assert len(k8s_stub.get_endpoints(TEST_NAMESPACE)) == 1
    endpoints = k8s_stub.get_endpoints(TEST_NAMESPACE)[0]
    assert [address.ip for address in endpoints.subsets[0].addresses] == ["10.0.0.1"]
    assert endpoints.metadata.name == service.metadata.name


def test_route_path(k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation.
    act: update the ingress relation with basic data.
    assert: service should contain correct path configurations.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.spec.rules[0].http.paths[0].path == "/test-app"


def test_legacy_k8s(legacy_k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation and simulate Kubernetes 1.20 API.
    act: update the ingress relation with basic data.
    assert: endpoint slice should be set up correctly in the simulated cluster.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com"})
    assert len(legacy_k8s_stub.get_endpoint_slices(TEST_NAMESPACE)) == 1

    unit_data = ingress_relation.gen_example_unit_data()
    unit_data["ip"] = '"10.0.0.2"'
    ingress_relation.update_unit_data(unit_data)
    endpoint_slice = legacy_k8s_stub.get_endpoint_slices(TEST_NAMESPACE)[0]
    assert endpoint_slice.endpoints[0].addresses == ["10.0.0.2"]

    ingress_relation.remove_relation()
    # test harness doesn't handle relation-broken properly
    harness.charm.model._relations._invalidate(ingress_relation.relation.name)
    harness.charm._on_data_removed(None)

    assert legacy_k8s_stub.get_endpoints(TEST_NAMESPACE) == []
    assert legacy_k8s_stub.get_endpoint_slices(TEST_NAMESPACE) == []
    assert legacy_k8s_stub.get_services(TEST_NAMESPACE) == []
    assert legacy_k8s_stub.get_ingresses(TEST_NAMESPACE) == []


def test_update_ingress_ip(k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation.
    act: update the ingress relation with basic data and update the ingress again with new ip.
    assert: endpoint slice should contain correct ip addresses after the update.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com"})
    assert k8s_stub.get_endpoint_slices(TEST_NAMESPACE)[0].endpoints[0].addresses == ["10.0.0.1"]

    unit_data = ingress_relation.gen_example_unit_data()
    unit_data["ip"] = '"10.0.0.2"'
    ingress_relation.update_unit_data(unit_data)
    assert k8s_stub.get_endpoint_slices(TEST_NAMESPACE)[0].endpoints[0].addresses == ["10.0.0.2"]

    ingress_relation.remove_relation()
    # test harness doesn't handle relation-broken properly
    harness.charm.model._relations._invalidate(ingress_relation.relation.name)
    harness.charm._on_data_removed(None)

    assert k8s_stub.get_endpoints(TEST_NAMESPACE) == []
    assert k8s_stub.get_endpoint_slices(TEST_NAMESPACE) == []
    assert k8s_stub.get_services(TEST_NAMESPACE) == []
    assert k8s_stub.get_ingresses(TEST_NAMESPACE) == []


def test_port_name(k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation.
    act: update the ingress relation with basic data.
    assert: port names are the same across all ingress related objects.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com"})
    assert (
        k8s_stub.get_services(TEST_NAMESPACE)[0].spec.ports[0].name
        == k8s_stub.get_endpoints(TEST_NAMESPACE)[0].subsets[0].ports[0].name
        == k8s_stub.get_endpoint_slices(TEST_NAMESPACE)[0].ports[0].name
    )


def test_hostname_in_app_data(k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation.
    act: update the ingress relation with basic data.
    assert: hostname is in the app data bag.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com", "path-routes": "/path"})

    expected_data = '{"url": "http://example.com/path"}'
    assert ingress_relation.relation.data[harness.charm.app].get("ingress") == expected_data

    harness.update_config({"additional-hostnames": "example.net"})
    # We have added an additional hostname, so the charm should be blocked and
    # the url should be removed from the app data.
    # If we confirm that the url is None, we can confirm that the charm is blocked.
    assert ingress_relation.relation.data[harness.charm.app].get("ingress") is None


def test_pathroutes(k8s_stub: K8sStub, harness: Harness, ingress_relation):
    """
    arrange: set up test harness and ingress relation.
    act: update the ingress relation with basic data.
    assert: path routes are set up correctly in the service.
    """
    harness.begin()
    ingress_relation.update_app_data(ingress_relation.gen_example_app_data())
    ingress_relation.update_unit_data(ingress_relation.gen_example_unit_data())
    harness.update_config({"service-hostname": "example.com", "path-routes": "/path"})
    expected_data = '{"url": "http://example.com/path"}'
    assert ingress_relation.relation.data[harness.charm.app].get("ingress") == expected_data

    harness.update_config({"path-routes": "/path1,/path2"})
    # We have added multiple path routes, so the charm should be blocked.
    assert ingress_relation.relation.data[harness.charm.app].get("ingress") is None

    harness.update_config({"path-routes": "/path1,invalid_path"})
    # We have added an invalid path route, that does not start with /
    #  so the charm should be blocked.
    assert ingress_relation.relation.data[harness.charm.app].get("ingress") is None

    harness.update_config({"path-routes": ""})
    expected_data = f'{{"url": "http://example.com/{harness.charm.model.name}-app"}}'
    # We have added an invalid path route, so the charm should be blocked.
    assert ingress_relation.relation.data[harness.charm.app].get("ingress") == expected_data
