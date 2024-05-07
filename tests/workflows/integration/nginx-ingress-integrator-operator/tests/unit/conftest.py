# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""nginx-ingress-integrator charm unit test fixtures."""


import copy
import unittest.mock
from collections import defaultdict
from functools import partial
from typing import Any, Dict, List, Union

import kubernetes
import ops.testing
import pytest

from charm import NginxIngressCharm


class K8sStub:
    """A test stub for kubernetes APIs."""

    def __init__(self):
        """Initialize a new K8sStub instance."""
        self.namespaces: defaultdict[str, dict] = defaultdict(
            lambda: {
                "ingress": {},
                "service": {},
                "endpoint_slice": {},
                "endpoints": {},
                "secret": {},
            }
        )
        self.auth = True
        self.legacy_mode = False
        self.ingress_classes = [
            kubernetes.client.V1IngressClass(
                metadata=kubernetes.client.V1ObjectMeta(
                    annotations={"ingressclass.kubernetes.io/is-default-class": "true"},
                    name="nginx-ingress",
                )
            )
        ]

    def _get_resource_dict(self, resource: str, namespace: str) -> Dict[str, Any]:
        """Retrieve the resource dictionary for a given namespace.

        Args:
            resource: Type of the kubernetes resource (ingress, service, etc.).
            namespace: Kubernetes namespace.

        Returns:
            A dictionary of resources for the given namespace.
        """
        return self.namespaces[namespace][resource]

    def get_ingresses(self, namespace: str) -> List[kubernetes.client.V1Ingress]:
        """Get ingress resources for the specified namespace.

        Args:
            namespace: Kubernetes namespace.

        Returns:
            List of ingress resources.
        """
        return list(self._get_resource_dict("ingress", namespace=namespace).values())

    def get_services(self, namespace: str) -> List[kubernetes.client.V1Service]:
        """Get service resources for the specified namespace.

        Args:
            namespace: Kubernetes namespace.

        Returns:
            List of service resources.
        """
        return list(self._get_resource_dict("service", namespace=namespace).values())

    def get_secrets(self, namespace: str) -> List[kubernetes.client.V1Secret]:
        """Get service resources for the specified namespace.

        Args:
            namespace: Kubernetes namespace.

        Returns:
            List of service resources.
        """
        return list(self._get_resource_dict("secret", namespace=namespace).values())

    def get_endpoint_slices(self, namespace: str) -> List[kubernetes.client.V1EndpointSlice]:
        """Get endpoint slice resources for the specified namespace.

        Args:
            namespace: Kubernetes namespace.

        Returns:
            List of endpoint slice resources.
        """
        return list(self._get_resource_dict("endpoint_slice", namespace=namespace).values())

    def get_endpoints(self, namespace: str) -> List[kubernetes.client.V1Endpoints]:
        """Get endpoints resources for the specified namespace.

        Args:
            namespace: Kubernetes namespace.

        Returns:
            List of endpoints resources.
        """
        return list(self._get_resource_dict("endpoints", namespace=namespace).values())

    def _update_ingress_status(self, ingress: kubernetes.client.V1Ingress):
        """Update the status of the provided ingress to include ingress IP address.

        Args:
            ingress: The ingress resource to update.
        """
        ingress.status = kubernetes.client.V1IngressStatus(
            load_balancer=kubernetes.client.V1LoadBalancerStatus(
                ingress=[kubernetes.client.V1LoadBalancerIngress(ip="127.0.0.1")]
            )
        )

    def _update_service_spec(self, service: kubernetes.client.V1Service):
        """Update the spec of the provided service to include service cluster IP address.

        Args:
            service: The service resource to update.
        """
        if service.spec.cluster_ip is None:
            service.spec.cluster_ip = "10.0.0.1"

    def create_namespaced_resource(
        self,
        resource: str,
        namespace: str,
        body: Union[
            kubernetes.client.V1Endpoints,
            kubernetes.client.V1EndpointSlice,
            kubernetes.client.V1Service,
            kubernetes.client.V1Secret,
            kubernetes.client.V1Ingress,
        ],
    ):
        """Create a namespaced Kubernetes resource.

        Args:
            resource: Type of the Kubernetes resource (endpoints, service, etc.).
            namespace: Kubernetes namespace in which the resource is to be created.
            body: The actual resource body that needs to be created.

        Raises:
            kubernetes.client.ApiException: If authentication fails (status=403).
            ValueError: If attempting to overwrite an existing resource of the same name.
        """
        if not self.auth:
            raise kubernetes.client.ApiException(status=403)
        resources = self._get_resource_dict(resource=resource, namespace=namespace)
        name = body.metadata.name
        if name in resources:
            raise ValueError(f"can't overwrite existing {resource} {name}")
        if isinstance(body, kubernetes.client.V1Ingress):
            self._update_ingress_status(body)
        if isinstance(body, kubernetes.client.V1Service):
            self._update_service_spec(body)
        resources[name] = body

    def patch_namespaced_resource(
        self,
        resource: str,
        namespace: str,
        name: str,
        body: Union[
            kubernetes.client.V1Endpoints,
            kubernetes.client.V1EndpointSlice,
            kubernetes.client.V1Service,
            kubernetes.client.V1Secret,
            kubernetes.client.V1Ingress,
        ],
    ) -> None:
        """Patch a specific namespaced Kubernetes resource.

        Args:
            resource: Type of the Kubernetes resource (endpoints, service, etc.).
            namespace: Kubernetes namespace where the resource is located.
            name: The name of the specific resource to patch.
            body: The updated body for the resource.

        Raises:
            kubernetes.client.ApiException: If authentication fails (status=403).
            ValueError: If the specified resource is not found in the given namespace.
        """
        if not self.auth:
            raise kubernetes.client.ApiException(status=403)
        resources = self._get_resource_dict(resource=resource, namespace=namespace)
        if name not in resources:
            raise ValueError(f"{resource} {name} in {namespace} not found")
        if isinstance(body, kubernetes.client.V1Ingress):
            self._update_ingress_status(body)
        if isinstance(body, kubernetes.client.V1Service):
            self._update_service_spec(body)
        resources[name] = body

    def list_namespaced_resource(
        self, resource: str, namespace: str, label_selector: str
    ) -> Union[
        kubernetes.client.V1EndpointsList,
        kubernetes.client.V1EndpointSliceList,
        kubernetes.client.V1ServiceList,
        kubernetes.client.V1SecretList,
        kubernetes.client.V1IngressList,
    ]:
        """List all resource in a specified namespace.

        Args:
            resource: Type of the kubernetes resource.
            namespace: Kubernetes namespace.
            label_selector: not used.

        Returns:
            List of endpoints resources in the namespace.

        Raises:
            kubernetes.client.ApiException: If authentication fails (status=403).
        """
        if not self.auth:
            raise kubernetes.client.ApiException(status=403)
        resources = list(self._get_resource_dict(resource=resource, namespace=namespace).values())
        if resource == "endpoints":
            return kubernetes.client.V1EndpointsList(items=resources)
        elif resource == "endpoint_slice":
            return kubernetes.client.V1EndpointSliceList(items=resources)
        elif resource == "service":
            return kubernetes.client.V1ServiceList(items=resources)
        elif resource == "secret":
            return kubernetes.client.V1SecretList(items=resources)
        elif resource == "ingress":
            return kubernetes.client.V1IngressList(items=resources)
        else:
            raise ValueError(f"unknown resource type: {resource}")

    def delete_namespaced_resource(self, resource: str, namespace: str, name: str):
        """Delete a resource in a specified namespace.

        Args:
            resource: Type of the kubernetes resource.
            namespace: Kubernetes namespace.
            name: Name of the resource.

        Raises:
            ValueError: If the resource is not found in the namespace.
        """
        if not self.auth:
            raise kubernetes.client.ApiException(status=403)
        resources = self._get_resource_dict(resource=resource, namespace=namespace)
        if name not in resources:
            raise ValueError(f"{resource} {name} in {namespace} not found")
        del resources[name]


@pytest.fixture
def k8s_stub(monkeypatch: pytest.MonkeyPatch) -> K8sStub:
    """Pytest fixture for creating a stub for Kubernetes API."""
    stub = K8sStub()
    for action in ("create", "patch", "list", "delete"):
        monkeypatch.setattr(
            f"kubernetes.client.CoreV1Api.{action}_namespaced_endpoints",
            partial(getattr(stub, f"{action}_namespaced_resource"), "endpoints"),
        )
        monkeypatch.setattr(
            f"kubernetes.client.DiscoveryV1Api.{action}_namespaced_endpoint_slice",
            partial(getattr(stub, f"{action}_namespaced_resource"), "endpoint_slice"),
        )
        monkeypatch.setattr(
            f"kubernetes.client.CoreV1Api.{action}_namespaced_service",
            partial(getattr(stub, f"{action}_namespaced_resource"), "service"),
        )
        monkeypatch.setattr(
            f"kubernetes.client.CoreV1Api.{action}_namespaced_secret",
            partial(getattr(stub, f"{action}_namespaced_resource"), "secret"),
        )
        ingress_action = action.replace("patch", "replace")
        monkeypatch.setattr(
            f"kubernetes.client.NetworkingV1Api.{ingress_action}_namespaced_ingress",
            partial(getattr(stub, f"{action}_namespaced_resource"), "ingress"),
        )
    monkeypatch.setattr(
        "kubernetes.client.NetworkingV1Api.list_ingress_class",
        lambda _: kubernetes.client.V1IngressClassList(items=stub.ingress_classes),
    )
    return stub


@pytest.fixture
def legacy_k8s_stub(monkeypatch: pytest.MonkeyPatch, k8s_stub: K8sStub):
    """Pytest fixture for creating a stub for Kubernetes 1.20 API."""
    for action in ("create", "patch", "list", "delete"):
        monkeypatch.setattr(
            f"kubernetes.client.DiscoveryV1Api.{action}_namespaced_endpoint_slice",
            unittest.mock.MagicMock(side_effect=kubernetes.client.ApiException(status=404)),
        )
        monkeypatch.setattr(
            f"kubernetes.client.DiscoveryV1beta1Api.{action}_namespaced_endpoint_slice",
            partial(getattr(k8s_stub, f"{action}_namespaced_resource"), "endpoint_slice"),
        )
    return k8s_stub


@pytest.fixture(name="patch_load_incluster_config")
def patch_load_incluster_config_fixture(monkeypatch):
    """Patch kubernetes.config.load_incluster_config."""
    monkeypatch.setattr("kubernetes.config.load_incluster_config", lambda: None)


@pytest.fixture(name="harness")
def harness_fixture(patch_load_incluster_config) -> ops.testing.Harness:
    """Create and prepare the ops testing harness."""
    harness = ops.testing.Harness(NginxIngressCharm)
    harness.set_model_name("test")
    harness.set_leader(True)
    return harness


class RelationFixture:
    """A fixture helper class for manipulating Charm relation events.

    Attrs:
        relation: The Ops Relation object for the current relation fixture.
    """

    def __init__(
        self,
        harness: ops.testing.Harness,
        relation_name: str,
        example_app_data: Dict[str, str],
        example_unit_data: Dict[str, str],
    ):
        """Initialize the RelationFixture.

        Args:
            harness: The testing harness from Ops testing framework.
            relation_name: Name of the relation.
            example_app_data: Sample app relation data for the relation.
            example_unit_data: Sample unit relation data for the relation.
        """
        self._harness = harness
        self._relation_name = relation_name
        self._remote_app = f"{relation_name}-remote"
        self._remote_unit = f"{self._remote_app}/0"
        self._relation_id = self._harness.add_relation(self._relation_name, self._remote_app)
        self._harness.add_relation_unit(self._relation_id, self._remote_unit)
        self._example_app_data = example_app_data
        self._example_unit_data = example_unit_data

    def update_app_data(self, data: Dict[str, str]) -> None:
        """Update the application relation data with the provided data.

        Args:
            data: The new app relation data.
        """
        self._harness.update_relation_data(self._relation_id, self._remote_app, data)

    def update_unit_data(self, data: Dict[str, str]) -> None:
        """Update the unit relation data with the provided data.

        Args:
            data: The new unit relation data.
        """
        self._harness.update_relation_data(self._relation_id, self._remote_unit, data)

    def remove_relation(self) -> None:
        """Remove the relation from the testing harness."""
        self._harness.remove_relation_unit(self._relation_id, self._remote_unit)
        self._harness.remove_relation(self._relation_id)

    def gen_example_app_data(self) -> Dict[str, str]:
        """Generate a copy of the example application relation data.

        Returns:
            A copy of the example app relation data.
        """
        return copy.copy(self._example_app_data)

    def gen_example_unit_data(self) -> Dict[str, str]:
        """Generate a copy of the example unit relation data.

        Returns:
            A copy of the example unit relation data.
        """
        return copy.copy(self._example_unit_data)

    @property
    def relation(self) -> ops.Relation:
        """Get the relation object for the current relation fixture.

        Returns:
            The relation object from Ops framework.
        """
        return self._harness.charm.model.get_relation(
            relation_name=self._relation_name, relation_id=self._relation_id
        )


@pytest.fixture
def nginx_route_relation(harness: ops.testing.Harness) -> RelationFixture:
    """Pytest fixture for simulating an nginx-route relation."""
    return RelationFixture(
        harness,
        relation_name="nginx-route",
        example_app_data={
            "service-hostname": "example.com",
            "service-port": "8080",
            "service-namespace": "test",
            "service-name": "app",
        },
        example_unit_data={},
    )


@pytest.fixture
def ingress_relation(harness: ops.testing.Harness) -> RelationFixture:
    """Pytest fixture for simulating an ingress relation."""
    return RelationFixture(
        harness,
        relation_name="ingress",
        example_app_data={
            "port": "8080",
            "model": '"test"',
            "name": '"app"',
        },
        example_unit_data={"host": '"test.svc.cluster.local"', "ip": '"10.0.0.1"'},
    )
