Ingress in the Kubernetes context is [defined as](https://kubernetes.io/docs/concepts/services-networking/ingress/) “An API object that manages external access to the services in a cluster, typically HTTP. Ingress may provide load balancing, SSL termination and name-based virtual hosting.”

In the context of this operator, there are two key concepts to understand:

* The first is an ingress **controller**, which is a cluster-level service that provides ingress for applications.
* The second is an ingress **resource**, which is something defined by an application running within a cluster describing how ingress for it should be configured.

This operator configures an ingress **resource** which is then picked up by an ingress **controller** to determine how ingress for a given application is configured.

### What does this charm do?

To enable ingress via Nginx for [sidecar charms](https://discourse.charmhub.io/t/the-future-of-charmed-operators-on-kubernetes/4361), we’ve created this nginx-ingress-integrator charm. To use this charm you’ll need to have an Nginx Ingress Controller deployed into your K8s cluster.

The charm can be configured via a relation (see [this page](https://charmhub.io/nginx-ingress-integrator/libraries/ingress) for details on the ingress library as an easy method of integrating Operator Framework charms with it), or via `juju config` directly.

The reason for offering both relation and direct `juju config` support is that providing the relation means charm authors can make the experience better for end users by implementing the relation, but if a charm doesn’t yet implement the relation it can still be used with this charm and configured manually.

The charm supports the following via the relation:

* Rate limiting (with a whitelist for exclusions by CIDRs)
* Setting maximum allowed body size for file uploads
* Configuring retrying of errors against the next server
* A session cookie to use for cookie-based session affinity, and the age of that cookie
* The TLS certificate to use for your service if applicable

All of these options can also be configured at deploy time. In addition there’s also an `ingress-class` option to use, in the case that your cluster has multiple ingress controllers. This allows you to target the correct one.