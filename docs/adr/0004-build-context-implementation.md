# 4. Build context implementation

Date: 2026-03-11

## Status

Accepted

## Context

There are multiple ways to implement the build context functionality.

## Decision

We will move the charmcraft.yaml file as if it was placed in the context directory, making the necessary in-place edits for it to work.

## Consequences

The solution will be more aligned with our expectations from upstream. Not requiring us to change the charmcraft.yaml location in the charm repositories.
