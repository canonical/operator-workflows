# operator-workflows

## Description

This repository includes several parametrized CI workflows to be used for both kubernetes and machine charms.

## Usage

To use the workflows in your repository, just reuse them including the `secrets: inherit` key. Examples of usage for every workflow can be found at the (indico operator)[https://github.com/canonical/indico-operator/blob/main/.github/workflows]. Note that you will need a CHARMHUB_TOKEN amoung your repository secrets to be able to run the workflows that interact with charmhub.

The following workflows are available:

* test: executes the default tox targets defined in the `tox.ini` file and generates a plain text report.

* comment: Posts the content of the artifact specified as a comment in a PR. It needs to be triggered from a PR triggered workflow.

* integration_test: Builds the existing Dockerfiles, if any, and executes the integration test target defined in the `tox.ini` file. The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| provider | string | microk8s | Actions operator provider as defined (here)[https://github.com/charmed-kubernetes/actions-operator#usage] |
| series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to tox as --series argument |


* test_and_publish_charm: Builds and publishes the charm and its resources to appropriate channel, as defined (here)[https://github.com/canonical/charming-actions/tree/main/channel].  The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| integration-test-extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| integration-test-pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| integration-test-provider | string | microk8s | Actions operator provider as defined (here)[https://github.com/charmed-kubernetes/actions-operator#usage] |
| integration-test-series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to tox as --series argument |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* promote_charm: Promotes a charm from the selected origin channel to the selected target channel. . The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| destination-channel | string | "" | Destination channel |
| origin-channel | string | "" | Origin channel |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.
