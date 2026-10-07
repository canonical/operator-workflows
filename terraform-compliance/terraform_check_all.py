# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI that discovers Terraform modules in a repository and checks all of
them for compliance (see ``terraform_check`` for discovery/classification
and the compliance checks: module type is classified from HCL content via
``terraform_check.classify_module_type``).
"""

import argparse
import sys
from pathlib import Path

import terraform_check

# Directories never worth walking into while searching for Terraform modules,
# including "tests" directories whose Terraform modules (and all nested
# content) are ignored.
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
        "tests",
    }
)


def discover_module_directories(root: Path) -> list[Path]:
    """Find Terraform module directories under ``root``.

    Walks the tree looking for ``main.tf`` files, pruning known vendor/hidden
    directories and any directory named ``tests`` (which is ignored along
    with everything beneath it).
    """
    included: list[Path] = []
    for current in sorted(root.rglob("*")):
        if not current.is_dir():
            continue
        if set(current.relative_to(root).parts) & EXCLUDED_DIR_NAMES:
            continue
        if (current / "main.tf").is_file():
            included.append(current)
    return included


def main(argv: list[str] | None = None) -> int:
    """Discover Terraform modules under a repo root and check all of them."""
    parser = argparse.ArgumentParser(
        description=(
            "Discover Terraform module directories under a repository root "
            "(by locating main.tf files) and check all of them for "
            "compliance with the configured spec."
        )
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show variables, outputs, and module sources discovered during parsing.",
    )
    parser.add_argument(
        "root", help="Repository root directory to search for Terraform modules."
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: repository root is not a directory: {root}")
        return 2
    included = discover_module_directories(root)

    if not included:
        print("No Terraform modules found")
        return 0

    check_argv = (["--verbose"] if args.verbose else []) + [
        str(directory) for directory in included
    ]
    return terraform_check.main(check_argv)


if __name__ == "__main__":
    sys.exit(main())
