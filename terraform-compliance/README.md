# CC008 Terraform compliance checker

Checks that Terraform modules follow the CC008 module standards. Runs in CI via
the reusable `terraform_modules_compliance.yaml` workflow.

Files:

- `cc008_spec.py` — the CC008 requirements, as data.
- `terraform_hcl.py` — `.tf` loading and `python-hcl2` normalisation.
- `cc008_check.py` — the checks and CLI.

## Usage

Requires Python ≥ 3.11 (CI pins 3.12; `-p 3.12` stops `uv` picking an older
cached interpreter).

```bash
# check
uv run -p 3.12 --with python-hcl2==8.1.3 python \
  terraform-compliance/cc008_check.py /path/to/repo/terraform

# tests
PYTHONPATH=terraform-compliance uv run -p 3.12 --with python-hcl2==8.1.3 \
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
  variables/outputs are validated only when present.
- Remote module sources are pinned (a `?ref=` that isn't a floating branch, or
  a registry `version`).

Module type is inferred: no `module` blocks → charm; composes modules and
defines a `juju_model`/`juju_secret`/`juju_integration`/`juju_offer` →
product; composes only → component.

## Known deviations

- `providers.tf` is not required (CC008 modules are non-root, so have no
  provider config to place there).
- Output types aren't checked (Terraform infers them from the value).
- `provides`/`requires` outputs are optional: CC008 makes them mandatory only
  when the charm defines that relation, which Terraform can't detect.
- `units` is optional: CC008 requires it except on subordinate charms (which
  must omit it), and subordinate-ness isn't visible from Terraform.
