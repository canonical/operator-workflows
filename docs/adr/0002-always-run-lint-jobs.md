# 2. Always run lint jobs

Date: 2026-02-09

## Status

Accepted

## Context

During the implementation of the `Terraform lint` job, the question has been raised to know if we should save some time and resources by skipping linting jobs when no corresponding file have changed (e.g. skip `Dockerfile lint` if the `Dockerfile` file has not changed).

## Decision

We dediced to keep running all the lint job on all PRs.

The main motivation are the following:

- The CI is the last barrier to ensure that our repositories meet our standards.
- These jobs are fast to execute and not resource intensive.
- If we want to save time and resources, we can explore solutions "before" the CI, like `pre-commit` hooks.

## Consequences

All linting jobs are run on all PRs.
