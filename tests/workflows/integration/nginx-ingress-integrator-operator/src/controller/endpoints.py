# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""nginx-ingress-integrator k8s endpoint controller."""


from typing import Dict, List

import kubernetes.client

from controller.resource import ResourceController, _map_k8s_auth_exception
from ingress_definition import IngressDefinition


class EndpointsController(ResourceController[kubernetes.client.V1Endpoints]):
    """Kubernetes Endpoints resource controller."""

    def __init__(self, namespace: str, labels: Dict[str, str]) -> None:
        """Initialize the EndpointsController.

        Args:
            namespace: Kubernetes namespace.
            labels: Labels to be added to created resources.
        """
        self._ns = namespace
        self._client = kubernetes.client.CoreV1Api()
        self._labels = labels

    @property
    def _name(self) -> str:
        """Name of the resource: "endpoints".

        Returns:
            Name of the resource: "endpoints".
        """
        return "endpoints"

    @property
    def _namespace(self) -> str:
        """Returns the kubernetes namespace.

        Returns:
            The namespace.
        """
        return self._ns

    @property
    def _label_selector(self) -> str:
        """Return the label selector for resources managed by this controller.

        Return:
            The label selector.
        """
        return ",".join(f"{k}={v}" for k, v in self._labels.items())

    @_map_k8s_auth_exception
    def _gen_resource_from_definition(
        self, definition: IngressDefinition
    ) -> kubernetes.client.V1Endpoints:
        """Generate an endpoints resource from ingress definition.

        Args:
            definition: Ingress definition to use for generating the V1Endpoints resource.

        Returns:
            Generated endpoints resource.
        """
        return kubernetes.client.V1Endpoints(
            api_version="v1",
            kind="Endpoints",
            metadata=kubernetes.client.V1ObjectMeta(
                name=definition.k8s_service_name,
                labels=self._labels,
                namespace=definition.service_namespace,
            ),
            subsets=[
                kubernetes.client.V1EndpointSubset(
                    addresses=[
                        kubernetes.client.V1EndpointAddress(ip=endpoint)
                        for endpoint in definition.upstream_endpoints
                    ],
                    ports=[
                        kubernetes.client.CoreV1EndpointPort(
                            name=definition.port_name, port=definition.service_port
                        )
                    ],
                )
            ],
        )

    @_map_k8s_auth_exception
    def _create_resource(self, body: kubernetes.client.V1Endpoints) -> None:
        """Create a new V1Endpoints resource in a given namespace.

        Args:
            body: The V1Endpoints resource object to create.
        """
        self._client.create_namespaced_endpoints(namespace=self._namespace, body=body)

    @_map_k8s_auth_exception
    def _patch_resource(self, name: str, body: kubernetes.client.V1Endpoints) -> None:
        """Patch an existing V1Endpoints resource in a given namespace.

        Args:
            name: The name of the V1Endpoints resource to patch.
            body: The modified V1Endpoints resource object.
        """
        self._client.patch_namespaced_endpoints(namespace=self._namespace, name=name, body=body)

    @_map_k8s_auth_exception
    def _list_resource(self) -> List[kubernetes.client.V1Endpoints]:
        """List V1Endpoints resources in a given namespace based on a label selector.

        Returns:
            A list of matched V1Endpoints resources.
        """
        return self._client.list_namespaced_endpoints(
            namespace=self._namespace,
            label_selector=",".join(f"{k}={v}" for k, v in self._labels.items()),
        ).items

    @_map_k8s_auth_exception
    def _delete_resource(self, name: str) -> None:
        """Delete a V1Endpoints resource from a given namespace.

        Args:
            name: The name of the V1Endpoints resource to delete.
        """
        self._client.delete_namespaced_endpoints(namespace=self._namespace, name=name)
