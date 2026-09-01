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


def test_terraform_block_juju_version_strictly_above_one_passes() -> None:
    text = """\
terraform {
  required_version = "~> 1.12"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "> 1.0.0"
    }
  }
}
"""
    assert cc008_check.check_terraform_block(hcl2.loads(text)) == []


def test_terraform_block_juju_exact_pin_at_one_passes() -> None:
    text = """\
terraform {
  required_version = "~> 1.12"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "1.0.0"
    }
  }
}
"""
    assert cc008_check.check_terraform_block(hcl2.loads(text)) == []


def test_terraform_block_juju_version_with_only_upper_bound_fails() -> None:
    text = """\
terraform {
  required_version = "~> 1.12"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "< 3.0"
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


def test_is_composed_module_detects_module_blocks() -> None:
    charm = hcl2.loads('resource "juju_application" "demo" {\n  name = var.app_name\n}\n')
    composed = hcl2.loads('module "demo" {\n  source = "../modules/demo"\n}\n')
    assert cc008_check.is_composed_module([charm]) is False
    assert cc008_check.is_composed_module([composed]) is True


def test_classify_module_type_charm_when_no_module_blocks() -> None:
    charm = hcl2.loads('resource "juju_application" "demo" {\n  name = var.app_name\n}\n')
    assert cc008_check.classify_module_type([charm]) == "charm"


def test_classify_module_type_component_when_no_tying_resources() -> None:
    composed = hcl2.loads('module "demo" {\n  source = "../modules/demo"\n}\n')
    assert cc008_check.classify_module_type([composed]) == "component"


def test_classify_module_type_product_when_tying_resource_present() -> None:
    composed = hcl2.loads(
        'module "demo" {\n  source = "../modules/demo"\n}\n'
        'resource "juju_integration" "demo" {\n  model_uuid = var.model_uuid\n}\n'
    )
    assert cc008_check.classify_module_type([composed]) == "product"


def test_charm_interface_requires_mandatory_variables_and_outputs() -> None:
    violations = cc008_check.check_interface(variables={}, outputs=[], module_type="charm")
    for variable in ("app_name", "channel", "config", "constraints", "model_uuid", "revision"):
        assert f"charm module missing mandatory variable: {variable}" in violations
    for output in ("application", "provides", "requires"):
        assert f"charm module missing mandatory output: {output}" in violations


def test_units_is_not_mandated_for_charm_modules() -> None:
    # CC008 exempts subordinate charms from `units`, and subordinate-ness is
    # not detectable from Terraform, so `units` is intentionally not required.
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                'variable "app_name" {\n  type = string\n}\n'
                'variable "channel" {\n  type = string\n}\n'
                'variable "config" {\n  type = map(string)\n}\n'
                'variable "constraints" {\n  type = string\n}\n'
                'variable "model_uuid" {\n  type = string\n}\n'
                'variable "revision" {\n  type = number\n}\n'
            )
        ]
    )
    violations = cc008_check.check_interface(
        variables, ["application", "provides", "requires"], module_type="charm"
    )
    assert violations == []


def test_compliant_charm_interface_passes() -> None:
    variables = cc008_check.variable_bodies([hcl2.loads(COMPLIANT_VARIABLES_TF)])
    outputs = ["application", "provides", "requires"]
    assert cc008_check.check_interface(variables, outputs, module_type="charm") == []


def test_component_interface_requires_mandatory_variables_and_outputs() -> None:
    violations = cc008_check.check_interface(variables={}, outputs=[], module_type="component")
    assert "component module missing mandatory variable: model_uuid" in violations
    assert "component module missing mandatory output: components" in violations


def test_compliant_component_interface_passes() -> None:
    variables = cc008_check.variable_bodies(
        [hcl2.loads('variable "model_uuid" {\n  type = string\n}\n')]
    )
    violations = cc008_check.check_interface(variables, ["components"], module_type="component")
    assert violations == []


def test_product_interface_requires_models_and_metadata() -> None:
    violations = cc008_check.check_interface(variables={}, outputs=[], module_type="product")
    assert "product module missing mandatory output: models" in violations
    assert "product module missing mandatory output: metadata" in violations


def test_product_interface_requires_mandatory_variables() -> None:
    violations = cc008_check.check_interface(variables={}, outputs=[], module_type="product")
    for variable in ("logging-config", "proxy", "risk"):
        assert f"product module missing mandatory variable: {variable}" in violations
    assert "product module missing mandatory variable: juju_controller" not in violations


def test_compliant_product_interface_passes() -> None:
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                'variable "logging-config" {\n  type = string\n}\n'
                'variable "proxy" {\n  type = object({ http = optional(string) })\n}\n'
                'variable "risk" {\n  type = string\n}\n'
            )
        ]
    )
    assert cc008_check.check_interface(variables, ["models", "metadata"], module_type="product") == []


def test_model_uuid_with_default_is_reported_as_not_required() -> None:
    variables = cc008_check.variable_bodies(
        [hcl2.loads('variable "model_uuid" {\n  type = string\n  default = null\n}\n')]
    )
    violations = cc008_check.check_interface(variables, ["components"], module_type="component")
    assert len(violations) == 1
    assert 'variable "model_uuid": must not declare a default' in violations[0]


def test_revision_wrong_default_is_reported() -> None:
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                COMPLIANT_VARIABLES_TF.replace(
                    'variable "revision" {\n  type    = number\n  default = null\n}\n',
                    'variable "revision" {\n  type    = number\n  default = 5\n}\n',
                )
            )
        ]
    )
    violations = cc008_check.check_interface(variables, ["application", "provides", "requires"], module_type="charm")
    assert len(violations) == 1
    assert 'variable "revision": default must be None' in violations[0]


def test_constraints_wrong_default_is_reported() -> None:
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                COMPLIANT_VARIABLES_TF.replace(
                    'variable "constraints" {\n  type    = string\n  default = null\n}\n',
                    'variable "constraints" {\n  type    = string\n  default = "arch=amd64"\n}\n',
                )
            )
        ]
    )
    violations = cc008_check.check_interface(variables, ["application", "provides", "requires"], module_type="charm")
    assert len(violations) == 1
    assert 'variable "constraints": default must be None' in violations[0]


def test_revision_wrong_type_family_is_reported() -> None:
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                COMPLIANT_VARIABLES_TF.replace(
                    'variable "revision" {\n  type    = number\n  default = null\n}\n',
                    'variable "revision" {\n  type    = string\n  default = null\n}\n',
                )
            )
        ]
    )
    violations = cc008_check.check_interface(variables, ["application", "provides", "requires"], module_type="charm")
    assert any('variable "revision": expected a number-like type, found string' in v for v in violations)


def test_config_map_type_family_passes_as_collection() -> None:
    variables = cc008_check.variable_bodies([hcl2.loads(COMPLIANT_VARIABLES_TF)])
    violations = cc008_check.check_interface(variables, ["application", "provides", "requires"], module_type="charm")
    assert not any('variable "config"' in v for v in violations)


def test_absent_optional_variable_is_not_reported() -> None:
    # `resources` is an optional charm variable; a charm that omits it must not
    # be flagged.
    variables = cc008_check.variable_bodies([hcl2.loads(COMPLIANT_VARIABLES_TF)])
    violations = cc008_check.check_interface(
        variables, ["application", "provides", "requires"], module_type="charm"
    )
    assert not any("resources" in v for v in violations)


def test_present_optional_variable_with_wrong_type_is_reported() -> None:
    # `base` is an optional string variable; if declared it must be string-like.
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                COMPLIANT_VARIABLES_TF.replace(
                    'variable "base" {\n  type    = string\n  default = null\n}\n',
                    'variable "base" {\n  type    = number\n  default = null\n}\n',
                )
            )
        ]
    )
    violations = cc008_check.check_interface(
        variables, ["application", "provides", "requires"], module_type="charm"
    )
    assert any('variable "base": expected a string-like type, found number' in v for v in violations)


def test_present_optional_variable_with_valid_type_passes() -> None:
    variables = cc008_check.variable_bodies(
        [
            hcl2.loads(
                COMPLIANT_VARIABLES_TF
                + 'variable "resources" {\n  type = map(string)\n  default = {}\n}\n'
            )
        ]
    )
    violations = cc008_check.check_interface(
        variables, ["application", "provides", "requires"], module_type="charm"
    )
    assert not any("resources" in v for v in violations)


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


def test_branch_ref_is_reported_case_insensitively() -> None:
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform?ref=Main"\n'
        "}\n"
    )
    violations = cc008_check.check_pinned_module_sources([hcl2.loads(text)])
    assert len(violations) == 1
    assert "floating references are not allowed" in violations[0]


def test_other_known_default_branch_names_are_reported() -> None:
    for branch in ("master", "develop", "trunk"):
        text = (
            'module "ic" {\n'
            f'  source = "git::https://github.com/canonical/x-operator//terraform?ref={branch}"\n'
            "}\n"
        )
        violations = cc008_check.check_pinned_module_sources([hcl2.loads(text)])
        assert len(violations) == 1, branch
        assert "floating references are not allowed" in violations[0]


def test_registry_version_source_is_allowed() -> None:
    text = 'module "ic" {\n  source  = "canonical/x/juju"\n  version = "1.2.0"\n}\n'
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_bare_semver_ref_is_allowed() -> None:
    # A dependency in a repository that does not yet follow CC008's own
    # tag-naming convention may still be pinned with a bare semver tag.
    # Enforcing that repository's tag naming is outside this checker's scope.
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/not-yet-cc008//terraform?ref=1.4.2"\n'
        "}\n"
    )
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_product_prefixed_semver_ref_is_allowed() -> None:
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-bundle//terraform'
        '?ref=gateway-api-integrator-1.0.0"\n'
        "}\n"
    )
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_prerelease_suffixed_ref_is_allowed() -> None:
    # A ref has no required shape; a pre-release tag is a legitimate pin, not
    # a branch, so it is not flagged.
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform?ref=1.0.0-rc1"\n'
        "}\n"
    )
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_arbitrary_named_tag_ref_is_allowed() -> None:
    # Refs are not required to look like semver at all.
    text = (
        'module "ic" {\n'
        '  source = "git::https://github.com/canonical/x-operator//terraform?ref=stable-release"\n'
        "}\n"
    )
    assert cc008_check.check_pinned_module_sources([hcl2.loads(text)]) == []


def test_compliant_charm_module_has_no_violations(tmp_path: Path) -> None:
    module = _write_charm_module(tmp_path)
    assert cc008_check.check_module(module) == []


def test_check_module_reports_missing_mandatory_variable(tmp_path: Path) -> None:
    module = _write_charm_module(tmp_path)
    (module / "variables.tf").write_text(
        COMPLIANT_VARIABLES_TF.replace(
            'variable "channel" {\n  type    = string\n  default = "1/stable"\n}\n', ""
        )
    )
    violations = cc008_check.check_module(module)
    assert "charm module missing mandatory variable: channel" in violations


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


def test_main_returns_two_when_no_directories_are_configured(capsys, monkeypatch) -> None:
  monkeypatch.setenv("GITHUB_ACTIONS", "true")

  exit_code = cc008_check.main([])

  output = capsys.readouterr().out
  assert exit_code == 2
  assert "ERROR: no Terraform module directories were provided" in output
  assert "::error title=CC008 configuration::" in output


def test_nonexistent_module_directory_fails(tmp_path: Path, capsys) -> None:
  missing = tmp_path / "does-not-exist"

  exit_code = cc008_check.main([str(missing)])

  output = capsys.readouterr().out
  assert exit_code == 1
  assert f"module directory does not exist: {missing}" in output
  assert "Summary: 1 checked, 0 passed, 1 failed" in output


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
