import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def _install_charmcraft() -> None:
    subprocess.run(
        ["sudo", "snap", "install", "charmcraft", "--classic"],
        check=True,
    )


def _parse_build_context(argv: list[str]) -> tuple[Path, list[str]]:
    """Extract --build-context from argv, return (context_dir, remaining_args)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--build-context", default=None)
    namespace, remaining = parser.parse_known_args(argv)
    context_dir = Path(namespace.build_context) if namespace.build_context else Path.cwd()
    return context_dir, remaining


def main() -> None:
    if shutil.which("charmcraft") is None:
        _install_charmcraft()

    context_dir, charmcraft_args = _parse_build_context(sys.argv[1:])

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Copy charmcraft.yaml from the current working directory if present
        charm_yaml = Path.cwd() / "charmcraft.yaml"
        if charm_yaml.exists():
            shutil.copy2(charm_yaml, tmp_path / "charmcraft.yaml")

        # Copy all files from the build-context directory into the temp dir
        for item in context_dir.iterdir():
            dest = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        result = subprocess.run(["charmcraft"] + charmcraft_args, cwd=tmp_path)

        charm_name: str | None = None
        if charm_yaml.exists() and yaml is not None:
            with charm_yaml.open() as f:
                charm_name = (yaml.safe_load(f) or {}).get("name")

        for charm_file in tmp_path.glob("*.charm"):
            if charm_name is None or charm_file.name.startswith(charm_name):
                shutil.copy2(charm_file, Path.cwd() / charm_file.name)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
