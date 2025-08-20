# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each revision is versioned by the date of the revision.

## 2025-08-20

### Fixed

- Skip the vale action entirely if `vale_style_check` is disabled.

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
