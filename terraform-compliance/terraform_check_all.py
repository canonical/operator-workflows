# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI that discovers Terraform modules in a repository and checks all of
them for compliance (see ``terraform_discover`` for the discovery/
classification rules, and ``terraform_check`` for the compliance checks).
"""

import argparse
import sys
from pathlib import Path

import terraform_check
from terraform_discover import discover_module_directories


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
    included, errors = discover_module_directories(root)

    for error in errors:
        print(f"ERROR: {error}")
        print(
            f"::error title=Terraform compliance discovery::"
            f"{terraform_check.escape_annotation(error)}"
        )

    if not included:
        print("No Terraform modules found" if not errors else "No Terraform modules checked")
        return 1 if errors else 0

    check_argv = (["--verbose"] if args.verbose else []) + [
        str(directory) for directory in included
    ]
    check_exit_code = terraform_check.main(check_argv)

    return check_exit_code or (1 if errors else 0)


if __name__ == "__main__":
    sys.exit(main())
