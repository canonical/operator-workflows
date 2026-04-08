#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Entry point for charmbuild: wraps charmcraft with build-context support."""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from charmbuild.files import (
    charm_name_from_yaml,
    compute_patched_yaml,
    copy_charm_files,
    copy_context_to_temp,
    move_generated_lib,
)

logging.basicConfig(format="%(name)s: %(message)s")

logger = logging.getLogger(__name__)


def _peek_verbose(argv: list[str]) -> bool:
    """Check whether --verbose / -v is present in argv without consuming it.

    The flag is intentionally left in argv so it is forwarded to charmcraft.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--verbose", "-v", action="store_true", default=False)
    namespace, _ = parser.parse_known_args(argv)
    return namespace.verbose


def _parse_build_context(argv: list[str]) -> tuple[Path, Path, Path, list[str]]:
    """Extract charmbuild-specific flags from argv.

    Returns a 4-tuple of (context_dir, project_dir, output, remaining_args), where
    remaining_args contains the args that were not consumed and should be forwarded
    to charmcraft.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--build-context", default=None)
    parser.add_argument("--project-dir", "-p", default=None)
    parser.add_argument("--output", "-o", default=None)
    namespace, remaining = parser.parse_known_args(argv)
    context_dir = (
        Path(namespace.build_context) if namespace.build_context else Path.cwd()
    )
    project_dir = Path(namespace.project_dir) if namespace.project_dir else Path.cwd()
    output = Path(namespace.output) if namespace.output else Path.cwd()
    return context_dir, project_dir, output, remaining


def main() -> None:
    """Run charmcraft with build-context staging and lib migration."""
    argv = sys.argv[1:]
    log_level = logging.DEBUG if _peek_verbose(argv) else logging.WARNING
    logging.getLogger().setLevel(log_level)

    if shutil.which("charmcraft") is None:
        logger.error(
            "charmcraft is not installed. Please install it before running charmbuild."
        )
        sys.exit(1)

    context_dir, project_dir, output, charmcraft_args = _parse_build_context(argv)
    subcommand = charmcraft_args[0] if charmcraft_args else ""
    if subcommand != "pack" or context_dir is None or context_dir == ".":
        result = subprocess.run(
            ["charmcraft"] + charmcraft_args, env=os.environ, check=False
        )
        sys.exit(result.returncode)

    charm_yaml = Path.cwd() / project_dir / "charmcraft.yaml"
    logger.debug("Charm YAML path: %s", charm_yaml)
    abs_context_dir = context_dir.resolve()
    logger.debug("Resolved absolute context directory: %s", abs_context_dir)
    try:
        uv_working_dir = charm_yaml.parent.resolve().relative_to(abs_context_dir)
    except ValueError:
        uv_working_dir = Path(".")
    logger.debug("UV working dir: %s", uv_working_dir)

    patched_yaml_content = compute_patched_yaml(charm_yaml, uv_working_dir)

    if patched_yaml_content is None:
        logger.debug(
            "No YAML patch needed; running charmcraft directly from %s",
            charm_yaml.parent,
        )
        result = subprocess.run(
            ["charmcraft"] + charmcraft_args,
            cwd=charm_yaml.parent,
            env=os.environ,
            check=False,
        )
        sys.exit(result.returncode)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        copy_context_to_temp(
            abs_context_dir, tmp_path, charm_yaml, patched_yaml_content
        )

        logger.debug("Running charmcraft: %s from %s", charmcraft_args, tmp_path)
        try:
            subprocess.run(
                ["charmcraft", "fetch-libs"], cwd=tmp_path, env=os.environ, check=True
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "`charmcraft fetch-libs` failed with exit code %s", exc.returncode
            )
            sys.exit(exc.returncode)
        move_generated_lib(tmp_path, Path.cwd())
        result = subprocess.run(
            ["charmcraft"] + charmcraft_args, cwd=tmp_path, env=os.environ, check=False
        )
        copy_charm_files(tmp_path, Path.cwd(), charm_name_from_yaml(charm_yaml))

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
