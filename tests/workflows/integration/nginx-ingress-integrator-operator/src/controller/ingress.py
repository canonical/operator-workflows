# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""nginx-ingress-integrator k8s ingress controller."""


import logging
import time
from typing import Dict, List, Optional

import kubernetes.client

from consts import CREATED_BY_LABEL
from controller.resource import ResourceController, _map_k8s_auth_exception
from ingress_definition import IngressDefinition

LOGGER = logging.getLogger(__name__)


class IngressController(
    ResourceController[kubernetes.client.V1Ingress]
):  # pylint: disable=inherit-non-class
    """Kubernetes Ingress resource controller."""

    def __init__(
        self,
        namespace: str,
        labels: Dict[str, str],
    ) -> None:
        """Initialize the IngressController.

        Args:
            namespace: Kubernetes namespace.
            labels: Label to be added to created resources.
        """
        self._ns = namespace
        self._client = kubernetes.client.NetworkingV1Api()
        self._labels = labels

    @property
    def _name(self) -> str:
        """Returns "ingress"."""
        return "ingress"

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

    def _look_up_and_set_ingress_class(
        self, ingress_class: Optional[str], body: kubernetes.client.V1Ingress
    ) -> None:
        """Set the configured ingress class, otherwise the cluster's default ingress class.

        Args:
            ingress_class: The desired ingress class name.
            body: The Ingress resource object.
        """
        if not ingress_class:
            defaults = [
                item.metadata.name
                for item in self._client.list_ingress_class().items
                if item.metadata.annotations.get("ingressclass.kubernetes.io/is-default-class")
                == "true"
            ]

            if not defaults:
                LOGGER.warning("Cluster has no default ingress class defined")
                return

            if len(defaults) > 1:
                default_ingress = " ".join(sorted(defaults))
                msg = "Multiple default ingress classes defined, declining to choose between them."
                LOGGER.warning(
                    "%s. They are: %s",
                    msg,
                    default_ingress,
                )
                return

            ingress_class = defaults[0]
            LOGGER.info("Using ingress class %s as it is the cluster's default", ingress_class)

        body.spec.ingress_class_name = ingress_class

    # disable the "function is too complex" warning here
    # this function is actually quite straightforward
    @_map_k8s_auth_exception
    def _gen_resource_from_definition(  # noqa: C901
        self, definition: IngressDefinition
    ) -> kubernetes.client.V1Ingress:
        """Generate a V1Ingress resource from ingress definition.

        Args:
            definition: Ingress definition to use for generating the V1Ingress resource.

        Returns:
            A V1Ingress resource based on provided definition.
        """
        ingress_paths = [
            kubernetes.client.V1HTTPIngressPath(
                path=path,
                path_type="Prefix",
                backend=kubernetes.client.V1IngressBackend(
                    service=kubernetes.client.V1IngressServiceBackend(
                        name=definition.k8s_service_name,
                        port=kubernetes.client.V1ServiceBackendPort(
                            number=int(definition.service_port),
                        ),
                    ),
                ),
            )
            for path in definition.path_routes
        ]

        hostnames = [definition.service_hostname]
        hostnames.extend(definition.additional_hostnames)
        ingress_rules = [
            kubernetes.client.V1IngressRule(
                host=hostname,
                http=kubernetes.client.V1HTTPIngressRuleValue(paths=ingress_paths),
            )
            for hostname in hostnames
        ]
        spec = kubernetes.client.V1IngressSpec(rules=ingress_rules)

        annotations = {
            "nginx.ingress.kubernetes.io/proxy-body-size": definition.max_body_size,
            "nginx.ingress.kubernetes.io/proxy-read-timeout": definition.proxy_read_timeout,
            "nginx.ingress.kubernetes.io/backend-protocol": definition.backend_protocol,
        }
        if not definition.enable_access_log:
            annotations["nginx.ingress.kubernetes.io/enable-access-log"] = "false"
        if definition.limit_rps:
            annotations["nginx.ingress.kubernetes.io/limit-rps"] = definition.limit_rps
            if definition.limit_whitelist:
                annotations["nginx.ingress.kubernetes.io/limit-whitelist"] = (
                    definition.limit_whitelist
                )
        if definition.owasp_modsecurity_crs:
            annotations["nginx.ingress.kubernetes.io/enable-modsecurity"] = "true"
            annotations["nginx.ingress.kubernetes.io/enable-owasp-modsecurity-crs"] = "true"
            sec_rule_engine = f"SecRuleEngine On\n{definition.owasp_modsecurity_custom_rules}"
            nginx_modsec_file = "/etc/nginx/owasp-modsecurity-crs/nginx-modsecurity.conf"
            annotations["nginx.ingress.kubernetes.io/modsecurity-snippet"] = (
                f"{sec_rule_engine}\nInclude {nginx_modsec_file}"
            )
        if definition.retry_errors:
            annotations["nginx.ingress.kubernetes.io/proxy-next-upstream"] = (
                definition.retry_errors
            )
        if definition.rewrite_enabled:
            annotations["nginx.ingress.kubernetes.io/rewrite-target"] = definition.rewrite_target
        if definition.session_cookie_max_age:
            annotations["nginx.ingress.kubernetes.io/affinity"] = "cookie"
            annotations["nginx.ingress.kubernetes.io/affinity-mode"] = "balanced"
            annotations["nginx.ingress.kubernetes.io/session-cookie-change-on-failure"] = "true"
            annotations["nginx.ingress.kubernetes.io/session-cookie-max-age"] = str(
                definition.session_cookie_max_age
            )
            annotations["nginx.ingress.kubernetes.io/session-cookie-name"] = (
                f"{definition.service_name.upper()}_AFFINITY"
            )
            annotations["nginx.ingress.kubernetes.io/session-cookie-samesite"] = "Lax"
        if definition.tls_secret_name:
            spec.tls = [
                kubernetes.client.V1IngressTLS(
                    hosts=[definition.service_hostname],
                    secret_name=definition.tls_secret_name,
                ),
            ]
        elif definition.tls_cert:
            spec.tls = [
                kubernetes.client.V1IngressTLS(
                    hosts=[hostname],
                    secret_name=f"{self._labels[CREATED_BY_LABEL]}-cert-tls-secret-{hostname}",
                )
                for hostname in hostnames
                if hostname in definition.tls_cert.keys()
            ]
        else:
            annotations["nginx.ingress.kubernetes.io/ssl-redirect"] = "false"
        if definition.whitelist_source_range:
            annotations["nginx.ingress.kubernetes.io/whitelist-source-range"] = (
                definition.whitelist_source_range
            )

        ingress = kubernetes.client.V1Ingress(
            api_version="networking.k8s.io/v1",
            kind="Ingress",
            metadata=kubernetes.client.V1ObjectMeta(
                name=definition.k8s_ingress_name,
                namespace=definition.service_namespace,
                annotations=annotations,
                labels=self._labels,
            ),
            spec=spec,
        )
        self._look_up_and_set_ingress_class(ingress_class=definition.ingress_class, body=ingress)
        return ingress

    @_map_k8s_auth_exception
    def _create_resource(self, body: kubernetes.client.V1Ingress) -> None:
        """Create a new V1Ingress resource in a given namespace.

        Args:
            body: The V1Ingress resource object to create.
        """
        self._client.create_namespaced_ingress(namespace=self._namespace, body=body)

    @_map_k8s_auth_exception
    def _patch_resource(self, name: str, body: kubernetes.client.V1Ingress) -> None:
        """Replace an existing V1Ingress resource in a given namespace.

        Args:
            name: The name of the V1Ingress resource to replace.
            body: The modified V1Ingress resource object.
        """
        self._client.replace_namespaced_ingress(namespace=self._namespace, name=name, body=body)

    @_map_k8s_auth_exception
    def _list_resource(self) -> List[kubernetes.client.V1Ingress]:
        """List V1Ingress resources in a given namespace based on a label selector.

        Returns:
            A list of matched V1Ingress resources.
        """
        return self._client.list_namespaced_ingress(
            namespace=self._namespace,
            label_selector=",".join(f"{k}={v}" for k, v in self._labels.items()),
        ).items

    @_map_k8s_auth_exception
    def _delete_resource(self, name: str) -> None:
        """Delete a V1Ingress resource from a given namespace.

        Args:
            name: The name of the V1Ingress resource to delete.
        """
        self._client.delete_namespaced_ingress(namespace=self._namespace, name=name)

    def get_ingress_ips(self) -> List[str]:
        """Return IP addresses of ingresses.

        Returns:
            A list of Ingress IPs.
        """
        deadline = time.time() + 100
        ips = []
        while time.time() < deadline:
            ingresses = self._list_resource()
            try:
                ips = [x.status.load_balancer.ingress[0].ip for x in ingresses]
            except TypeError:
                # We have no IPs yet.
                pass
            if ips:
                break
            LOGGER.info("Sleeping for %s seconds to wait for ingress IP", 1)
            time.sleep(1)
        return ips
