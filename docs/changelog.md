# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each revision is versioned by the date of the revision.

## 2026-02-17

- Add step to "docs" workflow to install docutils, so that the workflow can
  check reStructuredText files.

## 2026-02-11

- Add "terraform-lint" step in the "test" workflow.

## 2026-02-10

- Add `bootstrap-options` parameter to the `integration_test.yaml` workflow
to control how the controller is bootstrapped.

## 2026-02-01

- Update `docs_spread` workflow to support reStructuredText and more flexible
  handling of skippable commands.
- Update `workflow_test.yaml` to include a test for reStructuredText files.

## 2026-01-28

- Update `docs_rtd` workflow to use `canonical/documentation-workflows/.github/workflows/documentation-checks.yaml@main`.

## 2026-01-21

- Add `docs_spread` workflow to auto-generate testing materials and run Spread.

## 2026-01-20

- Use author instead of actor to verify bot pull requests.

## 2026-01-16

- Fix bug with license validation.

## 2026-01-12

- Fix bug with input parameter name for `check-libs` workflow.

## 2025-12-19

- Fix a problem in the integration test caused by a missing `apt install`.

## 2025-12-09

- Update the default juju bootstrap bootstrap-constraints to "cores=2 mem=4G root-disk=10G".
- Fix the integration test job in documentation pull requests

## 2025-12-08

- Add a new `auto-merge` parameter for the `generate_terraform_docs` workflow.

## 2025-12-04

- Fix the build job lookup algorithm in the integration test workflow.

## 2025-12-02

- Add 5 more integration test secrets mapping slots.
- Update the integration test workflow to run the build process concurrently with the setup phase of the integration tests.

## 2025-11-19

- Update `docs_rtd` workflow to point to a new branch where the starter pack workflows are callable.

## 2025-11-17

- Add allure report passing condition for subsequent run attempts following failure.

## 2025-11-13

- Add uv.lock to the .licenserc.yaml ignore list

## 2025-11-07

- Remove the expectation of specific linters to be run on the test workflow.

## 2025-10-28

- Fix breaking integration tests for VM charms when INTEGRATION_TEST_SECRET_ENV_NAME variables are not set.

## 2025-10-28

- Add `docs_rtd` workflow to consolidate all the starter pack workflows for RTD projects.

## 2025-10-21

- Add a job to create the `gh-pages` branch if it does not exist for the Allure workflow.

## 2025-10-09

- Add `*.rst` files to `IGNORED_PATTERNS` for integration testing.

## 2025-10-08

- Add `testing` model in the canonical-k8s setup.

## 2025-10-01

- Allow alternative rockcraft.yaml names. Rocks will be build and published for every rock in a file with a `rockcraft.yaml` suffix (e.g. `webhook-gateway_rockcraft.yaml`). This is to allow multiple rockcrafts in the same directory (currently not supported by rockcraft).

## 2025-09-24

- If the build step failed in the integration tests, fail the required_status_check.
- Temporarily disable link checks for terraform due to aggressive throttling.

## 2025-09-19

- Remove draft-publish-docs.

## 2025-09-18

- Removing the dedicated inclusive check job within the tests workflow.

## 2025-09-08

- Fix the checkout step in `generate_terraform_docs.yaml`

## 2025-09-08

- The `generate_terraform_docs` workflow now creates a pull request when used outside of a pull request.

## 2025-09-04

- Allow cross-track charm promotions. Validation of the track name is removed when promote a charm.

## 2025-09-02

### Changed

- Default self-hosted runners are updated to "noble" from "jammy".

### Fixed

- Add break-system-packages parameter only if runner is self-hosted and image is "noble".

## 2025-08-21

### Added

- Add generate terraform docs workflow.

## 2025-08-20

### Fixed

- Skip the vale action entirely if `vale_style_check` is disabled to temporarily mitigate `fail_on_error` issue. See <https://github.com/errata-ai/vale-action/issues/89>.

## 2025-08-19

### Fixed

- Fix the vale workflow to point to the latest version and enable `nofilter`.

### Changed

- Auto-approve PRs opened by dependabot[bot].

## 2025-08-11

### Fixed

- Make trivy exit-code configuration an input in the integration_test.yaml workflow

## 2025-07-29

### Fixed

- Move setup devstack-swift before setup operator environment to avoid a Kubernetes network issue.

## 2025-07-29

### Changed

- Refactor integration_test.yaml to make it reusable in any GitHub event, not just Pull Requests.

## 2025-07-16

### Changed

- Publish the artifacts from the last integration test workflow regardless of whether the execution is sucessful.

## 2025-07-14

### Added

- Add option to disable check-lib test.

## 2025-07-08

### Added

- Support for `DOCKERHUB_MIRROR` in Canonicak Kubernetes configuration.

## 2025-06-19

### Changed

- Revert "Define required secrets in the promote workflow".

## 2025-06-18

### Changed

Revert Make publish libs independent from charm publishing

## 2025-06-12

### Changed

- Define required secrets in the promote workflow.

### Fixed

- Bug getting the directory when publishing the charm libraries.

## 2025-06-12

### Changed

- Skip building and scanning artifacts if there are only documentation changes.
- Skip integration tests if there are only documentation changes.
- Make image scanning a required check.

## 2025-06-10

### Changed

- The logic to get the plan is extracted to a new action.

## 2025-06-09

### Changed

- gatekeeper is now called with a "base_branch" argument set to the default branch of the repository. This is to support documentation actions on repositories not using "main" as their main branch.

## 2025-06-09

### Added

- Added support for installing `tox` with `uv` in the integration tests workflows.

## 2025-06-09

## Removed

- Support from building charmcraft from source.

## 2025-05-30

### Added

- Add support to make the vale style check mandatory via the `vale-style-check` input to the `test` workflow.

## 2025-05-27

### Fixed

- Update `promote_charm` workflow to obtain charm name from `charmcraft expand-extensions` instead
  of `charmcraft.yaml`.

## 2025-05-22

### Fixed

- Fix the step "Run k8s integration test" in the integration test workflow to not always run.

## 2025-05-21

### Removed

- Ejected draft publish docs step from from promote charm workflow.

### Changed

- Allow the "Draft Publish Docs" job to fail, but still consider the "Tests" workflow successful.

## 2025-04-29

### Modified

- Update `promote_charm` workflow logic to use `charmcraft status` to obtain base information instead of `charmcraft.yaml`.

## 2025-03-21

### Added

- Changelog added for tracking changes.
- Added unique artifact name for zap-scan artifacts

# 2025-05-15

### Added

- Added support for canonical-k8s via the `use-canonical-k8s: true` and `provider: k8s` parameter
