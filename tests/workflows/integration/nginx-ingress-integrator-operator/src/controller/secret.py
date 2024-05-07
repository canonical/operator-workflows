# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""nginx-ingress-integrator k8s secret controller."""


import logging
import typing

import kubernetes.client

from consts import CREATED_BY_LABEL
from controller.resource import ResourceController, _map_k8s_auth_exception
from ingress_definition import IngressDefinition

LOGGER = logging.getLogger(__name__)


class SecretController(ResourceController[kubernetes.client.V1Secret]):
    """Kubernetes Secret resource controller."""

    def __init__(self, namespace: str, labels: typing.Dict[str, str]) -> None:
        """Initialize the SecretController.

        Args:
            namespace: Kubernetes namespace.
            labels: Labels to be added to created resources.
        """
        self._ns = namespace
        self._client = kubernetes.client.CoreV1Api()
        self._labels = labels

    @property
    def _name(self) -> str:
        """Returns "secret"."""
        return "secret"

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

    def define_resource(  # type: ignore[override] # pylint:disable=arguments-differ
        self, definition: IngressDefinition, key: str
    ) -> kubernetes.client.V1Secret:
        """Create or update a resource in kubernetes.

        Args:
            definition: The ingress definition
            key: Key to filter by hostname.

        Returns:
            The name of the created or modified resource, None if no resource is
            modified or created.
        """
        resource_list = self._list_resource()
        body = self._gen_resource_from_definition(definition, key)
        if body.metadata.name in [r.metadata.name for r in resource_list]:
            self._patch_resource(
                name=body.metadata.name,
                body=body,
            )
            # pylint: disable=duplicate-code
            LOGGER.info(
                "%s updated in namespace %s with name %s",
                self._name,
                self._namespace,
                body.metadata.name,
            )
        else:
            self._create_resource(body=body)
            # pylint: enable=duplicate-code
            LOGGER.info(
                "%s created in namespace %s with name %s",
                self._name,
                self._namespace,
                body.metadata.name,
            )
        return body

    def cleanup_resources(
        self,
        exclude: typing.Union[list, None] = None,  # type: ignore[override]
    ) -> None:
        """Remove unused resources.

        Args:
            exclude: The name of resource to be excluded from the cleanup.
        """
        if exclude is None:
            exclude = []
        for resource in self._list_resource():
            delete_flag = True
            if exclude:
                for exclude_item in exclude:
                    if exclude and resource.metadata.name == exclude_item.metadata.name:
                        delete_flag = False
                        break
            if delete_flag:
                self._delete_resource(name=resource.metadata.name)
                LOGGER.info(
                    "%s deleted in namespace %s with name %s",
                    self._name,
                    self._namespace,
                    resource.metadata.name,
                )

    @_map_k8s_auth_exception
    def _gen_resource_from_definition(  # pylint: disable=arguments-differ
        self, definition: IngressDefinition, key: str
    ) -> kubernetes.client.V1Secret:
        """Generate a V1Secret resource from ingress definition.

        Args:
            definition: Ingress definition to use for generating the V1Secret resource.
            key: Key to filter by hostname.

        Returns:
            The generated V1Secret resource.
        """
        return kubernetes.client.V1Secret(
            api_version="v1",
            string_data={"tls.crt": definition.tls_cert[key], "tls.key": definition.tls_key[key]},
            kind="Secret",
            metadata=kubernetes.client.V1ObjectMeta(
                name=f"{self._labels[CREATED_BY_LABEL]}-cert-tls-secret-{key}",
                labels=self._labels,
                namespace=self._namespace,
            ),
            type="kubernetes.io/tls",
        )

    @_map_k8s_auth_exception
    def _create_resource(self, body: kubernetes.client.V1Secret) -> None:
        """Create a new V1Service resource in a given namespace.

        Args:
            body: The V1Service resource object to create.
        """
        self._client.create_namespaced_secret(namespace=self._namespace, body=body)

    @_map_k8s_auth_exception
    def _patch_resource(self, name: str, body: kubernetes.client.V1Secret) -> None:
        """Patch an existing V1Secret resource in a given namespace.

        Args:
            name: The name of the V1Service resource to patch.
            body: The modified V1Service resource object.
        """
        self._client.patch_namespaced_secret(namespace=self._namespace, name=name, body=body)

    @_map_k8s_auth_exception
    def _list_resource(self) -> typing.List[kubernetes.client.V1Secret]:
        """List V1Service resources in a given namespace based on a label selector.

        Returns:
            A list of matched V1Secret resources.
        """
        return self._client.list_namespaced_secret(
            namespace=self._namespace,
            label_selector=",".join(f"{k}={v}" for k, v in self._labels.items()),
        ).items

    @_map_k8s_auth_exception
    def _delete_resource(self, name: str) -> None:
        """Delete a V1Secret resource from a given namespace.

        Args:
            name: The name of the V1Secret resource to delete.
        """
        self._client.delete_namespaced_secret(namespace=self._namespace, name=name)
