# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""nginx-ingress-integrator ingress definition."""

import dataclasses
import ipaddress
import re
from typing import List, Optional, Union, cast

import ops
from charms.traefik_k8s.v2.ingress import DataValidationError, IngressPerAppProvider
from ops.model import Application, ConfigData, Model, Relation

from consts import BOOLEAN_CONFIG_FIELDS
from exceptions import InvalidIngressError


class IngressDefinitionEssence:  # pylint: disable=too-many-public-methods
    """Class containing data from the Charm configuration, or from a relation."""

    @classmethod
    def from_nginx_route(  # pylint: disable=too-many-arguments
        cls,
        charm: ops.CharmBase,
        relation: Relation,
        tls_cert: dict,
        tls_key: dict,
    ) -> "IngressDefinitionEssence":
        """Create an ingress definition essence object for nginx-route relation.

        Args:
            charm: The charm object.
            relation: The nginx-route relation
            tls_cert: TLS Certificate content
            tls_key: TLS private key content

        Returns:
            The created ingress definition essence object.
        """
        return cls(
            model=charm.model,
            config=charm.config,
            relation=relation,
            tls_key=tls_key,
            tls_cert=tls_cert,
        )

    @classmethod
    def from_ingress(  # pylint: disable=too-many-arguments
        cls,
        charm: ops.CharmBase,
        relation: Relation,
        ingress_provider: IngressPerAppProvider,
        tls_cert: dict,
        tls_key: dict,
    ) -> "IngressDefinitionEssence":
        """Create an ingress definition essence object for ingress relation.

        Args:
            charm: The charm object.
            relation: The ingress relation.
            ingress_provider: The ingress provider object from ingress charm library.
            tls_cert: TLS Certificate content
            tls_key: TLS private key content

        Returns:
            The created ingress definition essence object.
        """
        return cls(
            model=charm.model,
            config=charm.config,
            relation=relation,
            ingress_provider=ingress_provider,
            tls_key=tls_key,
            tls_cert=tls_cert,
        )

    def __init__(  # pylint: disable=too-many-arguments
        self,
        model: Model,
        config: ConfigData,
        relation: Relation,
        tls_cert: dict,
        tls_key: dict,
        ingress_provider: Optional[IngressPerAppProvider] = None,
    ) -> None:
        """Create a _ConfigOrRelation Object.

        Args:
            model: The charm model.
            config: The charm's configuration.
            relation: One of the charm's relations, if any.
            ingress_provider: The ingress provider object from the ingress charm library.
            tls_cert: TLS Certificate content
            tls_key: TLS private key content
        """
        super().__init__()
        self.model = model
        self.config = config
        self.relation = relation
        self.ingress_provider = ingress_provider
        self.tls_key = tls_key
        self.tls_cert = tls_cert

    def _get_config(self, field: str) -> Union[str, float, int, bool, None]:
        """Get data from config.

        Args:
            field: Config field.

        Returns:
            The field's content.
        """
        # Config fields with a default of None don't appear in the dict
        config_data = self.config.get(field, None)
        # A value of False is valid in these fields, so check it's not a null-value instead
        if field in BOOLEAN_CONFIG_FIELDS and (config_data is not None and config_data != ""):
            return config_data
        if config_data:
            return config_data

        return None

    def _get_relation(self, field: str) -> Union[str, None]:
        """Get data from the relation, if any.

        Args:
            field: Relation field.

        Returns:
            The field's content.
        """
        return self.relation.data[cast(Application, self.relation.app)].get(field)

    def _get_config_or_relation_data(
        self, field: str, fallback: Union[str, float, int, bool, None]
    ) -> Union[str, float, int, bool, None]:
        """Get data from config or the ingress relation, in that order.

        Args:
            field: Config or relation field.
            fallback: Value to return if the field is not found.

        Returns:
            The field's content or the fallback value if no field is found.
        """
        data: Union[str, float, int, bool, None] = self._get_config(field)
        if data is not None:
            return data

        data = self._get_relation(field)
        if data is not None:
            return data

        return fallback

    def _get_relation_data_or_config(
        self, field: str, fallback: Union[str, int, bool, None]
    ) -> Union[str, float, int, bool, None]:
        """Get data from the ingress relation or config, in that order.

        Args:
            field: Config or relation field.
            fallback: Value to return if the field is not found.

        Returns:
            The field's content or the fallback value if no field is found.
        """
        data: Union[str, float, int, bool, None] = self._get_relation(field)
        if data is not None:
            return data

        data = self._get_config(field)
        if data is not None:
            return data

        return fallback

    @property
    def additional_hostnames(self) -> List[str]:
        """Return a list with additional hostnames.

        Returns:
            The additional hostnames set by configuration already split by comma.
        """
        additional_hostnames = cast(
            str, self._get_config_or_relation_data("additional-hostnames", "")
        ).strip()
        if not additional_hostnames:
            return []

        hostnames = [h.strip() for h in additional_hostnames.split(",")]
        for hostname in hostnames:
            if not self._is_valid_hostname(hostname):
                raise InvalidIngressError(
                    "invalid ingress additional-hostname, "
                    "the hostname must consist of lower case alphanumeric characters, '-' or '.'"
                )
        return hostnames

    @property
    def backend_protocol(self) -> str:
        """Return the backend-protocol to use for k8s ingress."""
        backend_protocol = cast(
            str, self._get_config_or_relation_data("backend-protocol", "HTTP")
        ).upper()
        if backend_protocol not in ("HTTP", "HTTPS", "GRPC", "GRPCS", "AJP", "FCGI"):
            raise InvalidIngressError(
                f"invalid backend protocol {backend_protocol!r}, "
                f"valid values: HTTP, HTTPS, GRPC, GRPCS, AJP, FCGI"
            )
        return backend_protocol

    @property
    def enable_access_log(self) -> bool:
        """Return if access log is enabled for this ingress.

        If the charm configuration is set, it takes precedence over the relation data.
        If this setting is not specified in the configuration or relation, it defaults to True.
        """
        relation_data = self._get_relation("enable-access-log")
        from_relation = relation_data.lower() == "true" if relation_data is not None else None
        from_config = self.config.get("enable-access-log")
        if from_config is None:
            # default (None) is True
            return from_relation or from_relation is None
        return bool(from_config) or from_config is None

    @property
    def k8s_endpoint_slice_name(self) -> str:
        """Return the endpoint slice name for the use creating a k8s endpoint slice."""
        # endpoint slice name must be the same as service name
        # to be detected by nginx ingress controller
        return self.k8s_service_name

    @property
    def k8s_service_name(self) -> str:
        """Return a service name for the use creating a k8s service."""
        return f"relation-{self.relation.id}-{self.service_name}-service"

    @property
    def k8s_ingress_name(self) -> str:
        """Return an ingress name for use creating a k8s ingress."""
        svc_hostname = cast(str, self._get_config_or_relation_data("service-hostname", ""))
        ingress_name = re.sub("[^0-9a-zA-Z]", "-", svc_hostname)
        return f"relation-{self.relation.id}-{ingress_name}-ingress"

    @property
    def limit_rps(self) -> str:
        """Return limit-rps value from config or relation."""
        limit_rps = self._get_config_or_relation_data("limit-rps", 0)
        if limit_rps:
            return str(limit_rps)
        # Don't return "0" which would evaluate to True.
        return ""

    @property
    def limit_whitelist(self) -> str:
        """Return the limit-whitelist value from config or relation."""
        return cast(str, self._get_config_or_relation_data("limit-whitelist", ""))

    @property
    def max_body_size(self) -> str:
        """Return the max-body-size to use for k8s ingress."""
        max_body_size = self._get_config_or_relation_data("max-body-size", 0)
        return f"{max_body_size}m"

    @property
    def owasp_modsecurity_crs(self) -> bool:
        """Return a boolean indicating whether OWASP ModSecurity CRS is enabled."""
        value = self._get_config_or_relation_data("owasp-modsecurity-crs", False)
        return str(value).lower() == "true"

    @property
    def owasp_modsecurity_custom_rules(self) -> str:
        r"""Return the owasp-modsecurity-custom-rules value from config or relation.

        Since when setting the config via CLI or via YAML file, the new line character ('\n')
        is escaped ('\\n') we need to replace it for a new line character.
        """
        return cast(
            str, self._get_config_or_relation_data("owasp-modsecurity-custom-rules", "")
        ).replace("\\n", "\n")

    @property
    def proxy_read_timeout(self) -> str:
        """Return the proxy-read-timeout to use for k8s ingress."""
        proxy_read_timeout = self._get_config_or_relation_data("proxy-read-timeout", 60)
        return f"{proxy_read_timeout}"

    @property
    def rewrite_enabled(self) -> bool:
        """Return whether rewriting should be enabled from config or relation."""
        value = self._get_config_or_relation_data("rewrite-enabled", True)
        # config data is typed, relation data is a string
        # Convert to string, then compare to a known value.
        return str(value).lower() == "true"

    @property
    def rewrite_target(self) -> str:
        """Return the rewrite target from config or relation."""
        return cast(str, self._get_config_or_relation_data("rewrite-target", "/"))

    @property
    def service_namespace(self) -> str:
        """Return the namespace to operate on."""
        if self.is_ingress_relation:
            try:
                return (
                    cast(IngressPerAppProvider, self.ingress_provider)
                    .get_data(self.relation)
                    .app.model
                )
            except DataValidationError as exc:
                raise InvalidIngressError(msg=f"{exc}, cause: {exc.__cause__!r}") from exc
        return cast(str, self._get_config_or_relation_data("service-namespace", self.model.name))

    @property
    def retry_errors(self) -> str:
        """Return the retry-errors setting from config or relation."""
        retry = cast(str, self._get_config_or_relation_data("retry-errors", ""))
        if not retry:
            return ""
        # See http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_next_upstream.
        accepted_values = [
            "error",
            "timeout",
            "invalid_header",
            "http_500",
            "http_502",
            "http_503",
            "http_504",
            "http_403",
            "http_404",
            "http_429",
            "non_idempotent",
            "off",
        ]
        return " ".join([x.strip() for x in retry.split(",") if x.strip() in accepted_values])

    @staticmethod
    def _is_valid_hostname(hostname: str) -> bool:
        """Check if a hostname is valid.

        Args:
            hostname: hostname to check.

        Returns:
            If the hostname is valid.
        """
        # This regex comes from the error message kubernetes shows when trying to set an
        # invalid hostname.
        # See https://github.com/canonical/nginx-ingress-integrator-operator/issues/2
        # for an example.
        result = re.fullmatch(
            "[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*", hostname
        )
        if result:
            return True
        return False

    @property
    def service_hostname(self) -> str:
        """Return the hostname for the service we're connecting to."""
        service_hostname = cast(str, self._get_config_or_relation_data("service-hostname", ""))
        if not service_hostname:
            if self.is_ingress_relation:
                raise InvalidIngressError(
                    "service-hostname is not set for the ingress relation, "
                    "configure it using `juju config`"
                )
            raise InvalidIngressError(
                "service-hostname definition is missing, verify the relation or configuration"
            )
        if not self._is_valid_hostname(service_hostname):
            raise InvalidIngressError(
                "invalid ingress service-hostname, "
                "the hostname must consist of lower case alphanumeric characters, '-' or '.'"
            )
        return service_hostname

    @property
    def service_name(self) -> str:
        """Return the name of the service we're connecting to."""
        if self.is_ingress_relation:
            try:
                return (
                    cast(IngressPerAppProvider, self.ingress_provider)
                    .get_data(self.relation)
                    .app.name
                )
            except DataValidationError as exc:
                raise InvalidIngressError(msg=f"{exc}, cause: {exc.__cause__!r}") from exc
        else:
            service_name = cast(str, self._get_relation_data_or_config("service-name", ""))
        return service_name

    @property
    def service_port(self) -> int:
        """Return the port for the service we're connecting to."""
        if self.is_ingress_relation:
            try:
                return (
                    cast(IngressPerAppProvider, self.ingress_provider)
                    .get_data(self.relation)
                    .app.port
                )
            except DataValidationError as exc:
                raise InvalidIngressError(msg=f"{exc}, cause: {exc.__cause__!r}") from exc
        else:
            port = self._get_relation_data_or_config("service-port", 0)
        return int(cast(Union[str, int], port))

    @property
    def path_routes(self) -> List[str]:
        """Return the path routes to use for the k8s ingress."""
        if self.is_ingress_relation:
            return cast(
                str,
                self._get_config_or_relation_data(
                    "path-routes", f"/{self.service_namespace}-{self.service_name}"
                ),
            ).split(",")
        return cast(str, self._get_config_or_relation_data("path-routes", "/")).split(",")

    @property
    def session_cookie_max_age(self) -> int:
        """Return the session-cookie-max-age to use for k8s ingress."""
        session_cookie_max_age = self._get_config_or_relation_data("session-cookie-max-age", 0)
        if not session_cookie_max_age:
            return 0
        if isinstance(session_cookie_max_age, str):
            if not session_cookie_max_age.isdigit():
                raise InvalidIngressError("session-cookie-max-age is invalid: not an integer")
            return int(session_cookie_max_age)
        return 0

    @property
    def tls_secret_name(self) -> str:
        """Return the tls-secret-name to use for k8s ingress (if any)."""
        return cast(str, self._get_config_or_relation_data("tls-secret-name", ""))

    @property
    def whitelist_source_range(self) -> str:
        """Return the whitelist-source-range config definition."""
        return cast(str, self._get_config("whitelist-source-range"))

    @property
    def upstream_endpoints(self) -> List[str]:
        """Return the ingress upstream endpoint ip addresses, only in ingress v2 relation."""
        endpoints = []
        if self.use_endpoint_slice:
            try:
                endpoints = [
                    u.ip
                    for u in cast(IngressPerAppProvider, self.ingress_provider)
                    .get_data(self.relation)
                    .units
                    if u.ip is not None
                ]
            except DataValidationError as exc:
                raise InvalidIngressError(msg=f"{exc}, cause: {exc.__cause__!r}") from exc
        if self.use_endpoint_slice and not endpoints:
            raise InvalidIngressError("no endpoints are provided in ingress relation")
        return endpoints

    @property
    def use_endpoint_slice(self) -> bool:
        """Check if the ingress need to use endpoint slice."""
        return self.is_ingress_relation

    @property
    def is_ingress_relation(self) -> bool:
        """Check if the relation is connected via ingress relation endpoint."""
        return self.relation.name == "ingress"

    @property
    def upstream_endpoint_type(self) -> Optional[str]:
        """Return the ip address type of upstream endpoint addresses.

        Return:
            IPv4 or IPv6.

        Raises:
            InvalidIngressError: if the upstream endpoints are invalid.
            ValueError: if there are no upstream endpoint.
        """
        if not self.upstream_endpoints:
            return None
        address_types = []
        for address in self.upstream_endpoints:
            address = address.strip()
            try:
                ipaddress.IPv6Address(address)
                address_types.append("IPv6")
                continue
            except ValueError:
                pass
            try:
                ipaddress.IPv4Address(address)
                address_types.append("IPv4")
                continue
            except ValueError:
                pass
            address_types.append("UNKNOWN")
        if not all(t == "IPv4" for t in address_types) or all(t == "IPv6" for t in address_types):
            raise InvalidIngressError("invalid ingress relation data, mixed or unknown IP types")
        return address_types[0]

    @property
    def ingress_class(self) -> Optional[str]:
        """Return the ingress class configured in the charm."""
        return str(self.config["ingress-class"]) if self.config["ingress-class"] else None


@dataclasses.dataclass
class IngressDefinition:  # pylint: disable=too-many-public-methods,too-many-instance-attributes
    """Class containing ingress definition collected from the Charm configuration or relation.

    See config.yaml for descriptions of each property.
    """

    additional_hostnames: List[str]
    backend_protocol: str
    enable_access_log: bool
    ingress_class: Optional[str]
    is_ingress_relation: bool
    k8s_endpoint_slice_name: str
    k8s_ingress_name: str
    k8s_service_name: str
    limit_rps: str
    limit_whitelist: str
    max_body_size: str
    owasp_modsecurity_crs: bool
    owasp_modsecurity_custom_rules: str
    path_routes: List[str]
    proxy_read_timeout: str
    retry_errors: str
    rewrite_enabled: bool
    rewrite_target: str
    service_hostname: str
    service_name: str
    service_namespace: str
    service_port: int
    session_cookie_max_age: int
    tls_secret_name: str
    tls_cert: dict
    tls_key: dict
    upstream_endpoint_type: Optional[str]
    upstream_endpoints: List[str]
    use_endpoint_slice: bool
    whitelist_source_range: str

    @classmethod
    def from_essence(cls, essence: IngressDefinitionEssence) -> "IngressDefinition":
        """Create an IngressDefinition object from the given IngressDefinitionEssence instance.

        This method attempts to convert the provided essence into a valid IngressDefinition.
        If the conversion encounters an invalid state, it raises an InvalidIngressError.

        Args:
            essence: The precursor IngressObjectEssence object.

        Returns:
            IngressDefinition: A validated IngressOption object.
        """
        return cls(
            additional_hostnames=essence.additional_hostnames,
            backend_protocol=essence.backend_protocol,
            enable_access_log=essence.enable_access_log,
            ingress_class=essence.ingress_class,
            is_ingress_relation=essence.is_ingress_relation,
            k8s_endpoint_slice_name=essence.k8s_endpoint_slice_name,
            k8s_ingress_name=essence.k8s_ingress_name,
            k8s_service_name=essence.k8s_service_name,
            limit_rps=essence.limit_rps,
            limit_whitelist=essence.limit_whitelist,
            max_body_size=essence.max_body_size,
            owasp_modsecurity_crs=essence.owasp_modsecurity_crs,
            owasp_modsecurity_custom_rules=essence.owasp_modsecurity_custom_rules,
            path_routes=essence.path_routes,
            proxy_read_timeout=essence.proxy_read_timeout,
            retry_errors=essence.retry_errors,
            rewrite_enabled=essence.rewrite_enabled,
            rewrite_target=essence.rewrite_target,
            service_hostname=essence.service_hostname,
            service_name=essence.service_name,
            service_namespace=essence.service_namespace,
            service_port=essence.service_port,
            session_cookie_max_age=essence.session_cookie_max_age,
            tls_secret_name=essence.tls_secret_name,
            tls_cert=essence.tls_cert,
            tls_key=essence.tls_key,
            upstream_endpoint_type=essence.upstream_endpoint_type,
            upstream_endpoints=essence.upstream_endpoints,
            use_endpoint_slice=essence.use_endpoint_slice,
            whitelist_source_range=essence.whitelist_source_range,
        )

    @property
    def port_name(self) -> str:
        """Return the port name for ingress related objects."""
        return f"tcp-{self.service_port}"

    @property
    def pathroutes(self) -> List[str]:
        """Return the path routes to use for the k8s ingress."""
        if not all(path_route.startswith("/") for path_route in self.path_routes):
            raise InvalidIngressError("All path routes must start with a forward slash '/'")
        return self.path_routes
