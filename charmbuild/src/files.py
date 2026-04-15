#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""File utilities for charmbuild: copying context, patching YAML, and moving build artefacts."""

import logging
import shutil
import yaml
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def compute_patched_yaml(charm_yaml: Path, rel_path: Path) -> "Optional[str]":
    """Load charm_yaml and return patched YAML content, or None if no patch is needed.

    Patches the single uv-plugin part's build-environment, replacing any UV_WORKING_DIR
    set to '.' with the given rel_path. Returns None when rel_path is '.', when the file
    does not exist, when there is not exactly one uv part, or when no UV_WORKING_DIR
    entry equals '.'.
    """
    if rel_path == Path(".") or yaml is None or not charm_yaml.exists():
        return None

    with charm_yaml.open() as f:
        data = yaml.safe_load(f) or {}

    parts = data.get("parts", {})
    uv_parts = [
        p for p in parts.values() if isinstance(p, dict) and p.get("plugin") == "uv"
    ]
    if len(uv_parts) != 1:
        return None
    uv_part = uv_parts[0]

    rel_str = str(rel_path)
    build_env = uv_part.get("build-environment", [])
    patched = False
    new_build_env = []
    for entry in build_env:
        if isinstance(entry, dict) and entry.get("UV_WORKING_DIR") == ".":
            new_build_env.append({"UV_WORKING_DIR": rel_str})
            patched = True
        else:
            new_build_env.append(entry)

    if not patched:
        return None

    uv_part["build-environment"] = new_build_env
    return yaml.dump(data, default_flow_style=False)


def copy_context_to_temp(
    abs_context_dir: Path,
    tmp_path: Path,
    charm_yaml: Path,
    patched_yaml_content: "Optional[str]" = None,
) -> None:
    """Copy charmcraft.yaml (if present) and all files from context_dir into tmp_path.

    If patched_yaml_content is provided, it is written as charmcraft.yaml in tmp_path
    instead of copying the original file.
    """
    logger.debug(
        "Copying context to temp directory: abs_context_dir=%s, tmp_path=%s, charm_yaml=%s",
        abs_context_dir,
        tmp_path,
        charm_yaml,
    )
    logger.debug("Resolved absolute context directory: %s", abs_context_dir)

    for item in abs_context_dir.iterdir():
        dest = tmp_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    if charm_yaml.exists():
        dest_yaml = tmp_path / "charmcraft.yaml"
        if patched_yaml_content is not None:
            dest_yaml.write_text(patched_yaml_content)
            logger.debug("Wrote patched charmcraft.yaml:\n%s", patched_yaml_content)
        else:
            shutil.copy2(charm_yaml, dest_yaml)


def move_generated_lib(tmp_path: Path, dest_dir: Path) -> None:
    """Move a lib directory generated at the tmp_path root into the dest_dir subdirectory.

    When charmcraft generates a lib directory (e.g. via fetch-libs) it places it relative
    to the charmcraft.yaml, which is at tmp_path root.  The charm sources live under
    tmp_path / uv_working_dir, so the lib must be moved there to be usable.
    """
    generated_lib = tmp_path / "lib"
    for file in generated_lib.glob("*.py"):
        logger.debug("Moving generated lib: %s -> %s", file, dest_dir)
        shutil.copy2(file, dest_dir / file.name)
    else:
        logger.debug("No generated lib found at %s, skipping move", generated_lib)


def charm_name_from_yaml(charm_yaml: Path) -> Optional[str]:
    """Return the 'name' field from charmcraft.yaml, or None if unavailable."""
    if not charm_yaml.exists() or yaml is None:
        return None
    with charm_yaml.open() as f:
        return (yaml.safe_load(f) or {}).get("name")


def copy_charm_files(
    tmp_path: Path, dest_dir: Path, charm_name: Optional[str]
) -> list[Path]:
    """Copy .charm files from tmp_path to dest_dir, filtered by charm_name prefix.

    Returns the list of files that were copied.
    """
    copied: list[Path] = []
    for charm_file in tmp_path.glob("*.charm"):
        if charm_name is None or charm_file.name.startswith(charm_name):
            shutil.copy2(charm_file, dest_dir / charm_file.name)
            copied.append(dest_dir / charm_file.name)
    return copied
