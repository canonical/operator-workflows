# operator-workflows

## Description

This repository includes several parametrized CI workflows to be used for both kubernetes and machine charms.

## Usage

To use the workflows in your repository, just reuse them including the `secrets: inherit` key. Examples of usage for every workflow can be found at the [indico operator](https://github.com/canonical/indico-operator/blob/main/.github/workflows). Note that you will need a CHARMHUB_TOKEN among your repository secrets to be able to run the workflows that interact with charmhub.

The following workflows are available:

* test: executes the default tox targets defined in the `tox.ini` file and generates a plain text report. This requires the `lint`, `unit`, `static` and `coverage-report` `tox` environments to be included in the tox defaults. The following parameters are available for this workflow:


| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| working-directory | string | "./" | Directory where jobs should be executed |

* comment: Posts the content of the artifact specified as a comment in a PR. It needs to be triggered from a PR triggered workflow.

* integration_test: Builds the existing Dockerfiles, if any, and executes the `integration` test target defined in the `tox.ini` file. This workflow also supports running addtional load and chaos tests. The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| chaos-enabled  | bool | false | Whether Chaos testing is enabled |
| chaos-experiments | string | "" | List of experiments to run |
| chaos-namespace | string | testing | Namespace to install Litmus Chaos |
| chaos-app-namespace | string | testing | Namespace of chaos tested application |
| chaos-app-label | string | "" | Label for chaos selection |
| chaos-app-kind | string | statefulset | Application kind |
| chaos-duration | string | 60 | Duration of the chaos experiment |
| extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| extra-test-matrix | string | '{}' | Additional test matrices to run the integration test combinations |
| load-test-enabled | bool | false | Whether load testing is enabled. If enabled, k6 will expect a load_tests/load-test.js file with the tests to run. |
| load-test-run-args | string | "" | Command line arguments for the load test execution. |
| modules | string | '[""]' | List of modules to run in parallel in JSON format, i.e. '["foo", "bar"]'. Each element will be passed to pytest through tox as -k argument |
| pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| provider | string | microk8s | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| microk8s-addons | string | "storage dns rbac" | Microk8s provider add-ons override. A minimum set of addons (the defaults) must be enabled. |
| channel | string | latest/stable | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| juju-channel | string | 2.9/stable | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to pytest through tox as --series argument |
| setup-devstack-swift | bool | false | Use setup-devstack-swift action to prepare a swift server for testing. |
| tmate-debugging | bool | false | Enable tmate debugging after integration test failure. |
| trivy-fs-config | string | "" | Trivy YAML configuration for fs type |
| trivy-fs-enabled | boolean | false | Whether Trivy testing of type fs is enabled |
| trivy-fs-ref | string | "." | Target directory to do the Trivy testing |
| trivy-image-config | string | "" | Trivy YAML configuration for image type |
| working-directory | string | "./" | Custom working directory for jobs to run on |
| zap-auth-header | string | "" | If this is defined then its value will be added as a header to all of the ZAP requests |
| zap-auth-header-value | string | "" | If this is defined then its value will be used as the header name to all of the ZAP requests |
| zap-before-command | string | "" | Command to run before ZAP testing |
| zap-cmd-options | string | "-T 60" | Options to be used by ZAP. Default sets maximum scanning time to 60 minutes |
| zap-enabled | boolean | false | Whether ZAP testing is enabled |
| zap-target | string | "" | If this is not set, the unit IP address will be used as ZAP target |
| zap-target-protocol | string | "http" | ZAP target protocol |
| zap-target-port | string | 80 | ZAP target port |
| zap-rules-file-name | string | "" | Rules file to ignore any alerts from the ZAP scan |

More information about OWASP ZAP testing can be found [here](OWASPZAP.md).

More information about Trivy testing can be found [here](TRIVY.MD).

* test_and_publish_charm: Builds and publishes the charm and its resources to appropriate channel, as defined [here](https://github.com/canonical/charming-actions/tree/main/channel).  The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| channel | string | latest/edge | Destination channel to push the charm to
| integration-test-extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| integration-test-extra-test-matrix | string | '{}' | Additional test matrices to run the integration test combinations |
| integration-test-pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| integration-test-provider | string | microk8s | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| integration-test-microk8s-addons | string | "storage dns rbac" | Microk8s provider add-ons override. A minimum set of addons (the defaults) must be enabled. |
| integration-test-provider-channel | string | latest/stable | Actions operator provider channel as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| integration-test-juju-channel | string | 2.9/stable | Actions operator juju channel as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| integration-test-series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to pytest through tox as --series argument |
| integration-test-modules | string | '[""]' | List of modules to run in parallel in JSON format, i.e. '["foo", "bar"]'. Each element will be passed to pytest through tox as -k argument |
| setup-devstack-swift | bool | false | Use setup-devstack-swift action to prepare a swift server for integration tests. |
| trivy-fs-config | string | "" | Trivy YAML configuration for fs type |
| trivy-fs-enabled | boolean | false | Whether Trivy testing of type fs is enabled |
| trivy-fs-ref | string | "." | Target directory to do the Trivy testing |
| trivy-image-config | string | "" | Trivy YAML configuration for image type |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* promote_charm: Promotes a charm from the selected origin channel to the selected target channel. . The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| destination-channel | string | "" | Destination channel |
| origin-channel | string | "" | Origin channel |
| architecture | string | amd64 | Charm architecture |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* auto_update_charm_libs: Checks if updates to the charm libraries are available and, of necessary,  opens a pull request to update them. This workflow requires `pull_request` and `content` write permissions.
