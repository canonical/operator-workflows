# CC008 Terraform compliance checker

`cc008_check.py` verifies that Terraform modules follow the CC008 Terraform
module standards. HCL is parsed with `python-hcl2`.

`cc008_spec.py` is the single source of truth for *what* CC008 requires
(required files, mandatory variables/outputs per module type and their
type/required/default constraints, the Product-module tying-resource types,
the floating-ref denylist) as plain dataclasses with no checking logic. To see
the full CC008 contract this checker enforces, read `cc008_spec.py` alone —
`cc008_check.py` only contains the *how* (HCL parsing, constraint math,
alphabetical comparison, etc.) that evaluates it.

The reusable workflow installs the pinned dependencies from `requirements.txt`
and runs the checker against module directories in the caller repository.

## Run locally

From the `operator-workflows` repository:

```bash
uv run --with python-hcl2==8.1.3 python \
  terraform-compliance/cc008_check.py \
  /path/to/repository/terraform
```

Exit code `0` means every module passed; `1` means at least one module reported
a violation. Exit code `2` means no module directories were provided. Missing
paths and directories without the required Terraform module files fail the
check rather than passing silently.

## Run the unit tests

```bash
PYTHONPATH=terraform-compliance \
  uv run --with python-hcl2==8.1.3 --with pytest \
  pytest terraform-compliance/tests
```

Pass `--verbose` locally to include discovered variables, outputs, and module
sources. The reusable workflow always runs with `--verbose`. In GitHub Actions,
violations are also emitted as error annotations.

Pass `--check <slug>` to run only one check category (see `--list-checks` for
the available slugs: `required-files`, `terraform-configuration`,
`variable-ordering`, `output-ordering`, `module-interface`, `module-sources`).
This is mainly useful for local debugging of a single category; the reusable
workflow runs all categories in one invocation, since `cc008_check.py` already
reports a PASS/FAIL breakdown per category plus a summary in a single pass.

## Checks performed

- Required files: `terraform.tf`, `variables.tf`, `outputs.tf`, `main.tf`, and
  `README.md`.
- `terraform.tf` declares `required_version` and a `juju` provider whose
  version constraint's lower bound allows `>= 1.0.0` (e.g. `>= 1.0`, `> 1.0.0`,
  `~> 1.12`, or a bare `1.0.0` pin). A constraint with no lower bound at all,
  such as `< 3.0`, is rejected.
- Variable and output blocks are alphabetical.
- Charm, Component, and Product modules each declare their mandatory
  variables and outputs (see "Module classification" below for how a module's
  type is determined):
  - Charm: `app_name`, `channel`, `config`, `constraints`, `model_uuid`,
    `revision`, `units` variables; `application`, `provides`, `requires`
    outputs.
  - Component: `model_uuid` variable; `components` output.
  - Product: `logging-config`, `proxy`, `risk` variables; `metadata`, `models`
    outputs.
- Mandatory variables are also checked against a broad type family (`string`,
  `number`, `bool`, or `collection` for `map`/`list`/`set`/`object`/`tuple`)
  and, where CC008 is unambiguous, `required`/`default` rules:
  - `model_uuid` must not declare a `default` (it is always required).
  - `units`' default, if declared, must be `1`; `config`'s default, if
    declared, must be `{}`.
  - The type check is deliberately a broad family match, not an exact type
    comparison — CC008 doesn't mandate one specific collection/object shape
    for most of these variables, and exact-shape checks have already caused
    false positives elsewhere in this checker (see the ref-pinning note
    below), so this only flags obvious mismatches (e.g. a number-typed
    variable declared as `string`).
  - Terraform `output` blocks have no `type` field — the type is inferred
    from the `value` expression — so outputs are not type-checked, only
    checked for presence.
- Remote module sources declare a `?ref=...` (or a registry `version`). A ref
  can be named anything — Terraform/git impose no required shape on tags, so
  this checker does not try to validate ref naming. It only rejects the small
  set of conventional default/floating branch names CC008 explicitly calls
  out (`main`, `master`, `trunk`, `develop`, `development`, `head`, matched
  case-insensitively). Any other ref value, including a bare semver tag from a
  dependency that does not follow CC008's own `tf-X.Y.Z`/`vX.Y.Z` convention,
  is treated as pinned.

### Module classification

A module with no `module` blocks is a Charm module. A module that composes
other modules (has at least one `module` block) is a Product module if it also
declares a `juju_model`, `juju_secret`, `juju_integration`, or `juju_offer`
resource/data block (i.e. it ties components together, per CC008's definition
of Product modules); otherwise it is a Component module (it only bundles other
modules without tying them together).

## Known deviations from the CC008 spec

- CC008 lists `providers.tf` as part of the standard module file structure,
  alongside `terraform.tf`. The two serve different purposes: `terraform.tf`
  declares dependencies only (`required_version`, `required_providers` — which
  provider and version range this module needs), while `providers.tf` would
  hold actual `provider "juju" { ... }` *configuration* (controller address,
  credentials). Terraform's own convention reserves `provider` configuration
  blocks for root modules; a reusable Charm/Component/Product module (as
  defined by CC008) is always instantiated by something else — a deployment, a
  test harness, a higher-level product module — and that caller is the one
  that provides the `provider "juju" {}` configuration. A CC008 module
  therefore has nothing to put in `providers.tf`; declaring the dependency in
  `terraform.tf` is the complete requirement. This checker does not require
  `providers.tf` for that reason.
- CC008 states `provides`/`requires` outputs are mandatory only *if the charm
  defines that relation*. Terraform alone cannot determine whether a charm
  declares `provides`/`requires` relations, so this checker treats both as
  always mandatory for charm modules. This is intentionally stricter than the
  spec.
