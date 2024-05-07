# How to contribute

## Overview

This document explains the processes and practices recommended for contributing enhancements to the Nginx Ingress Integrator operator.

* Generally, before developing enhancements to this charm, you should consider [opening an issue ](https://github.com/canonical/nginx-ingress-integrator-operator/issues)explaining your use case.

* If you would like to chat with us about your use-cases or proposed implementation, you can reach us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev) or [Discourse](https://discourse.charmhub.io/).

* Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library will help you a lot when working on new features or bug fixes.

* All enhancements require review before being merged. Code review typically examines

* code quality

* test coverage

* user experience for Juju administrators of this charm.

* Please help us out in ensuring easy to review branches by rebasing your pull request branch onto the `main` branch. This also avoids merge commits and creates a linear Git commit history.

## Developing

For any problems with this charm, please [report bugs here](https://github.com/canonical/nginx-ingress-integrator-operator/issues).

The code for this charm can be downloaded as follows:

```

git clone https://github.com/canonical/nginx-ingress-integrator-operator

```

To run tests, simply run `tox` from within the charm code directory.

To build and deploy a local version of the charm, simply run:

```

charmcraft pack

# Ensure you're connected to a juju k8s model, assuming you're on amd64

juju deploy ./nginx-ingress-integrator_ubuntu-20.04-amd64.charm

```

## Canonical contributor agreement

Canonical welcomes contributions to the Nginx Ingress Integrator Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you’re interested in contributing to the solution.