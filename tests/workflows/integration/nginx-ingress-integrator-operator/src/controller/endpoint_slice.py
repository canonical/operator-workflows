# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""nginx-ingress-integrator k8s endpoint slice controller."""


from typing import Dict, List

import kubernetes.client

from controller.resource import ResourceController, _map_k8s_auth_exception
from ingress_definition import IngressDefinition


class EndpointSliceController(
    ResourceController[kubernetes.client.V1EndpointSlice]
):  # pylint: disable=inherit-non-class
    """Kubernetes EndpointSlice resource controller."""

    def __init__(self, namespace: str, labels: Dict[str, str]) -> None:
        """Initialize the EndpointSliceController.

        Args:
            namespace: Kubernetes namespace.
            labels: Label to be added to created resources.
        """
        self._ns = namespace
        self._labels = labels
        self._client = kubernetes.client.DiscoveryV1Api()
        self._beta_client = kubernetes.client.DiscoveryV1beta1Api()  # pylint: disable=no-member

    @property
    def _name(self) -> str:
        """Returns "endpoint slice"."""
        return "endpoint slice"

    @property
    def _namespace(self) -> str:
        """Returns the kubernetes namespace.

        Returns:
            The namespace.
        """
        return self._ns

    @_map_k8s_auth_exception
    def _gen_resource_from_definition(
        self, definition: IngressDefinition
    ) -> kubernetes.client.V1EndpointSlice:
        """Generate a V1EndpointSlice resource from ingress definition.

        Args:
            definition: Ingress definition to use for generating the V1EndpointSlice resource.

        Returns:
            The generated V1EndpointSlice resource.
        """
        address_type = definition.upstream_endpoint_type
        return kubernetes.client.V1EndpointSlice(
            api_version="discovery.k8s.io/v1",
            kind="EndpointSlice",
            metadata=kubernetes.client.V1ObjectMeta(
                name=definition.k8s_endpoint_slice_name,
                namespace=definition.service_namespace,
                labels={
                    **self._labels,
                    "kubernetes.io/service-name": definition.k8s_service_name,
                },
            ),
            address_type=address_type,
            ports=[
                kubernetes.client.DiscoveryV1EndpointPort(
                    name=definition.port_name,
                    port=definition.service_port,
                )
            ],
            endpoints=[
                kubernetes.client.V1Endpoint(
                    addresses=definition.upstream_endpoints,
                    conditions=kubernetes.client.V1EndpointConditions(ready=True, serving=True),
                )
            ],
        )

    @_map_k8s_auth_exception
    def _create_resource(self, body: kubernetes.client.V1EndpointSlice) -> None:
        """Create a new V1EndpointSlice resource in a given namespace.

        Args:
            body: The V1EndpointSlice resource object to create.

        Raises:
            ApiException: if the Python kubernetes raised an unknown ApiException
        """
        try:
            self._client.create_namespaced_endpoint_slice(namespace=self._namespace, body=body)
        except kubernetes.client.exceptions.ApiException as exc:
            if exc.status == 404:
                body.api_version = "discovery.k8s.io/v1beta1"
                self._beta_client.create_namespaced_endpoint_slice(
                    namespace=self._namespace, body=body
                )
            else:
                raise

    @_map_k8s_auth_exception
    def _patch_resource(self, name: str, body: kubernetes.client.V1EndpointSlice) -> None:
        """Patch an existing V1EndpointSlice resource in a given namespace.

        Args:
            name: The name of the V1EndpointSlice resource to patch.
            body: The modified V1EndpointSlice resource object.

        Raises:
            ApiException: if the Python kubernetes raised an unknown ApiException
        """
        try:
            self._client.patch_namespaced_endpoint_slice(
                namespace=self._namespace, name=name, body=body
            )
        except kubernetes.client.exceptions.ApiException as exc:
            if exc.status == 404:
                body.api_version = "discovery.k8s.io/v1beta1"
                self._beta_client.patch_namespaced_endpoint_slice(
                    namespace=self._namespace, name=name, body=body
                )
            else:
                raise

    @_map_k8s_auth_exception
    def _list_resource(self) -> List[kubernetes.client.V1EndpointSlice]:
        """List V1EndpointSlice resources in a given namespace based on a label selector.

        Returns:
            A list of matched V1EndpointSlice resources.

        Raises:
            ApiException: if the Python kubernetes raised an unknown ApiException
        """
        label_selector = ",".join(f"{k}={v}" for k, v in self._labels.items())
        try:
            return self._client.list_namespaced_endpoint_slice(
                namespace=self._namespace, label_selector=label_selector
            ).items
        except kubernetes.client.exceptions.ApiException as exc:
            if exc.status == 404:
                return self._beta_client.list_namespaced_endpoint_slice(
                    namespace=self._namespace, label_selector=label_selector
                ).items
            raise

    @_map_k8s_auth_exception
    def _delete_resource(self, name: str) -> None:
        """Delete a V1EndpointSlice resource from a given namespace.

        Args:
            name: The name of the V1EndpointSlice resource to delete.

        Raises:
            ApiException: if the Python kubernetes raised an unknown ApiException
        """
        try:
            self._client.delete_namespaced_endpoint_slice(namespace=self._namespace, name=name)
        except kubernetes.client.exceptions.ApiException as exc:
            if exc.status == 404:
                self._beta_client.delete_namespaced_endpoint_slice(
                    namespace=self._namespace, name=name
                )
            else:
                raise
