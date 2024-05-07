# How to add the Nginx-route relation.

The `nginx-route` relation is preferred over the `ingress`` relation if you want to use nginx-specific features, such as owasp-modsecurity-crs. If you need
something more generic then please follow the [ingress relation](https://charmhub.io/nginx-ingress-integrator/docs/add-the-ingress-relation) tutorial instead.

## Requirements

You will need:
* A laptop or desktop running Ubuntu (or you can use a VM).
* [Juju and Microk8s](https://juju.is/docs/olm/microk8s) installed. We'll also want to make sure the ingress add-on is enabled, which we can do by running `microk8s enable ingress`.
* [Charmcraft](https://juju.is/docs/sdk/install-charmcraft) installed.
* A code editor of your choice.

## Create a charm

First of all, let's create a very basic charm to add our relation to.
```
mkdir my-charm
cd my-charm
charmcraft init
```
You'll then see the following output:
```
Charmed operator package file and directory tree initialised.

Now edit the following package files to provide fundamental charm metadata and other information:

metadata.yaml
config.yaml
src/charm.py
README.md
```
Let's start by updating `metadata.yaml`. We want to update the `display-name` to "My Charm", and the `summary` and `description` to "A charm with a relation to nginx ingress integrator".

We can leave the other files as is for now, but if we want to publish this charm later, we'll want to update them before doing so.

## Deploy the charm

Now let's deploy the charm just to confirm everything is working as expected without the relation. To do that, just run this:
```
charmcraft pack
```
This will build the charm inside an LXC container. The output is the location of the built charm. For example, `my-charm_ubuntu-22.04-amd64.charm`.

Add a juju model and deploy the charm.
```
juju add-model ingress-test
juju deploy ./my-charm_ubuntu-22.04-amd64.charm --resource httpbin-image=kennethreitz/httpbin
```
To inspect the deployment, run `juju status`. Once the application reaches a status of `active idle` the application has been deployed. Visit it in a browser by getting the IP address of the unit and then going to `http://${ip_of_unit}`.

Note that `juju status` includes two IP addresses, one for the "Unit" and one for the "App". Here's an example:
```
Model         Controller          Cloud/Region        Version  SLA          Timestamp
ingress-test  microk8s-localhost  microk8s/localhost  2.9.37   unsupported  12:12:17+01:00

App       Version  Status  Scale  Charm     Channel  Rev  Address         Exposed  Message
my-charm           active      1  my-charm             0  10.152.183.205  no       

Unit         Workload  Agent  Address       Ports  Message
my-charm/0*  active    idle   10.1.129.139         
```

The steps thus far don't include ingress for the application. MicroK8s sets up networking in a way that unit IPs can be reached directly, but in a production Kubernetes cluster this is not the case. To allow real hostnames/IP addresses, configure Ingress.

## Add the Nginx-route relation

First of all, let's grab the [relation library](https://charmhub.io/nginx-ingress-integrator/libraries/ingress). We can do this by running this:
```
charmcraft fetch-lib charms.nginx_ingress_integrator.v0.nginx_route
```
This has downloaded `lib/charms/nginx_ingress_integrator/v0/nginx_route.py`. Now we just need to update `src/charm.py`.

Add the following just after `import logging`:
```
# Add this just after `import logging`.
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
```
Then add the following to the end of your charm's `__init__` method:
```
require_nginx_route(
    charm=self,
    service_hostname=self.config["external-hostname"] or self.app.name,
    service_name=self.app.name,
    service_port=8080 # assuming your app listens in port 8080
)
```
As you can see, we're adding support for a configuration option of `external-hostname` that will be used when configuring `nginx-route`. Let's update `config.yaml` to enable this. Add the following the end of that file:
```
  external-hostname:
    description: |
      The external hostname to use. Will default to the name of the deployed
      application.
    default: ""
    type: string
```
Now we just need to add the relation definition to `metadata.yaml`. Add the following to the end of that file:
```
requires:
  nginx-route:
    interface: nginx-route
```
Now let's rebuild our charm and run a charm upgrade.
```
charmcraft pack
juju refresh my-charm --path=./my-charm_ubuntu-22.04-amd64.charm
```
And now we can deploy the Nginx Ingress Integrator and add the relation:
```
juju deploy nginx-ingress-integrator
juju relate nginx-ingress-integrator my-charm
# If you have RBAC enabled, you'll also need to run this
juju trust nginx-ingress-integrator --scope cluster
```
Now we just wait until `juju status` reports `active idle` for both applications, and then we can get the IP of our ingress controller. We can do this by running `microk8s kubectl get pods -n ingress -o wide` and looking at the "IP" field. If we now add the following to `/etc/hosts` we'll be able to browse to `http://my-charm/` to get to the site:
```
${ingress-ip}    my-charm
```
We can also take a look at the configured ingress resource as follows (with sample output):
```
$ microk8s kubectl describe ingress -n ingress-test
Name:             my-charm-ingress
Labels:           app.juju.is/created-by=nginx-ingress-integrator
                  nginx-ingress-integrator.charm.juju.is/managed-by=nginx-ingress-integrator
Namespace:        ingress-test
Address:          127.0.0.1
Ingress Class:    public
Default backend:  <default>
Rules:
  Host        Path  Backends
  ----        ----  --------
  my-charm    
              /   my-charm-service:8080 (10.1.194.49:8080)
Annotations:  nginx.ingress.kubernetes.io/backend-protocol: HTTP
              nginx.ingress.kubernetes.io/proxy-body-size: 20m
              nginx.ingress.kubernetes.io/proxy-read-timeout: 60
              nginx.ingress.kubernetes.io/rewrite-target: /
              nginx.ingress.kubernetes.io/ssl-redirect: false
Events:
  Type    Reason  Age                   From                      Message
  ----    ------  ----                  ----                      -------
  Normal  Sync    4m3s (x2 over 4m22s)  nginx-ingress-controller  Scheduled for sync
```
Congratulations! You've configured your charm to have a relation to the Nginx Ingress Integrator Operator, and are ready to deploy your charm into a production Kubernetes cluster and easily make it available to external clients.
