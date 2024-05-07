# How to add the Ingress relation.

The `ingress` relation is preferred over the `nginx-route` relation if you want to use generic features. If you need
something nginx-specific such as owasp-modsecurity-crs, then please follow the [nginx-route relation](https://charmhub.io/nginx-ingress-integrator/docs/add-the-nginx-route-relation) tutorial instead.

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
This will build the charm inside an LXC container for you. The output will tell you the location of the built charm. For example, `my-charm_ubuntu-22.04-amd64.charm`.

Now let's add a juju model and deploy our charm.
```
juju add-model ingress-test
juju deploy ./my-charm_ubuntu-22.04-amd64.charm --resource httpbin-image=kennethreitz/httpbin
```
To inspect the deployment, let's run `juju status`. Once the application reaches a status of `active idle` our application has been deployed. We can visit it in a browser by getting the IP address of the unit and then going to `http://${ip_of_unit}`.

Note that `juju status` includes two IP addresses, one for the "Unit" and one for the "App". Here's an example:
```
Model         Controller          Cloud/Region        Version  SLA          Timestamp
ingress-test  microk8s-localhost  microk8s/localhost  2.9.37   unsupported  12:12:17+01:00

App       Version  Status  Scale  Charm     Channel  Rev  Address         Exposed  Message
my-charm           active      1  my-charm             0  10.152.183.205  no       

Unit         Workload  Agent  Address       Ports  Message
my-charm/0*  active    idle   10.1.129.139         
```

So we now have a working charm, great! However, what we don't currently have is ingress for our application configured. MicroK8s sets up networking in such a way that you can reach the IPs of units directly, but in a production Kubernetes cluster things don't work in this way. Also, we're visiting a cluster-internal IP address directly, what if we want a real hostname/IP address for this? We'll need to configure Ingress for this to be possible.

Also, you may notice that you can visit the Unit IP address in a browser, but not the App IP address. Why is that? The reason is that the App IP address refers to a [Kubernetes Service](https://kubernetes.io/docs/concepts/services-networking/service/) so as you add other units to the charm they would in theory be reachable through the same IP. However, Juju doesn't have a mechanism for a charm to define what port that Service should be configured with, and this why we can't use it to browse the web site (which is listening on port 80).

## Add the Ingress relation

First of all, let's grab the [relation library](https://charmhub.io/nginx-ingress-integrator/libraries/ingress). We can do this by running this:
```
charmcraft fetch-lib charms.nginx_ingress_integrator.v0.ingress
```
This has downloaded `lib/charms/nginx_ingress_integrator/v0/ingress.py`. Now we just need to update `src/charm.py`.

Add the following just after `import logging`:
```
# Add this just after `import logging`.
from charms.nginx_ingress_integrator.v0.ingress import IngressRequires
```
Then add the following to the end of your charm's `__init__` method:
```
self.ingress = IngressRequires(self, {"service-hostname": self.config["external-hostname"] or self.app.name,
                                      "service-name": self.app.name,
                                      "service-port": 80})
```
And now add the following to top of the `_on_config_changed` method:
```
self.ingress.update_config({"service-hostname": self.config["external-hostname"] or self.app.name})
```
As you can see, we're adding support for a configuration option of `external-hostname` that will be used when configuring ingress. Let's update `config.yaml` to enable this. Add the following the end of that file:
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
  ingress:
    interface: ingress
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
              /   my-charm-service:80 (10.1.129.140:80)
Annotations:  nginx.ingress.kubernetes.io/proxy-body-size: 20m
              nginx.ingress.kubernetes.io/rewrite-target: /
              nginx.ingress.kubernetes.io/ssl-redirect: false
Events:
  Type    Reason  Age                   From                      Message
  ----    ------  ----                  ----                      -------
  Normal  Sync    3m30s (x2 over 4m6s)  nginx-ingress-controller  Scheduled for sync
```
Congratulations! You've configured your charm to have a relation to the Nginx Ingress Integrator Operator, and are ready to deploy your charm into a production Kubernetes cluster and easily make it available to external clients.
