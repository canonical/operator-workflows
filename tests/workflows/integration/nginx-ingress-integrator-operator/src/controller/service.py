# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""nginx-ingress-integrator k8s service controller."""


import typing

import kubernetes.client

from controller.resource import ResourceController, _map_k8s_auth_exception
from ingress_definition import IngressDefinition


class ServiceController(
    ResourceController[kubernetes.client.V1Service]
):  # pylint: disable=inherit-non-class
    """Kubernetes Service resource controller."""

    def __init__(self, namespace: str, labels: typing.Dict[str, str]) -> None:
        """Initialize the ServiceController.

        Args:
            namespace: Kubernetes namespace.
            labels: Labels to be added to created resources.
        """
        self._ns = namespace
        self._client = kubernetes.client.CoreV1Api()
        self._labels = labels

    @property
    def _name(self) -> str:
        """Returns "service"."""
        return "service"

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
    ) -> kubernetes.client.V1Service:
        """Generate a V1Service resource from ingress definition.

        Args:
            definition: Ingress definition to use for generating the V1Service resource.

        Returns:
            The generated V1Service resource.
        """
        spec = kubernetes.client.V1ServiceSpec(
            ports=[
                kubernetes.client.V1ServicePort(
                    name=definition.port_name,
                    port=definition.service_port,
                    target_port=definition.service_port,
                )
            ],
        )
        if not definition.use_endpoint_slice:
            spec.selector = {"app.kubernetes.io/name": definition.service_name}
        else:
            spec.cluster_ip = "None"
        return kubernetes.client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=kubernetes.client.V1ObjectMeta(
                name=definition.k8s_service_name,
                labels=self._labels,
                namespace=definition.service_namespace,
            ),
            spec=spec,
        )

    @_map_k8s_auth_exception
    def _create_resource(self, body: kubernetes.client.V1Service) -> None:
        """Create a new V1Service resource in a given namespace.

        Args:
            body: The V1Service resource object to create.
        """
        self._client.create_namespaced_service(namespace=self._namespace, body=body)

    @_map_k8s_auth_exception
    def _patch_resource(self, name: str, body: kubernetes.client.V1Service) -> None:
        """Patch an existing V1Service resource in a given namespace.

        Args:
            name: The name of the V1Service resource to patch.
            body: The modified V1Service resource object.
        """
        self._client.patch_namespaced_service(namespace=self._namespace, name=name, body=body)

    @_map_k8s_auth_exception
    def _list_resource(self) -> typing.List[kubernetes.client.V1Service]:
        """List V1Service resources in a given namespace based on a label selector.

        Returns:
            A list of matched V1Service resources.
        """
        return self._client.list_namespaced_service(
            namespace=self._namespace,
            label_selector=",".join(f"{k}={v}" for k, v in self._labels.items()),
        ).items

    @_map_k8s_auth_exception
    def _delete_resource(self, name: str) -> None:
        """Delete a V1Service resource from a given namespace.

        Args:
            name: The name of the V1Service resource to delete.
        """
        self._client.delete_namespaced_service(namespace=self._namespace, name=name)
