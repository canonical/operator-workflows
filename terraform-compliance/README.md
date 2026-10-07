# Terraform module compliance checker

Generic checker that validates Terraform modules against a configurable spec.
The spec enforced by default is [CC008](../CC008.md).
Runs in CI via the reusable `terraform_modules_compliance.yaml` workflow.

Files:

- `terraform_spec.py` — the requirements, as data (`DEFAULT_SPEC` currently encodes CC008).
- `terraform_hcl.py` — `.tf` loading and `python-hcl2` normalisation.
- `terraform_check.py` — the checks and CLI (spec-agnostic; takes a spec argument).
- `terraform_discover.py` — finds Terraform module directories in a
  repository tree and classifies them by directory name (for `terraform-check-all`).
- `terraform_check_all.py` — the `terraform-check-all` CLI: discovers modules
  and runs `terraform_check` against all of them.

## Usage

Requires Python ≥ 3.11

### Install as a tool

Install the `terraform-check` CLI straight from this monorepo's subdirectory:

```bash
uv tool install "git+https://github.com/canonical/operator-workflows@main#subdirectory=terraform-compliance"
terraform-check /path/to/repo/terraform
```

Or run it once without installing anything:

```bash
uvx --from "git+https://github.com/canonical/operator-workflows@main#subdirectory=terraform-compliance" \
  terraform-check /path/to/repo/terraform
```

> Note: `uv run <url>/terraform_check.py` (running the bare script by raw file
> URL) is **not** supported — the checker is split across `terraform_check.py`,
> `terraform_hcl.py`, and `terraform_spec.py`, and a single-file URL run can't
> resolve those sibling imports. Use the `uvx --from git+url` form above
> instead.

### Install as a tool: check all modules in a repository

Once installed (see above), `terraform-check-all` discovers every Terraform
module in a repository and checks all of them in one go, instead of listing
each module directory by hand:

```bash
terraform-check-all /path/to/repo
```

It walks the given root, skipping `.git`, `.terraform`, `.venv`,
`node_modules`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, and `.tox`,
looking for `main.tf` files. Each discovered module directory is classified
by its own name (not the directory containing it):

- named exactly `terraform` → a charm module, checked.
- name contains `product` (case-insensitive) → a product module, checked.
- named exactly `tests` → ignored, along with everything beneath it.
- anything else → reported as `Unsupported module type: <path>` and counted
  as a failure; scanning continues and other modules are still checked.

This directory-name classification only decides what gets discovered and
checked; the compliance checks themselves still infer the module's actual
type (charm/component/product) from its HCL content, same as `terraform-check`.

### check

```bash
uv run --with python-hcl2==8.1.3 python \
  terraform-compliance/terraform_check.py /path/to/repo/terraform
```

### tests

```bash
PYTHONPATH=terraform-compliance uv run --with python-hcl2==8.1.3 \
  --with pytest pytest terraform-compliance/tests

```

Exit codes: `0` pass, `1` violations found, `2` no directories given. Flags:
`--verbose`, `--check <slug>`, `--list-checks`.

## What it checks

- Required files: `terraform.tf`, `variables.tf`, `outputs.tf`, `main.tf`,
  `README.md`.
- `terraform.tf` has `required_version` and a `juju/juju` provider allowing
  `>= 1.0.0`.
- Variable and output blocks are alphabetical.
- Mandatory variables/outputs per module type (charm, component, product),
  plus a broad type-family check and CC008 defaults where unambiguous. Optional
  variables/outputs are validated only when present. CC008 allows arbitrary
  extra variables and outputs, but names retired under CC008 (e.g. `endpoints`,
  split into `provides`/`requires`) are flagged as deprecated.
- Required non-null variables explicitly declare `nullable = false`.
- Charm `application` outputs reference the complete `juju_application`
  resource. Literal `provides`/`requires` maps contain endpoint objects with
  `kind`, `name`, and `endpoint` fields; computed output and entry expressions
  are left to Terraform.
- Remote module sources are pinned (a `?ref=` that isn't a floating branch, or
  a registry `version`).

Module type is inferred: no `module` blocks → charm; composes modules and
defines a `juju_model`/`juju_secret`/`juju_integration`/`juju_offer` →
product; composes only → component.

## Known deviations

- `providers.tf` is not required (CC008 modules are non-root, so have no
  provider config to place there).
- General output types aren't checked (Terraform infers them from the value).
- `provides`/`requires` outputs are optional: CC008 makes them mandatory only
  when the charm defines that relation, which Terraform can't detect.
- `units` is optional: CC008 requires it except on subordinate charms (which
  must omit it), and subordinate-ness isn't visible from Terraform.
