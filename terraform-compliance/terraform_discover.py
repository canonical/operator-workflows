# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Discover Terraform module directories in a repository tree.

Finds every ``main.tf`` and classifies its containing directory by name, so
that ``terraform_check_all`` knows which directories to run the compliance
checker (``terraform_check``) against. This classification is only used for
*discovery*: the actual per-module compliance checks still rely on
``terraform_check.classify_module_type``, which inspects HCL content.
"""

import os
from enum import StrEnum
from pathlib import Path

# Directories never worth walking into while searching for Terraform modules.
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".terraform",
        ".venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
    }
)

# Directories whose Terraform modules (and all nested content) are ignored.
_IGNORED_DIR_NAME = "tests"


class ModulePathClassification(StrEnum):
    """How a module directory's own name classifies it for discovery."""

    CHARM = "charm"
    PRODUCT = "product"


class UnsupportedModuleType(ValueError):
    """Raised when a module directory's name matches no known convention."""

    def __init__(self, module_dir: Path) -> None:
        self.module_dir = module_dir
        super().__init__(f"Unsupported module type: {module_dir}")


def classify_module_path(module_dir: Path) -> ModulePathClassification:
    """Classify a module directory for discovery purposes, by its own name.

    Raises ``UnsupportedModuleType`` if the name matches no known
    convention. Callers are expected to have already excluded directories
    named ``tests`` before calling this (see ``discover_module_directories``).
    """
    name = module_dir.name
    if name == "terraform":
        return ModulePathClassification.CHARM
    if "product" in name.lower():
        return ModulePathClassification.PRODUCT
    raise UnsupportedModuleType(module_dir)


def discover_module_directories(root: Path) -> tuple[list[Path], list[str]]:
    """Find Terraform module directories under ``root``.

    Walks the tree looking for ``main.tf`` files, pruning known vendor/hidden
    directories and any directory named ``tests`` (which is ignored along
    with everything beneath it). Returns ``(included_module_dirs,
    error_messages)``: directories classified as charm/product modules are
    included; directories with a ``main.tf`` but an unrecognised name produce
    an ``"Unsupported module type: <path>"`` error message, and scanning
    continues.
    """
    included: list[Path] = []
    errors: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in EXCLUDED_DIR_NAMES and name != _IGNORED_DIR_NAME
        )
        if current.name == _IGNORED_DIR_NAME:
            continue
        if "main.tf" not in filenames:
            continue
        try:
            classify_module_path(current)
        except UnsupportedModuleType as exc:
            errors.append(str(exc))
            continue
        included.append(current)
    return included, errors
