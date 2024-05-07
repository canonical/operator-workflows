At it’s core, Nginx Ingress Integrator is a basic charm that talks to the Kubernetes API and provisions an Nginx ingress resource.

In designing this charm, we've leveraged Juju's sidecar pattern for Kubernetes charms, but somewhat unusually we're not actually deploying a workload container alongside our charm code. Instead, the charm code is talking directly to the Kubernetes API to provision the appropriate Nginx ingress resource to enable traffic to reach the service in question. 

As a result, if you run a `kubectl get pods` on a namespace named for the Juju model you’ve deployed the nginx-ingress-integrator charm into, you’ll see something like the following:

```
NAME                             READY   STATUS    RESTARTS   AGE
nginx-ingress-integrator-0       1/1     Running   0          3h47m

```

This shows there is only one container, for the charm code itself.