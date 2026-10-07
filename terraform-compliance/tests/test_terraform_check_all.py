# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the terraform-check-all CLI (discovery + aggregate check)."""

from pathlib import Path

import terraform_check_all
from test_terraform_modules_compliance import (
    COMPLIANT_MAIN_TF,
    COMPLIANT_OUTPUTS_TF,
    COMPLIANT_TERRAFORM_TF,
    COMPLIANT_VARIABLES_TF,
)


def _write_compliant_module(module_dir: Path) -> None:
    module_dir.mkdir(parents=True)
    (module_dir / "terraform.tf").write_text(COMPLIANT_TERRAFORM_TF)
    (module_dir / "variables.tf").write_text(COMPLIANT_VARIABLES_TF)
    (module_dir / "outputs.tf").write_text(COMPLIANT_OUTPUTS_TF)
    (module_dir / "main.tf").write_text(COMPLIANT_MAIN_TF)
    (module_dir / "README.md").write_text("# demo\n")


def test_no_modules_found_passes(tmp_path: Path, capsys) -> None:
    exit_code = terraform_check_all.main([str(tmp_path)])

    assert exit_code == 0
    assert "No Terraform modules found" in capsys.readouterr().out


def test_all_compliant_modules_pass(tmp_path: Path, capsys) -> None:
    _write_compliant_module(tmp_path / "terraform")
    _write_compliant_module(tmp_path / "my-product")

    exit_code = terraform_check_all.main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "2 checked, 2 passed, 0 failed, 0 unsupported" in out


def test_unsupported_module_type_fails_even_if_others_pass(
    tmp_path: Path, capsys
) -> None:
    _write_compliant_module(tmp_path / "terraform")
    (tmp_path / "widgets").mkdir()
    (tmp_path / "widgets" / "main.tf").write_text("")

    exit_code = terraform_check_all.main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert f"Unsupported module type: {tmp_path / 'widgets'}" in out
    assert "1 checked, 1 passed, 0 failed, 1 unsupported" in out


def test_only_unsupported_module_types_found(tmp_path: Path, capsys) -> None:
    (tmp_path / "widgets").mkdir()
    (tmp_path / "widgets" / "main.tf").write_text("")

    exit_code = terraform_check_all.main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert f"Unsupported module type: {tmp_path / 'widgets'}" in out
    assert "Summary: 0 checked, 0 passed, 0 failed, 1 unsupported" in out


def test_tests_directory_is_not_checked(tmp_path: Path, capsys) -> None:
    _write_compliant_module(tmp_path / "terraform")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "main.tf").write_text("")

    exit_code = terraform_check_all.main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1 checked, 1 passed, 0 failed, 0 unsupported" in out
    assert "Unsupported module type" not in out
    assert str(tmp_path / "tests") not in out


def test_noncompliant_module_fails(tmp_path: Path, capsys) -> None:
    module = tmp_path / "terraform"
    module.mkdir()
    (module / "main.tf").write_text("")

    exit_code = terraform_check_all.main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "1 checked, 0 passed, 1 failed, 0 unsupported" in out
