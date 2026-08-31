# CC008 Terraform compliance checker

`cc008_check.py` verifies that Terraform modules follow the CC008 Terraform
module standards. HCL is parsed with `python-hcl2`.

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
The reusable workflow runs each category as its own step against every
configured module directory in one job, so a failure in one check category is
immediately visible in the Actions UI without hiding the results of the
others, and without paying the cost of a separate runner per module (checkout,
Python setup, and dependency install) for what is otherwise a sub-second
parse-and-check per module.

## Checks performed

- Required files: `terraform.tf`, `variables.tf`, `outputs.tf`, `main.tf`, and
  `README.md`.
- `terraform.tf` declares `required_version` and a `juju` provider whose
  version constraint's lower bound allows `>= 1.0.0` (e.g. `>= 1.0`, `> 1.0.0`,
  `~> 1.12`, or a bare `1.0.0` pin). A constraint with no lower bound at all,
  such as `< 3.0`, is rejected.
- Variable and output blocks are alphabetical.
- Charm modules declare the mandatory variables and outputs.
- Product modules declare the mandatory variables (`juju_controller`, `proxy`,
  `logging-config`, `risk`) and outputs (`models`, `metadata`).
- Remote module sources declare a `?ref=...` (or a registry `version`). A ref
  can be named anything — Terraform/git impose no required shape on tags, so
  this checker does not try to validate ref naming. It only rejects the small
  set of conventional default/floating branch names CC008 explicitly calls
  out (`main`, `master`, `trunk`, `develop`, `development`, `head`, matched
  case-insensitively). Any other ref value, including a bare semver tag from a
  dependency that does not follow CC008's own `tf-X.Y.Z`/`vX.Y.Z` convention,
  is treated as pinned.

A module is treated as a product module when any of its files declares a
`module` block; otherwise it is treated as a charm module. Component modules
(bundles of charm modules sharing one release cycle, with a `components`
mandatory output) are not currently distinguished from product modules by this
checker — a Component module will be checked against the product module rules
instead.

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
