import shutil
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def copy_context_to_temp(context_dir: Path, tmp_path: Path, charm_yaml: Path) -> None:
    """Copy charmcraft.yaml (if present) and all files from context_dir into tmp_path."""
    if charm_yaml.exists():
        shutil.copy2(charm_yaml, tmp_path / "charmcraft.yaml")

    for item in context_dir.iterdir():
        dest = tmp_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


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
