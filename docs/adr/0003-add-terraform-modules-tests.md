# 3. Add terraform modules tests

Date: 2026-02-12

## Status

Accepted

## Context

We initially had a workflow as part of our [charm template](https://github.com/canonical/platform-engineering-charm-template/). By moving it to this repository we aim at reducing the maintenance costs of all our repositories.

## Decision

The Terraform module tests are implemented as part of a reusable workflow and not as part of the integration tests.

Main motivation: Terraform currently needs the charm(s) to be available on Charmhub, so the tests wouldn't bring value during the integration tests.

The workflow deploys Canonical Kubernetes directly (not via [concierge](https://github.com/canonical/concierge/) for instance) to limit the steps to the strict minimum to speed up the CI.

## Consequences

We need to ensure that the `renovate` configuration is correct to ensure a PR will be created whenever a new release will be available in Charmhub.
