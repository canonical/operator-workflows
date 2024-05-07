# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""nginx-ingress-integrator k8s resource controllers."""

import abc
import functools
import logging
import typing

import kubernetes.client

from exceptions import InvalidIngressError
from ingress_definition import IngressDefinition

logger = logging.getLogger(__name__)

AnyResource = typing.TypeVar(
    "AnyResource",
    kubernetes.client.V1Endpoints,
    kubernetes.client.V1EndpointSlice,
    kubernetes.client.V1Service,
    kubernetes.client.V1Secret,
    kubernetes.client.V1Ingress,
)


def _map_k8s_auth_exception(func: typing.Callable) -> typing.Callable:
    """Remap the kubernetes 403 ApiException to InvalidIngressError.

    Args:
        func: function to be wrapped.

    Returns:
        A wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        """Remap the kubernetes 403 ApiException to InvalidIngressError.

        Args:
            args: function arguments.
            kwargs: function keyword arguments.

        Returns:
            The function return value.

        Raises:
            ApiException: if the Python kubernetes raised an unknown ApiException
            InvalidIngressError: if the Python kubernetes raised a permission error
        """
        try:
            return func(*args, **kwargs)
        except kubernetes.client.exceptions.ApiException as exc:
            if exc.status == 403:
                logger.error(
                    "Insufficient permissions to create the k8s service, "
                    "will request `juju trust` to be run"
                )
                juju_trust_cmd = "juju trust <nginx-ingress-integrator> --scope=cluster"
                raise InvalidIngressError(
                    f"Insufficient permissions, try: `{juju_trust_cmd}`"
                ) from exc
            raise

    return wrapper


class ResourceController(typing.Protocol[AnyResource]):
    """Abstract base class for a generic Kubernetes resource controller."""

    @property
    @abc.abstractmethod
    def _name(self) -> str:
        """Abstract property that returns the name of the resource type.

        Returns:
            Name of the resource type.
        """

    @property
    @abc.abstractmethod
    def _namespace(self) -> str:
        """Abstract property that returns the namespace of the controller.

        Returns:
            The namespace.
        """

    @abc.abstractmethod
    def _gen_resource_from_definition(self, definition: IngressDefinition) -> AnyResource:
        """Abstract method to generate a resource from ingress definition.

        Args:
            definition: Ingress definition to use for generating the resource.
        """

    @abc.abstractmethod
    def _create_resource(self, body: AnyResource) -> None:
        """Abstract method to create a new resource in a given namespace.

        Args:
            body: The resource object to create.
        """

    @abc.abstractmethod
    def _patch_resource(self, name: str, body: AnyResource) -> None:
        """Abstract method to patch an existing resource in a given namespace.

        Args:
            name: The name of the resource to patch.
            body: The modified resource object.
        """

    @abc.abstractmethod
    def _list_resource(self) -> typing.List[AnyResource]:
        """Abstract method to list resources in a given namespace based on a label selector."""

    @abc.abstractmethod
    def _delete_resource(self, name: str) -> None:
        """Abstract method to delete a resource from a given namespace.

        Args:
            name: The name of the resource to delete.
        """

    def define_resource(
        self,
        definition: IngressDefinition,
    ) -> AnyResource:
        """Create or update a resource in kubernetes.

        Args:
            definition: The ingress definition

        Returns:
            The name of the created or modified resource, None if no resource is
            modified or created.
        """
        resource_list = self._list_resource()
        body = self._gen_resource_from_definition(definition)
        if body.metadata.name in [r.metadata.name for r in resource_list]:
            self._patch_resource(
                name=body.metadata.name,
                body=body,
            )
            logger.info(
                "%s updated in namespace %s with name %s",
                self._name,
                self._namespace,
                body.metadata.name,
            )
        else:
            self._create_resource(body=body)
            logger.info(
                "%s created in namespace %s with name %s",
                self._name,
                self._namespace,
                body.metadata.name,
            )
        return body

    def cleanup_resources(
        self,
        exclude: typing.Optional[AnyResource] = None,
    ) -> None:
        """Remove unused resources.

        Args:
            exclude: The name of resource to be excluded from the cleanup.
        """
        for resource in self._list_resource():
            if exclude is not None and resource.metadata.name == exclude.metadata.name:
                continue
            self._delete_resource(name=resource.metadata.name)
            logger.info(
                "%s deleted in namespace %s with name %s",
                self._name,
                self._namespace,
                resource.metadata.name,
            )
