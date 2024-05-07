# How to support multiple relations

This charm supports multiple relations, allowing you to configure a set of applications within the same model to share the same nginx-ingress-integrator instance.

However, there are a few things to bear in mind when doing so:

* This is designed for applications that have been written with the intention of being related to the same nginx-ingress-integrator charm.

* If the charms related to the nginx-ingress-integrator charm would result in different annotations being created on the same ingress object, the charm will go into a `blocked` state and prompt the user to resolve these conflicts by setting `juju config` on the nginx-ingress-integrator charm.

* If the charms related to the nginx-ingress-integrator charm have duplicates in their `path-routes`, the charm will go into a `blocked` state and inform the user that there is a conflict.

* If multiple applications are related to a single nginx-ingress-integrator charm, the `service-name`, `service-port` and `path-routes` configurations options will be ignored. This is because allowing the values passed to those via the relation could potentially break the applications, because they would be applied to all.

It is recommended that only applications that have been explicitly written to work with the same nginx-ingress-integrator charm are related in this way. It is also recommended that this is configured in such a way that only one external hostname is generated (although the `additional-hostnames` configuration option can still be used to duplicate the ingress definitions for other hostnames). If you have applications in your model that need to respond on different external hostnames, it is recommended to deploy a separate instance of the nginx-ingress-integrator charm for each.