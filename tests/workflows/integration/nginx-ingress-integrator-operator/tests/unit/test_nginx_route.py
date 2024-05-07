# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""nginx-ingress-integrator charm unit tests."""


import textwrap

import kubernetes.client
from ops.testing import Harness

from consts import CREATED_BY_LABEL
from tests.unit.conftest import K8sStub
from tests.unit.constants import TEST_NAMESPACE


def test_basic(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: update the nginx-route relation with basic data.
    assert: validate ingress and service are created appropriately.
    """
    harness.begin()
    nginx_route_relation.update_app_data(nginx_route_relation.gen_example_app_data())
    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 1
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.labels[CREATED_BY_LABEL] == harness.charm.app.name
    assert len(ingress.spec.rules) == 1
    assert ingress.spec.rules[0].host == "example.com"
    assert len(k8s_stub.get_services(TEST_NAMESPACE)) == 1
    service = k8s_stub.get_services(TEST_NAMESPACE)[0]
    assert service.spec.selector == {"app.kubernetes.io/name": "app"}
    assert len(service.spec.ports) == 1
    assert service.spec.ports[0].port == 8080
    assert service.spec.ports[0].target_port == 8080
    assert not k8s_stub.get_endpoint_slices(TEST_NAMESPACE)


def test_relation_broken(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: update the nginx-route relation with basic data then remove the relation.
    assert: validate ingress and service are cleaned up.
    """
    harness.begin()
    nginx_route_relation.update_app_data(nginx_route_relation.gen_example_app_data())
    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 1
    assert len(k8s_stub.get_services(TEST_NAMESPACE)) == 1

    # ops testing harness emit relation-broken before the relation is removed
    harness.disable_hooks()
    nginx_route_relation.remove_relation()
    harness.charm.on["nginx-route"].relation_broken.emit(nginx_route_relation.relation)

    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 0
    assert len(k8s_stub.get_services(TEST_NAMESPACE)) == 0


def test_remove_old_resources(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: create some unused resources in the k8s cluster.
    assert: validate unused ingress and service are cleaned up.
    """
    harness.begin()
    k8s_stub.create_namespaced_resource(
        "service",
        namespace=TEST_NAMESPACE,
        body=kubernetes.client.V1Service(
            metadata=kubernetes.client.V1ObjectMeta(
                name="app-service", annotations={CREATED_BY_LABEL: harness.charm.app.name}
            ),
            spec=kubernetes.client.V1ServiceSpec(),
        ),
    )
    k8s_stub.create_namespaced_resource(
        "ingress",
        namespace=TEST_NAMESPACE,
        body=kubernetes.client.V1Ingress(
            metadata=kubernetes.client.V1ObjectMeta(
                name="example-com-ingress", annotations={CREATED_BY_LABEL: harness.charm.app.name}
            )
        ),
    )
    assert len(k8s_stub.get_services(TEST_NAMESPACE)) == 1
    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 1

    nginx_route_relation.update_app_data(nginx_route_relation.gen_example_app_data())
    assert len(k8s_stub.get_services(TEST_NAMESPACE)) == 1
    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 1
    assert k8s_stub.get_services(TEST_NAMESPACE)[0].metadata.name != "app-service"
    assert k8s_stub.get_ingresses(TEST_NAMESPACE)[0].metadata.name != "example-com-ingress"


def test_additional_hostnames(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the additional-hostnames in the nginx-route relation and charm config.
    assert: ingress rules are updated according to the additional-hostname value.
    """
    relation_data = {
        **nginx_route_relation.gen_example_app_data(),
        "additional-hostnames": "www.example.com",
    }
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    rules = ingress.spec.rules
    assert len(rules) == 2
    assert set(r.host for r in rules) == {"example.com", "www.example.com"}
    harness.update_config({"additional-hostnames": "example.net,example.org"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    rules = ingress.spec.rules
    assert len(rules) == 3
    assert set(r.host for r in rules) == {"example.com", "example.net", "example.org"}


def test_backend_protocol(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the backend-protocol in the nginx-route relation and charm config.
    assert: ingress annotations are updated according to the additional-hostname value.
    """
    relation_data = nginx_route_relation.gen_example_app_data()
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/backend-protocol"] == "HTTP"
    relation_data["backend-protocol"] = "HTTPS"
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/backend-protocol"] == "HTTPS"
    harness.update_config({"backend-protocol": "GRPC"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/backend-protocol"] == "GRPC"


def test_backend_protocol_error(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the backend-protocol in the nginx-route relation with an incorrect value.
    assert: charm should enter blocked state.
    """
    relation_data = {
        **nginx_route_relation.gen_example_app_data(),
        "backend-protocol": "FOO",
    }
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    assert k8s_stub.get_ingresses(TEST_NAMESPACE) == []
    assert harness.charm.unit.status.name == "blocked"


def test_disable_access_log(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the disable-access-log in the nginx-route relation.
    assert: ingress annotations are updated according to the disable-access-log value.
    """
    relation_data = nginx_route_relation.gen_example_app_data()
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert "nginx.ingress.kubernetes.io/enable-access-log" not in ingress.metadata.annotations
    relation_data["enable-access-log"] = "false"
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/enable-access-log"] == "false"
    relation_data["enable-access-log"] = "true"
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert "nginx.ingress.kubernetes.io/enable-access-log" not in ingress.metadata.annotations
    harness.update_config({"enable-access-log": False})
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/enable-access-log"] == "false"
    harness.update_config({"enable-access-log": True})
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert "nginx.ingress.kubernetes.io/enable-access-log" not in ingress.metadata.annotations


def test_ingress_class(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the ingress-class in charm config.
    assert: ingress should contain correct ingres class attribute.
    """
    relation_data = nginx_route_relation.gen_example_app_data()
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.spec.ingress_class_name == "nginx-ingress"
    harness.update_config({"ingress-class": "bar"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.spec.ingress_class_name == "bar"


def test_multiple_ingress_class(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set multiple default ingress classes in kubernetes test stub.
    assert: ingress should contain no ingress class.
    """
    relation_data = nginx_route_relation.gen_example_app_data()
    k8s_stub.ingress_classes.append(
        kubernetes.client.V1IngressClass(
            metadata=kubernetes.client.V1ObjectMeta(
                annotations={"ingressclass.kubernetes.io/is-default-class": "true"},
                name="foobar",
            )
        )
    )
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.spec.ingress_class_name is None


def test_limit_rps(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the limit-rps in relation and charm config.
    assert: ingress should contain correct limit-rps annotation.
    """
    relation_data = {**nginx_route_relation.gen_example_app_data(), "limit-rps": "100"}
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/limit-rps"] == "100"
    harness.update_config({"limit-rps": 1000})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/limit-rps"] == "1000"


def test_limit_whitelist(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the limit-whitelist in relation and charm config.
    assert: ingress should contain correct limit-whitelist annotations.
    """
    relation_data = {
        **nginx_route_relation.gen_example_app_data(),
        "limit-whitelist": "10.0.0.0/8",
    }
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert "nginx.ingress.kubernetes.io/limit-rps" not in ingress.metadata.annotations
    assert "nginx.ingress.kubernetes.io/limit-whitelist" not in ingress.metadata.annotations
    relation_data["limit-rps"] = "100"
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert (
        ingress.metadata.annotations["nginx.ingress.kubernetes.io/limit-whitelist"] == "10.0.0.0/8"
    )
    harness.update_config({"limit-whitelist": "1.0.0.0/24"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert (
        ingress.metadata.annotations["nginx.ingress.kubernetes.io/limit-whitelist"] == "1.0.0.0/24"
    )


def test_max_body_size(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the max-body-size in relation and charm config.
    assert: ingress should contain correct limit-whitelist annotations.
    """
    relation_data = nginx_route_relation.gen_example_app_data()
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/proxy-body-size"] == "20m"
    relation_data["max-body-size"] = "100"
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    # TODO: max-body-size default config shadows the relation
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/proxy-body-size"] == "20m"


def test_owasp_modsecurity_crs(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the modsecurity option in relation and charm config.
    assert: ingress should contain correct modsecurity annotations.
    """
    relation_data = {
        **nginx_route_relation.gen_example_app_data(),
        "owasp-modsecurity-crs": "True",
    }
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/enable-modsecurity"] == "true"
    assert (
        ingress.metadata.annotations["nginx.ingress.kubernetes.io/enable-owasp-modsecurity-crs"]
        == "true"
    )
    assert ingress.metadata.annotations[
        "nginx.ingress.kubernetes.io/modsecurity-snippet"
    ] == textwrap.dedent(
        """\
        SecRuleEngine On\n
        Include /etc/nginx/owasp-modsecurity-crs/nginx-modsecurity.conf"""
    )


def test_owasp_modsecurity_custom_rules(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the modsecurity option in relation and charm config.
    assert: ingress should contain correct modsecurity annotations.
    """
    custom_rule = (
        'SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"\n'
    )
    relation_data = {
        **nginx_route_relation.gen_example_app_data(),
        "owasp-modsecurity-custom-rules": custom_rule,
    }
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert "nginx.ingress.kubernetes.io/modsecurity-snippet" not in ingress.metadata.annotations
    relation_data["owasp-modsecurity-crs"] = "TRUE"
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations[
        "nginx.ingress.kubernetes.io/modsecurity-snippet"
    ] == textwrap.dedent(
        """\
        SecRuleEngine On
        SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"\n
        Include /etc/nginx/owasp-modsecurity-crs/nginx-modsecurity.conf"""
    )


def test_path_routes(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the path-routes option in relation and charm config.
    assert: ingress should contain correct path definition.
    """
    relation_data = nginx_route_relation.gen_example_app_data()
    harness.begin()
    nginx_route_relation.update_app_data(relation_data)
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert [p.path for p in ingress.spec.rules[0].http.paths] == ["/"]
    relation_data["path-routes"] = "/foo,/bar"
    nginx_route_relation.update_app_data(relation_data)
    assert len(k8s_stub.get_ingresses(TEST_NAMESPACE)) == 1
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert [p.path for p in ingress.spec.rules[0].http.paths] == ["/foo", "/bar"]
    harness.update_config({"path-routes": "/foobar"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert [p.path for p in ingress.spec.rules[0].http.paths] == ["/foobar"]


def test_proxy_read_timeout(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the proxy-read-timeout option in relation and charm config.
    assert: ingress should contain correct proxy-read-timeout annotations.
    """
    harness.begin()
    nginx_route_relation.update_app_data(
        {**nginx_route_relation.gen_example_app_data(), "proxy-read-timeout": "100"}
    )
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    # TODO: proxy-read-timeout default config shadows the relation
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] == "60"
    harness.update_config({"proxy-read-timeout": 120})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] == "120"


def test_retry_errors(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the retry-errors option in relation and charm config.
    assert: ingress should contain correct proxy-next-upstream annotations.
    """
    harness.begin()
    nginx_route_relation.update_app_data(
        {**nginx_route_relation.gen_example_app_data(), "retry-errors": "http_503"}
    )
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert (
        ingress.metadata.annotations["nginx.ingress.kubernetes.io/proxy-next-upstream"]
        == "http_503"
    )
    harness.update_config({"retry-errors": "http_500,foobar"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    # invalid retry errors are ignored
    assert (
        ingress.metadata.annotations["nginx.ingress.kubernetes.io/proxy-next-upstream"]
        == "http_500"
    )


def test_rewrite_enabled(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the rewrite-enabled option in relation and charm config.
    assert: ingress should contain correct rewrite-target annotations.
    """
    harness.begin()
    nginx_route_relation.update_app_data(nginx_route_relation.gen_example_app_data())
    harness.update_config({"rewrite-enabled": True})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/rewrite-target"] == "/"
    harness.update_config({"rewrite-enabled": False})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert "nginx.ingress.kubernetes.io/rewrite-target" not in ingress.metadata.annotations


def test_rewrite_target(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the rewrite-target option in relation and charm config.
    assert: ingress should contain correct rewrite-target annotations.
    """
    harness.begin()
    harness.update_config({"rewrite-enabled": True})
    nginx_route_relation.update_app_data(
        {**nginx_route_relation.gen_example_app_data(), "rewrite-target": "/foo"}
    )
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/rewrite-target"] == "/foo"
    harness.update_config({"rewrite-target": "/bar"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.metadata.annotations["nginx.ingress.kubernetes.io/rewrite-target"] == "/bar"


def test_session_cookie_max_age(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the session-cookie-max-age option in relation and charm config.
    assert: ingress should contain correct session cookie annotations.
    """
    harness.begin()
    nginx_route_relation.update_app_data(
        {**nginx_route_relation.gen_example_app_data(), "session-cookie-max-age": "100"}
    )
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    annotations = ingress.metadata.annotations
    assert annotations["nginx.ingress.kubernetes.io/affinity"] == "cookie"
    assert annotations["nginx.ingress.kubernetes.io/affinity-mode"] == "balanced"
    assert annotations["nginx.ingress.kubernetes.io/session-cookie-change-on-failure"] == "true"
    assert annotations["nginx.ingress.kubernetes.io/session-cookie-max-age"] == "100"
    assert annotations["nginx.ingress.kubernetes.io/session-cookie-name"] == "APP_AFFINITY"
    assert annotations["nginx.ingress.kubernetes.io/session-cookie-samesite"] == "Lax"


def test_tls_secret_name(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the tls-secret-name option in relation and charm config.
    assert: ingress should contain correct TLS settings.
    """
    harness.begin()
    nginx_route_relation.update_app_data(
        {**nginx_route_relation.gen_example_app_data(), "tls-secret-name": "secret"}
    )
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    # TODO: ingress tls contains only the service-hostname, not including additional-hostnames
    assert len(ingress.spec.tls) == 1
    assert ingress.spec.tls[0].secret_name == "secret"  # nosec
    harness.update_config({"tls-secret-name": "new-secret"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert ingress.spec.tls[0].secret_name == "new-secret"  # nosec


def test_whitelist_source_range(k8s_stub: K8sStub, harness: Harness, nginx_route_relation):
    """
    arrange: set up test harness and nginx-route relation.
    act: set the whitelist-source-range option in charm config.
    assert: ingress should contain correct whitelist-source-range annotations.
    """
    harness.begin()
    nginx_route_relation.update_app_data(nginx_route_relation.gen_example_app_data())
    harness.update_config({"whitelist-source-range": "10.0.0.0/8"})
    ingress = k8s_stub.get_ingresses(TEST_NAMESPACE)[0]
    assert (
        ingress.metadata.annotations["nginx.ingress.kubernetes.io/whitelist-source-range"]
        == "10.0.0.0/8"
    )
