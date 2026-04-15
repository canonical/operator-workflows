# Trivy

According to the [official documentation](https://aquasecurity.github.io/trivy/v0.36/), Trivy is a comprehensive and versatile security scanner. Trivy has scanners that look for security issues, and targets where it can find those issues.

## Description

By enabling Trivy in the integration test, the [Trivy GitHub action](https://github.com/aquasecurity/trivy-action) will run a scan in the repository (fs type) or a Docker image (image type) to find vulnerabilities.

The result will be available in the integration test output.

## How to use

Default configuration: will fail with exit code 1 for high and critical vulnerabilities.

Custom configurations can be set in a ``trivy.yaml`` file stored in the repository. The location should be set in ``trivy-image-config``parameters.

In order to reduce the manual work of upgrading the ``.trivyignore`` file, include the CVEs of binaries that you have no control over by using the ``skip-files`` option of the ``trivy.yaml`` file.

## Examples

### Custom configuration

```yaml
jobs:
  integration-tests:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    secrets: inherit
    with:
      trivy-image-config: tests/trivy/trivy.yaml
```

Example of trivy.yaml content:

```yaml
format: json
exit-code: 1
severity: CRITICAL
scan:
  skip-files:
    - usr/bin/pebble # this will ignore any CVEs caused by the pebble binary
```

See the [Config file](https://aquasecurity.github.io/trivy/v0.36/docs/references/customization/config-file/) for the options list.
