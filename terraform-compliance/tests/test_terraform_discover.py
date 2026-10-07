# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Terraform module discovery/classification."""

from pathlib import Path

import pytest
from terraform_discover import (
    ModulePathClassification,
    UnsupportedModuleType,
    classify_module_path,
    discover_module_directories,
)


def test_classify_exact_terraform_is_charm(tmp_path: Path) -> None:
    module = tmp_path / "terraform"

    assert classify_module_path(module) is ModulePathClassification.CHARM


def test_classify_terraform_substring_is_not_charm(tmp_path: Path) -> None:
    module = tmp_path / "my-terraform-thing"

    with pytest.raises(UnsupportedModuleType):
        classify_module_path(module)


@pytest.mark.parametrize(
    "name", ["product", "my-product", "Product", "PRODUCT-foo", "foo-product-bar"]
)
def test_classify_product_substring_case_insensitive(tmp_path: Path, name: str) -> None:
    module = tmp_path / name

    assert classify_module_path(module) is ModulePathClassification.PRODUCT


def test_classify_unsupported_name_raises_with_path_in_message(tmp_path: Path) -> None:
    module = tmp_path / "widgets"

    with pytest.raises(UnsupportedModuleType) as excinfo:
        classify_module_path(module)

    assert str(excinfo.value) == f"Unsupported module type: {module}"
    assert excinfo.value.module_dir == module


def _touch_main_tf(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "main.tf").write_text("")


def test_discover_includes_charm_and_product_modules(tmp_path: Path) -> None:
    _touch_main_tf(tmp_path / "terraform")
    _touch_main_tf(tmp_path / "some-product")

    included, errors = discover_module_directories(tmp_path)

    assert sorted(included) == sorted(
        [tmp_path / "terraform", tmp_path / "some-product"]
    )
    assert errors == []


def test_discover_ignores_tests_directory_entirely(tmp_path: Path) -> None:
    _touch_main_tf(tmp_path / "terraform")
    _touch_main_tf(tmp_path / "tests")
    # Nested fixture under tests/ must not be discovered or flagged either.
    _touch_main_tf(tmp_path / "tests" / "whatever-unsupported-name")

    included, errors = discover_module_directories(tmp_path)

    assert included == [tmp_path / "terraform"]
    assert errors == []


def test_discover_reports_unsupported_module_type_and_continues(tmp_path: Path) -> None:
    _touch_main_tf(tmp_path / "terraform")
    _touch_main_tf(tmp_path / "widgets")
    _touch_main_tf(tmp_path / "some-product")

    included, errors = discover_module_directories(tmp_path)

    assert sorted(included) == sorted(
        [tmp_path / "terraform", tmp_path / "some-product"]
    )
    assert errors == [f"Unsupported module type: {tmp_path / 'widgets'}"]


def test_discover_excludes_vendor_and_hidden_directories(tmp_path: Path) -> None:
    _touch_main_tf(tmp_path / "terraform")
    for vendor_dir in (".git", ".terraform", ".venv", "node_modules", "__pycache__"):
        # These directories would classify as unsupported if ever visited.
        _touch_main_tf(tmp_path / vendor_dir / "unsupported-name")

    included, errors = discover_module_directories(tmp_path)

    assert included == [tmp_path / "terraform"]
    assert errors == []


def test_discover_root_itself_named_tests_is_ignored(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    _touch_main_tf(tests_root)

    included, errors = discover_module_directories(tests_root)

    assert included == []
    assert errors == []


def test_discover_with_no_modules_found(tmp_path: Path) -> None:
    included, errors = discover_module_directories(tmp_path)

    assert included == []
    assert errors == []
