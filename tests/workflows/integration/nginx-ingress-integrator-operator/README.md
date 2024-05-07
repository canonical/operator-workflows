[![CharmHub Badge](https://charmhub.io/nginx-ingress-integrator/badge.svg)](https://charmhub.io/nginx-ingress-integrator)
[![Publish to edge](https://github.com/canonical/nginx-ingress-integrator-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/nginx-ingress-integrator-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/nginx-ingress-integrator-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/nginx-ingress-integrator-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying and managing external access to HTTP/HTTPS services in a
Kubernetes cluster via an Nginx Ingress resource. This requires the Kubernetes
cluster in question to have an [Nginx Ingress Controller](https://docs.nginx.com/nginx-ingress-controller/) already deployed into it.

This charm simplifies exposing services running inside a Kubernetes cluster to
external clients. It offers TLS termination as well as easy configuration of a
number of advanced features including rate limiting, restricting access to
specific client IP source ranges, and OWASP ModSecurity Core Rule Set (CRS).

As such, the charm makes it easy for charm developers to provide external
access to their HTTP workloads in Kubernetes by easy integration offered via
[the charm's ingress library](https://charmhub.io/nginx-ingress-integrator/libraries/ingress).

For DevOps and SRE teams, providing ingress for charms that support a relation
to this charm will be possible via a simple `juju relate` command.

## Project and community

The Nginx Ingress Integrator Operator is a member of the Ubuntu family. It's an
open source project that warmly welcomes community projects, contributions,
suggestions, fixes and constructive feedback.
* [Code of conduct](https://ubuntu.com/community/code-of-conduct)
* [Get support](https://discourse.charmhub.io/)
* [Join our online chat](https://chat.charmhub.io/charmhub/channels/charm-dev)
* [Contribute](https://charmhub.io/nginx-ingress-integrator/docs/contributing)
* [Roadmap](https://charmhub.io/nginx-ingress-integrator/docs/roadmap)
Thinking about using the Nginx Ingress Integrator for your next project? [Get in touch](https://chat.charmhub.io/charmhub/channels/charm-dev)!

---

For further details,
[see the charm's detailed documentation](https://charmhub.io/nginx-ingress-integrator/docs).
