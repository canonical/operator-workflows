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
- Remote module sources are pinned to a tag or commit. A pinned ref may be a
  commit SHA or any tag ending in a semver suffix (`tf-X.Y.Z`, `vX.Y.Z`,
  `<product>-X.Y.Z`, or a bare `X.Y.Z`). Bare semver tags are accepted because
  a dependency may live in a repository that does not yet follow CC008's own
  tag-naming convention; enforcing that repository's tag naming is outside
  this checker's scope — only that the ref is pinned (not a floating branch)
  matters here.

A module is treated as a product module when any of its files declares a
`module` block; otherwise it is treated as a charm module. Component modules
(bundles of charm modules sharing one release cycle, with a `components`
mandatory output) are not currently distinguished from product modules by this
checker — a Component module will be checked against the product module rules
instead.

## Known deviations from the CC008 spec

- CC008 lists `providers.tf` as part of the standard module file structure.
  This checker does not require it: none of the reference CC008-compliant
  modules evaluated (including this repository's own product/charm modules)
  use a separate `providers.tf` — provider configuration lives in the
  `required_providers` block of `terraform.tf` instead. Enforcing
  `providers.tf` today would fail every currently-compliant module.
- CC008 states `provides`/`requires` outputs are mandatory only *if the charm
  defines that relation*. Terraform alone cannot determine whether a charm
  declares `provides`/`requires` relations, so this checker treats both as
  always mandatory for charm modules. This is intentionally stricter than the
  spec.
