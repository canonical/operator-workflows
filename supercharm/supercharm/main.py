import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from supercharm.files import charm_name_from_yaml, copy_charm_files, copy_context_to_temp


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
        copy_context_to_temp(context_dir, tmp_path, charm_yaml)

        result = subprocess.run(["charmcraft"] + charmcraft_args, cwd=tmp_path)

        copy_charm_files(tmp_path, Path.cwd(), charm_name_from_yaml(charm_yaml))

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
