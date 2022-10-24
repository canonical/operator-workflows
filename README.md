# operator-workflows

## Description

This repository includes several parametrized CI workflows to be used for both kubernetes and machine charms.

## Usage

To use the workflows in your repository, just reuse them including the `secrets: inherit` key. Examples of usage for every workflow can be found at the (indico operator)[https://github.com/canonical/indico-operator/blob/main/.github/workflows].

The following workflows are available:

* test: executes the default tox targets defined in the `tox.ini` file and generates a plain text report. The following parameters are available for this workflow:

| Name | Type | Default | Description
| runs-on| string | ubuntu-20.04 | Image runner for the test execution |

* comment: Posts the content of the artifact specified as a comment in a PR. It needs to be triggered from a PR triggered workflow.

* integration_test: Builds the existing Dockerfiles, if any, and executes the integration test target defined in the `tox.ini` file. The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|
| extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| provider | string | microk8s | Actions operator provider as defined (here)[https://github.com/charmed-kubernetes/actions-operator#usage] |
| runs-on | string | ubuntu-20.04 | Image runner for the test execution |
| series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to tox as --series argument |


* on_push: Builds and publishes the charm and its resources to appropriate channel, as defined (here)[https://github.com/canonical/charming-actions/tree/main/channel].  The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|
| integration-test-extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| integration-test-pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| integration-test-provider | string | microk8s | Actions operator provider as defined (here)[https://github.com/charmed-kubernetes/actions-operator#usage] |
| integration-test-series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to tox as --series argument |
| test-runs-on | string | ubuntu-20.04 | Image runner for the test execution |

* release: Promotes a charm from the selected origin channel to the selected target channel. . The following parameters are available for this workflow:
| Name | Type | Default | Description |
|--------------------|----------|--------------------|
| destination-channel | string | "" | Destination channel |
| origin-channel | string | "" | Origin channel |
