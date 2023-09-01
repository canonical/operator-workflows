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
| self-hosted-runner | bool | true | Whether self-hosted-runner should be enabled |
| pre-run-script | string | "" | Path to the bash script to be run before the integration tests |

* comment: Posts the content of the artifact specified as a comment in a PR. It needs to be triggered from a PR triggered workflow.

* integration_test: Builds the existing Dockerfiles, if any, and executes the `integration` test target defined in the `tox.ini` file. This workflow also supports running addtional load and chaos tests. The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| channel | string | latest/stable | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| chaos-enabled  | bool | false | Whether Chaos testing is enabled |
| chaos-experiments | string | "" | List of experiments to run |
| chaos-namespace | string | testing | Namespace to install Litmus Chaos |
| chaos-app-namespace | string | testing | Namespace of chaos tested application |
| chaos-app-label | string | "" | Label for chaos selection |
| chaos-app-kind | string | statefulset | Application kind |
| chaos-duration | string | 60 | Duration of the chaos experiment |
| extra-arguments | string | "" | Additional arguments to pass to the integration test execution |
| extra-test-matrix | string | '{}' | Additional test matrices to run the integration test combinations |
| image-build-args | string | "" | List of build args to pass to the build image job |
| juju-channel | string | 2.9/stable | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| load-test-enabled | bool | false | Whether load testing is enabled. If enabled, k6 will expect a load_tests/load-test.js file with the tests to run. |
| load-test-run-args | string | "" | Command line arguments for the load test execution. |
| modules | string | '[""]' | List of modules to run in parallel in JSON format, i.e. '["foo", "bar"]'. Each element will be passed to pytest through tox as -k argument |
| pre-run-script | string | "" | Path to the bash script to be run before the integration tests |
| provider | string | microk8s | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
| microk8s-addons | string | "dns ingress rbac storage" | Microk8s provider add-ons override. A minimum set of addons (the defaults) must be enabled. |
| series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to pytest through tox as --series argument |
| setup-devstack-swift | bool | false | Use setup-devstack-swift action to prepare a swift server for testing. |
| tmate-debug | bool | false | Enable tmate debugging after integration test failure. |
| tmate-timeout | number | 30 | Timeout in minutes to keep tmate debugging session. |
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

The following secrets are available for this workflow:

| Name | Description |
|--------------------|-------------------|
| INTERGRATION_TEST_ARGS | Additional arguments to pass to the integration test execution that contain secrets |

When running the integration tests, the following posargs will be automatically passed to the `integration` target:

* --charm-file [charm_file_name]: The name of the charm artifact generated prior to the integration tests run
* --series [series]: As defined in the `series` configuration described option above
* -k [module]: As defined in the `modules` configuration option described above
* --keep-models
* --model testing: Only for tests running on a microk8s substrate
* One parameter per resource defined in the `metadata.yaml` of the charm, containing a reference to the built image

For instance, for pytest you can leverage this by adding a conftest.py file

```python
def pytest_addoption(parser):
    """Add test arguments."""
    parser.addoption("--charm-file", action="store")
```

and then use the argument value

```python
charm = pytestconfig.getoption("--charm-file")
```

* publish_charm: Publishes the charm and its resources to appropriate channel, as defined [here](https://github.com/canonical/charming-actions/tree/main/channel).

This workflow requires a `CHARMHUB_TOKEN` secret containing a charmhub token with package-manage and package-view permissions for the charm and the destination channel. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth) and a `REPO_ACCESS_TOKEN` secret containg a classic PAT with full repository permissions. See how to generate it [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic).

The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| channel | string | latest/edge | Destination channel to push the charm to |
| working-directory | string | "./" | Directory where jobs should be executed |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* promote_charm: Promotes a charm from the selected origin channel to the selected target channel.

This workflow requires a `CHARMHUB_TOKEN` secret containing a charmhub token with package-manage and package-view permissions for the charm and the origin and destination channels. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).

The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| destination-channel | string | "" | Destination channel |
| origin-channel | string | "" | Origin channel |
| architecture | string | amd64 | Charm architecture |
| doc-automation-disabled | boolean | true | Whether the documentation automation is disabled |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* auto_update_charm_libs: Checks if updates to the charm libraries are available and, of necessary,  opens a pull request to update them.

This workflow requires `pull_request` and `content` write permissions and a `CHARMHUB_TOKEN` secret containing a charmhub token. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).
