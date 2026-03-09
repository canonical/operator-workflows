import logging
import shutil
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _patch_charmcraft_yaml(yaml_path: Path, rel_path: Path) -> None:
    """Add UV_WORKING_DIR and override-build to the charm part in a charmcraft.yaml."""
    if yaml is None:
        return

    rel_str = str(rel_path)
    with yaml_path.open() as f:
        data = yaml.safe_load(f) or {}

    parts = data.setdefault("parts", {})
    charm = parts.setdefault("charm", {})

    build_env = charm.get("build-environment", [])
    build_env = [e for e in build_env if not (isinstance(e, dict) and "UV_WORKING_DIR" in e)]
    build_env.append({"UV_WORKING_DIR": rel_str})
    charm["build-environment"] = build_env

    charm["override-build"] = (
        "craftctl default\n"
        "cp --archive --recursive --reflink=auto"
        " $CRAFT_PART_BUILD/$UV_WORKING_DIR/src $CRAFT_PART_INSTALL/src\n"
        "cp --archive --recursive --reflink=auto"
        " $CRAFT_PART_BUILD/$UV_WORKING_DIR/lib $CRAFT_PART_INSTALL/lib\n"
    )

    with yaml_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False)

    logger.debug("Patched charmcraft.yaml (UV_WORKING_DIR=%s):\n%s", rel_str, yaml_path.read_text())


def copy_context_to_temp(abs_context_dir: Path, tmp_path: Path, charm_yaml: Path) -> None:
    """Copy charmcraft.yaml (if present) and all files from context_dir into tmp_path."""
    logger.debug("Copying context to temp directory: abs_context_dir=%s, tmp_path=%s, charm_yaml=%s",
                 abs_context_dir, tmp_path, charm_yaml)
    logger.debug("Resolved absolute context directory: %s", abs_context_dir)

    if charm_yaml.exists():
        shutil.copy2(charm_yaml, tmp_path / "charmcraft.yaml")
        try:
            rel_path = charm_yaml.parent.relative_to(abs_context_dir)
            logger.debug("Charm YAML relative path: %s", rel_path)
        except ValueError:
            rel_path = Path(".")
        if rel_path != Path("."):
            _patch_charmcraft_yaml(tmp_path / "charmcraft.yaml", rel_path)

    for item in abs_context_dir.iterdir():
        dest = tmp_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def move_generated_lib(tmp_path: Path, uv_working_dir: Path) -> None:
    """Move a lib directory generated at the tmp_path root into the UV_WORKING_DIR subdirectory.

    When charmcraft generates a lib directory (e.g. via fetch-libs) it places it relative
    to the charmcraft.yaml, which is at tmp_path root.  The charm sources live under
    tmp_path / uv_working_dir, so the lib must be moved there to be usable.
    """
    generated_lib = tmp_path / "lib"
    if generated_lib.exists():
        dest = tmp_path / uv_working_dir / "lib"
        logger.debug("Moving generated lib: %s -> %s", generated_lib, dest)
        shutil.move(str(generated_lib), dest)
    else:
        logger.debug("No generated lib found at %s, skipping move", generated_lib)


def charm_name_from_yaml(charm_yaml: Path) -> Optional[str]:
    """Return the 'name' field from charmcraft.yaml, or None if unavailable."""
    if not charm_yaml.exists() or yaml is None:
        return None
    with charm_yaml.open() as f:
        return (yaml.safe_load(f) or {}).get("name")


def copy_charm_files(tmp_path: Path, dest_dir: Path, charm_name: Optional[str]) -> list[Path]:
    """Copy .charm files from tmp_path to dest_dir, filtered by charm_name prefix.

    Returns the list of files that were copied.
    """
    copied: list[Path] = []
    for charm_file in tmp_path.glob("*.charm"):
        if charm_name is None or charm_file.name.startswith(charm_name):
            shutil.copy2(charm_file, dest_dir / charm_file.name)
            copied.append(dest_dir / charm_file.name)
    return copied
