# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the CC008 Terraform compliance checker."""

from pathlib import Path

import cc008_check
import hcl2

COMPLIANT_TERRAFORM_TF = """\
terraform {
  required_version = "~> 1.12"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 1.0, < 3.0"
    }
  }
}
"""

COMPLIANT_VARIABLES_TF = """\
variable "app_name" {
  type    = string
  default = "demo"
}

variable "base" {
  type    = string
  default = null
}

variable "channel" {
  type    = string
  default = "1/stable"
}

variable "config" {
  type    = map(string)
  default = {}
}

variable "constraints" {
  type    = string
  default = null
}

variable "model_uuid" {
  type = string
}

variable "revision" {
  type    = number
  default = null
}

variable "units" {
  type    = number
  default = 1
}
"""

COMPLIANT_OUTPUTS_TF = """\
output "application" {
  value = juju_application.demo
}

output "provides" {
  value = {}
}

output "requires" {
  value = {}
}
"""

COMPLIANT_MAIN_TF = """\
resource "juju_application" "demo" {
  name       = var.app_name
  model_uuid = var.model_uuid
}
"""


def _write_charm_module(root: Path) -> Path:
    module = root / "charm"
    module.mkdir()
    (module / "terraform.tf").write_text(COMPLIANT_TERRAFORM_TF)
    (module / "variables.tf").write_text(COMPLIANT_VARIABLES_TF)
    (module / "outputs.tf").write_text(COMPLIANT_OUTPUTS_TF)
    (module / "main.tf").write_text(COMPLIANT_MAIN_TF)
    (module / "README.md").write_text("# demo\n")
    return module


def test_missing_required_files_are_reported(tmp_path: Path) -> None:
    module = tmp_path / "empty"
    module.mkdir()

    violations = cc008_check.check_required_files(module)

    assert "missing required file: terraform.tf" in violations
    assert "missing required file: variables.tf" in violations
    assert "missing required file: outputs.tf" in violations
    assert "missing required file: main.tf" in violations
    assert "missing required file: README.md" in violations


def test_compliant_terraform_block_has_no_violations() -> None:
    assert cc008_check.check_terraform_block(hcl2.loads(COMPLIANT_TERRAFORM_TF)) == []


def test_terraform_block_missing_required_version() -> None:
    text = """\
terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 1.0"
    }
  }
}
"""
    violations = cc008_check.check_terraform_block(hcl2.loads(text))
    assert "terraform.tf: missing required_version" in violations


def test_terraform_block_missing_juju_provider() -> None:
    text = """\
terraform {
  required_version = "~> 1.12"
}
"""
    violations = cc008_check.check_terraform_block(hcl2.loads(text))
    assert "terraform.tf: missing juju provider in required_providers" in violations


def test_terraform_block_juju_version_too_low() -> None:
    text = """\
terraform {
  required_version = "~> 1.12"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "~> 0.9"
    }
  }
}
"""
    violations = cc008_check.check_terraform_block(hcl2.loads(text))
    assert "terraform.tf: juju provider version must allow >= 1.0" in violations


def test_block_names_preserves_source_order() -> None:
    text = """\
variable "zeta" {
  type = string
}
variable "alpha" {
  type = string
}
"""
    assert cc008_check.block_names(hcl2.loads(text), "variable") == ["zeta", "alpha"]


def test_alphabetical_variables_pass() -> None:
    text = """\
variable "alpha" {
  type = string
}
variable "beta" {
  type = string
}
"""
    assert cc008_check.check_alphabetical(hcl2.loads(text), "variable", "variables.tf") == []


def test_unordered_variables_are_reported() -> None:
    text = """\
variable "beta" {
  type = string
}
variable "alpha" {
  type = string
}
"""
    violations = cc008_check.check_alphabetical(hcl2.loads(text), "variable", "variables.tf")
    assert len(violations) == 1
    assert "variables.tf: variable blocks are not alphabetical" in violations[0]


def test_is_product_module_detects_module_blocks() -> None:
    charm = hcl2.loads('resource "juju_application" "demo" {\n  name = var.app_name\n}\n')
    product = hcl2.loads('module "demo" {\n  source = "../modules/demo"\n}\n')
    assert cc008_check.is_product_module([charm]) is False
    assert cc008_check.is_product_module([product]) is True


def test_charm_interface_requires_mandatory_variables_and_outputs() -> None:
    violations = cc008_check.check_interface(variables=[], outputs=[], product=False)
    for variable in ("app_name", "channel", "config", "constraints", "model_uuid", "revision", "units"):
        assert f"charm module missing mandatory variable: {variable}" in violations
    for output in ("application", "provides", "requires"):
        assert f"charm module missing mandatory output: {output}" in violations


def test_compliant_charm_interface_passes() -> None:
    variables = ["app_name", "channel", "config", "constraints", "model_uuid", "revision", "units"]
    outputs = ["application", "provides", "requires"]
    assert cc008_check.check_interface(variables, outputs, product=False) == []


def test_product_interface_requires_models_and_metadata() -> None:
    violations = cc008_check.check_interface(variables=[], outputs=[], product=True)
    assert "product module missing mandatory output: models" in violations
    assert "product module missing mandatory output: metadata" in violations


def test_compliant_product_interface_passes() -> None:
    assert cc008_check.check_interface([], ["models", "metadata"], product=True) == []


def test_local_module_source_is_allowed() -> None:
    parsed = hcl2.loads('module "demo" {\n  source = "../modules/demo"\n}\n')
    assert cc008_check.check_pinned_module_sources([parsed]) == []


def test_tag_pinned_remote_source_is_allowed() -> None:
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform?ref=tf-2.0.0&depth=1"\n'
        "}\n"
    )
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_commit_pinned_remote_source_is_allowed() -> None:
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform?ref=1a2b3c4d"\n'
        "}\n"
    )
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_unpinned_remote_source_is_reported() -> None:
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform"\n'
        "}\n"
    )
    violations = cc008_check.check_pinned_module_sources([hcl2.loads(text)])
    assert len(violations) == 1
    assert 'module "ic": source must be pinned' in violations[0]


def test_branch_ref_is_reported() -> None:
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform?ref=main"\n'
        "}\n"
    )
    violations = cc008_check.check_pinned_module_sources([hcl2.loads(text)])
    assert len(violations) == 1
    assert "floating references are not allowed" in violations[0]


def test_registry_version_source_is_allowed() -> None:
    text = 'module "ic" {\n  source  = "canonical/x/juju"\n  version = "1.2.0"\n}\n'
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_compliant_charm_module_has_no_violations(tmp_path: Path) -> None:
    module = _write_charm_module(tmp_path)
    assert cc008_check.check_module(module) == []


def test_check_module_reports_missing_mandatory_variable(tmp_path: Path) -> None:
    module = _write_charm_module(tmp_path)
    (module / "variables.tf").write_text(
        COMPLIANT_VARIABLES_TF.replace(
            'variable "units" {\n  type    = number\n  default = 1\n}\n', ""
        )
    )
    violations = cc008_check.check_module(module)
    assert "charm module missing mandatory variable: units" in violations


def test_main_returns_zero_for_compliant_module(tmp_path: Path, capsys) -> None:
    module = _write_charm_module(tmp_path)
    exit_code = cc008_check.main([str(module)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_returns_one_for_noncompliant_module(tmp_path: Path, capsys) -> None:
    module = tmp_path / "broken"
    module.mkdir()
    exit_code = cc008_check.main([str(module)])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_logs_categories_and_summary(tmp_path: Path, capsys) -> None:
  module = _write_charm_module(tmp_path)

  exit_code = cc008_check.main([str(module)])

  output = capsys.readouterr().out
  assert exit_code == 0
  assert "Checking 1 Terraform module(s) for CC008 compliance" in output
  assert f"Checking {module} (charm module)" in output
  assert "PASS Required files" in output
  assert "PASS Terraform configuration" in output
  assert "PASS Variable ordering" in output
  assert "PASS Output ordering" in output
  assert "PASS Module interface" in output
  assert "PASS Module sources" in output
  assert "Summary: 1 checked, 1 passed, 0 failed" in output


def test_verbose_logs_discovered_interface(tmp_path: Path, capsys) -> None:
  module = _write_charm_module(tmp_path)

  exit_code = cc008_check.main(["--verbose", str(module)])

  output = capsys.readouterr().out
  assert exit_code == 0
  assert "Variables: app_name, base, channel, config, constraints, model_uuid, revision, units" in output
  assert "Outputs: application, provides, requires" in output
  assert "Module sources: none" in output


def test_github_actions_failure_emits_error_annotations(
  tmp_path: Path, capsys, monkeypatch
) -> None:
  module = tmp_path / "broken"
  module.mkdir()
  monkeypatch.setenv("GITHUB_ACTIONS", "true")

  exit_code = cc008_check.main([str(module)])

  output = capsys.readouterr().out
  assert exit_code == 1
  assert "::error title=CC008 compliance::" in output
  assert "missing required file: terraform.tf" in output
  assert "SKIP Terraform configuration (terraform.tf is missing)" in output
  assert "SKIP Variable ordering (variables.tf is missing)" in output
  assert "SKIP Output ordering (outputs.tf is missing)" in output
