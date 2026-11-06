# Terraform module compliance checker

Generic checker that validates Terraform modules against a configurable spec.
The spec enforced by default is [CC008](../CC008.md).
Runs in CI via the reusable `terraform_modules_compliance.yaml` workflow.

Files:

- `terraform_spec.py` — the requirements, as data (`DEFAULT_SPEC` currently encodes CC008).
- `terraform_hcl.py` — `.tf` loading and `python-hcl2` normalisation.
- `terraform_check.py` — the checks and CLI (spec-agnostic; takes a spec argument).
  By default it discovers Terraform module directories under each given path
  (by locating the spec's marker files, `main.tf` or `terraform.tf`).
  The `terraform-check-all` command is an alias of `terraform-check`.

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

Once installed (see above), `terraform-check` (also available as
`terraform-check-all`, kept for compatibility) discovers every Terraform
module under the given repository root and checks all of them in one go:

```bash
terraform-check /path/to/repo
```

It walks the given root, skipping `.git`, `.terraform`, `.venv`,
`node_modules`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, and `.tox`,
looking for `main.tf` or `terraform.tf` files (legacy modules may lack
`terraform.tf`; a directory named exactly `tests` is ignored, along with
everything beneath it). Directories containing `.tf` files but neither marker
are reported as warnings and not checked. Every discovered module is then
checked, and its type (charm/component/product) is inferred from its path and
`outputs.tf`. Pass `--no-discover` to treat each path as a module directory
instead (used by the reusable workflow).

### check

```bash
uv run --with python-hcl2==8.1.3 python \
  terraform-compliance/terraform_check.py /path/to/repo
```

### tests

```bash
PYTHONPATH=terraform-compliance uv run --with python-hcl2==8.1.3 \
  --with pytest pytest terraform-compliance/tests

```

Exit codes: `0` pass, `1` violations found (or no modules discovered), `2` no or invalid paths given. Flags:
`--verbose`, `--check <slug>`, `--list-checks`, `--no-discover`, `--root`.

## What it checks

- Required files: `terraform.tf`, `variables.tf`, `outputs.tf`, `README.md`.
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

Module type is inferred, never guessed from the HCL body. A path element
(relative to the `--root` given to `terraform-check`, or the path as given)
containing `product` or `component`, or the whole word `charm`/`charms` (so
`charmed-spark` is not a charm), names the type; a path naming several types is
ambiguous. Otherwise `outputs.tf` decides: `juju_model` means product,
`components` means component, `juju_application` means charm. If no rule matches,
the "Module type" check fails (`module-type`) and the module-interface check is
skipped.

## Known deviations

- `providers.tf` is not required (CC008 modules are non-root, so have no
  provider config to place there).
- General output types aren't checked (Terraform infers them from the value).
- `provides`/`requires` outputs are optional: CC008 makes them mandatory only
  when the charm defines that relation, which Terraform can't detect.
- `units` is optional: CC008 requires it except on subordinate charms (which
  must omit it), and subordinate-ness isn't visible from Terraform.
