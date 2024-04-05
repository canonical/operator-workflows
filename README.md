# operator-workflows

## Description

This repository includes several parametrized CI workflows to be used for both kubernetes and machine charms.

## Usage

To use the workflows in your repository, just reuse them including the `secrets: inherit` key. Examples of usage for every workflow can be found at the [indico operator](https://github.com/canonical/indico-operator/blob/main/.github/workflows). Note that you will need a CHARMHUB_TOKEN among your repository secrets to be able to run the workflows that interact with charmhub.

The following workflows are available:

* test: executes the default tox targets defined in the `tox.ini` file and generates a plain text report. This requires the `lint`, `unit`, `static` and `coverage-report` `tox` environments to be included in the tox defaults. The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| charm-working-directory | string | Null | The working directory for the charm. docs directory, if existing, should be under this directory |
| working-directory | string | "./" | Directory where jobs should be executed |
| self-hosted-runner | bool | true | Whether self-hosted-runner should be enabled |
| self-hosted-runner-label| string | large | Label used to select the self-hosted runner if enabled |
| pre-run-script | string | "" | Path to the bash script to be run before the integration tests |

* comment: Posts the content of the artifact specified as a comment in a PR. It needs to be triggered from a PR triggered workflow.

* integration_test: Builds the existing Dockerfiles, if any, and executes the `integration` test target defined in the `tox.ini` file. The tox environment used can be changed with the `test-tox-env` input. The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| charmcraft-channel       | string | latest/stable | Charmcraft channel to use for the integration test |
| charmcraft-ref           | string | "" | Used in conjunction with charmcraft-repository to pull and build charmcraft from source instead of using snapstore version. |
| charmcraft-repository    | string | "" | Pull and build charmcraft from source instead of using snapstore version (this means that the `charmcraft-channel` input will be ignored). |
| channel | string | latest/stable | Actions operator provider as defined [here](https://github.com/charmed-kubernetes/actions-operator#usage) |
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
| rockcraft-channel        | string | latest/stable | Rockcraft channel to use for the integration test |
| rockcraft-ref            | string | "" | Used in conjunction with rockcraft-repository to pull and build rockcraft from source instead of using snapstore version. |
| rockcraft-repository     | string | "" | Pull and build rockcraft from source instead of using snapstore version (this means that the `rockcraft-channel` input will be ignored). |
| self-hosted-runner| bool | false | Whether to use self-hosted runner for tests. |
| self-hosted-runner-label | string | large | Label to filter the self-hosted runner, if the self-hosted runners are used. |
| series | string | '[""]' | List of series to run the tests in JSON format, i.e. '["jammy", "focal"]'. Each element will be passed to pytest through tox as --series argument |
| setup-devstack-swift | bool | false | Use setup-devstack-swift action to prepare a swift server for testing. |
| test-timeout | number | 360 | The timeout in minutes for the integration test |
| test-tox-env | string | "integration" | The tox environment name for the integration test. |
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
| INTEGRATION_TEST_ARGS | Additional arguments to pass to the integration test execution that contain secrets |

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

tmate can be run on failed tests either by setting the `tmate-debug` input to 'true' or by re-running a job with the "Enable debug logging" checkbox checked.

* publish_charm: Publishes the charm and its resources to appropriate channel, as defined [here](https://github.com/canonical/charming-actions/tree/main/channel).

This workflow requires a `CHARMHUB_TOKEN` secret containing a charmhub token with package-manage and package-view permissions for the charm and the destination channel. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth) and a `REPO_ACCESS_TOKEN` secret containg a classic PAT with full repository permissions. See how to generate it [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic).

The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| channel | string | latest/edge | Destination channel to push the charm to |
| charm-working-directory | string | Null | The working directory for the charm. docs directory, if existing, should be under this directory |
| charmcraft-channel       | string | latest/stable | Charmcraft channel to use for the integration test |
| working-directory | string | "./" | Directory where jobs should be executed |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* promote_charm: Promotes a charm from the selected origin channel to the selected target channel.

This workflow requires a `CHARMHUB_TOKEN` secret containing a charmhub token with package-manage and package-view permissions for the charm and the origin and destination channels. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).

The following parameters are available for this workflow:

| Name | Type | Default | Description |
|--------------------|----------|--------------------|-------------------|
| base-architecture | string | amd64 | Charm architecture |
| destination-channel | string | "" | Destination channel |
| doc-automation-disabled | boolean | true | Whether the documentation automation is disabled |
| charm-working-directory | string | Null | The working directory for the charm. docs directory, if existing, should be under this directory |
| origin-channel | string | "" | Origin channel |
| working-directory | string | "./" | The working directory for the job |

The runner image will be set to the value of `bases[0].build-on[0]` in the `charmcraft.yaml` file, defaulting to ubuntu-22.04 if the file does not exist.

* auto_update_charm_libs: Checks if updates to the charm libraries are available and, of necessary,  opens a pull request to update them.

This workflow requires `pull_request` and `content` write permissions and a `CHARMHUB_TOKEN` secret containing a charmhub token. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).

bot_pr_approval: Automatically provides 1 approval for PRs generated by bots.
