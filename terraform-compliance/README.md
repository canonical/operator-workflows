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

Pass `--verbose` locally, or set the reusable workflow's `verbose` input to
`true`, to include discovered variables, outputs, and module sources. In GitHub
Actions, violations are also emitted as error annotations.

## Checks performed

- Required files: `terraform.tf`, `variables.tf`, `outputs.tf`, `main.tf`, and
  `README.md`.
- `terraform.tf` declares `required_version` and a `juju` provider allowing
  `>= 1.0`.
- Variable and output blocks are alphabetical.
- Charm modules declare mandatory variables and outputs.
- Product modules declare `models` and `metadata` outputs.
- Remote module sources are pinned to a tag or commit.

A module is treated as a product module when any of its files declares a
`module` block; otherwise it is treated as a charm module.
