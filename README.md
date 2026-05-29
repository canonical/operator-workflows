# operator-workflows

This repository includes several parametrized CI workflows to be used for both kubernetes and machine charms.

To use the workflows in your repository, just reuse them including the `secrets: inherit` key. Examples of usage for every workflow can be found at the [indico operator](https://github.com/canonical/indico-operator/blob/main/.github/workflows). Note that you will need a CHARMHUB_TOKEN among your repository secrets to be able to run the workflows that interact with charmhub.

## Workflows

### Test Workflow (`canonical/operator-workflows/.github/workflows/test.yaml@main`)

This workflow executes the default tox targets defined in the `tox.ini` file and generates a plain text report. This requires the `lint`, `unit`, `static` and `coverage-report` `tox` environments to be included in the tox defaults. See [the workflow file](.github/workflows/test.yaml) for workflow inputs.

### Comment Workflow (`canonical/operator-workflows/.github/workflows/comment.yaml@main`)

Posts the content of the artifact specified as a comment in a PR. It needs to be triggered from a PR triggered workflow.

### Integration Test Workflow (`canonical/operator-workflows/.github/workflows/integration_test.yaml@main`)

Builds the existing docker or rock images, if any, and executes the `integration` test target defined in the `tox.ini` file. The tox environment used can be changed with the `test-tox-env` input. See [the workflow file](.github/workflows/integration_test.yaml) for workflow inputs.

More information about OWASP ZAP testing can be found [here](OWASPZAP.md).

More information about Trivy testing can be found [here](TRIVY.MD).

In order to export sensitive data as environment variables into the integration test run,
a mapping of variables to secrets can be defined by setting the [GitHub Action Variable](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables)
`INTEGRATION_TEST_SECRET_ENV_NAME` with the name of the environment variable you want to export and `INTEGRATION_TEST_SECRET_ENV_VALUE` with the value you want the environment variable to have.
 There are six slots available. In addition to the one mentioned above, you can use
`INTEGRATION_TEST_SECRET_ENV_NAME_{1,...5}` and `INTEGRATION_TEST_SECRET_ENV_VALUE_{1,...5}`.

When running the integration tests, the following posargs will be automatically passed to the `integration` target:

* --charm-file [charm_file_name]: The name of the charm artifact generated prior to the integration tests run, this argument can be supplied multiple times for charm with multiple bases.
* --{image-name}-image: The name of the image artifact built prior to the integration tests run, this argument may be supplied multiple times or not at all depending on the plan
* --{resource-name}-resource: The name of the charm file resources built prior to the integration tests run, this argument may be supplied multiple times or not at all depending on the plan
* --series [series]: As defined in the `series` configuration described option above
* -k [module]: As defined in the `modules` configuration option described above
* --keep-models
* --model testing: Only for tests running on a microk8s substrate
* One parameter per resource defined in the `metadata.yaml` of the charm, containing a reference to the built image

For instance, for pytest you can leverage this by adding a conftest.py file

```python
def pytest_addoption(parser):
    """Add test arguments."""
    parser.addoption("--charm-file", action="append")
```

and then use the argument value

```python
charm = pytestconfig.getoption("--charm-file")[0] # the charm only has one base
```

tmate can be run on failed tests either by setting the `tmate-debug` input to 'true' or by re-running a job with the "Enable debug logging" checkbox checked.

By providing a file path to `pre-build-script` variable, a script can be run before the build step. This is especially valuable if a set of operations need to be done before packing the rock or charm.

### Publish Charm Workflow (`canonical/operator-workflows/.github/workflows/publish_charm.yaml@main`)

Publishes the charm and its resources to appropriate channel, as defined [here](https://github.com/canonical/charming-actions/tree/main/channel).

This workflow requires a `CHARMHUB_TOKEN` secret containing a charmhub token with package-manage and package-view permissions for the charm and the destination channel. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).

By default, the publish workflow will search for an [integration test workflow](#integration-test-workflow-canonicaloperator-workflowsgithubworkflowsintegration_testyamlmain) that was succeeded with the exact matching git tree ID. It will then use the artifacts built in that workflow run (charms and images) as the assets for upload. This default behavior can be overridden by providing the `workflow-run-id` input to the publish workflow. When this input is supplied, the publish workflow will specifically retrieve artifacts from the given workflow run.

See [the workflow file](.github/workflows/publish_charm.yaml) for workflow inputs.

### Promote Charm Workflow (`canonical/operator-workflows/.github/workflows/promote_charm.yaml@main`)

Promotes a charm from the selected origin channel to the selected target channel.

This workflow requires a `CHARMHUB_TOKEN` secret containing a charmhub token with package-manage and package-view permissions for the charm and the origin and destination channels. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).

See [the workflow file](.github/workflows/promote_charm.yaml) for workflow inputs.

### Update Charm Libs Workflow (`canonical/operator-workflows/.github/workflows/auto_update_charm_libs.yaml@main`)

Checks if updates to the charm libraries are available and, of necessary,  opens a pull request to update them.

This workflow requires `pull_request` and `content` write permissions and a `CHARMHUB_TOKEN` secret containing a charmhub token. See how to generate it [here](https://juju.is/docs/sdk/remote-env-auth).

### Bot PR Approval Workflow (`canonical/operator-workflows/.github/workflows/bot_pr_approval.yaml@main`)

Automatically provides 1 approval for PRs generated by bots.

### RTD-specific Workflow (`canonical/operator-workflows/.github/workflows/docs_rtd.yaml@main`)

Consolidated set of workflows from
[canonical/sphinx-docs-starter-pack](https://github.com/canonical/sphinx-docs-starter-pack)
with documentation checks specifically for Read the Docs projects.

### Automated Documentation Testing Workflow (`canonical/operator-workflows/.github/workflows/docs_spread.yaml@main`)

Runs `canonical/operator-workflows/spread/create_spread_task_file.py` over a documentation file
to generate the `task.yaml` needed for a Spread test, and then runs Spread over the resulting file.
This workflow supports Markdown and reStructuredText files.

This workflow requires a `spread.yaml` file to already exist in the root of your repository, along with
three input variables:

* `input-file`: The full path to the documentation file you want to test.
* `output-dir`: The directory where the `task.yaml` file will be created.
* `spread-job`: The name of the Spread job to run (e.g., `github-ci:ubuntu-24.04-64:tests/spread`).
  Note that `spread-job` must match the information provided in the `suites` section of your `spread.yaml` file.

### Terraform modules tests (`canonical/operator-workflows/.github/workflows/terraform_modules_test.yaml@main)

Runs `terraform test` in the `tests` subfolder of the specified directories.

You can find an example on how to call it in the [`platform-engineering-charm-template`](https://github.com/canonical/platform-engineering-charm-template/blob/main/.github/workflows/test_terraform_module.yaml).

## Required GitHub Token Permissions

GitHub organisations can set the default `GITHUB_TOKEN` permissions to read-only. When your organisation uses read-only defaults, calling jobs must explicitly grant any permissions beyond `contents: read`. The table below lists the **minimum required permissions** for each reusable workflow so you can be explicit in your own calling workflows.

| Workflow | Required permissions | Reason |
|---|---|---|
| `allure_report.yaml` | `contents: write` | Pushes the Allure report to the `gh-pages` branch |
| `auto_update_charm_libs.yaml` | `contents: write`<br>`pull-requests: write`<br>`id-token: write` | Creates PRs to update charm libraries; uses OIDC for Charmhub authentication |
| `bot_pr_approval.yaml` | `pull-requests: write` | Approves bot-authored PRs via the GitHub API |
| `comment_contributing.yaml` | `pull-requests: write` | Posts a contributing-guide comment on newly opened PRs |
| `comment.yaml` | `pull-requests: write`<br>`actions: read` | Creates and deletes PR comments; downloads artifacts from a specific workflow run by ID |
| `docs_rtd.yaml` | `contents: read` | Checks out the repository for Read the Docs build checks |
| `docs_spread.yaml` | `contents: read` | Checks out the repository for Spread-based documentation testing |
| `docs.yaml` | `contents: read` | Checks out the repository for Vale and Lychee linting |
| `generate_terraform_docs.yaml` | `contents: write`<br>`pull-requests: write` | Commits generated Terraform docs and opens a PR with the changes |
| `integration_test.yaml` | `contents: read`<br>`packages: write`<br>`pull-requests: write` *(optional)* | Checks out the repository; pushes built OCI images to `ghcr.io` when `upload-image: registry` is used or when running on non-forked PRs; `pull-requests: write` is only needed to post `.trivyignore` warning comments (non-fatal if absent) |
| `promote_charm.yaml` | `contents: write` | Creates a git tag via `charming-actions/release-charm` |
| `publish_charm.yaml` | `contents: write`<br>`packages: write`<br>`actions: read` | Creates git tags and releases libraries; pushes OCI images to `ghcr.io`; downloads build artifacts from a prior integration test run |
| `terraform_modules_test.yaml` | `contents: read` | Checks out the repository to run `terraform test` |
| `test.yaml` | `contents: read`<br>`pull-requests: write` | Checks out the repository; `charming-actions/check-libraries` posts a comment on PRs when charm libraries are out of date |

### Example calling workflow

```yaml
jobs:
  integration-tests:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    permissions:
      contents: read
      packages: write
    secrets: inherit
```

> **Note:** `packages: write` is only needed by `integration_test.yaml` and `publish_charm.yaml` when OCI images are pushed to `ghcr.io`. If your charm has no OCI images, `contents: read` is sufficient for `integration_test.yaml`.
