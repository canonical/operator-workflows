import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from supercharm.files import charm_name_from_yaml, copy_charm_files, copy_context_to_temp, move_generated_lib

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


def _install_charmcraft() -> None:
    subprocess.run(
        ["sudo", "snap", "install", "charmcraft", "--classic"],
        check=True,
    )


def _parse_build_context(argv: list[str]) -> tuple[Path, list[str]]:
    """Extract --build-context from argv, return (context_dir, remaining_args)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--build-context", default=None)
    parser.add_argument("--project-dir", "-p", default=None)
    parser.add_argument("--output", "-o", default=None)
    namespace, remaining = parser.parse_known_args(argv)
    context_dir = Path(namespace.build_context) if namespace.build_context else Path.cwd()
    project_dir = Path(namespace.project_dir) if namespace.project_dir else Path.cwd()
    output = Path(namespace.output) if namespace.output else Path.cwd()
    return context_dir, project_dir, output, remaining


def main() -> None:
    argv = sys.argv[1:]
    log_level = logging.DEBUG if _peek_verbose(argv) else logging.WARNING
    logging.getLogger().setLevel(log_level)

    if shutil.which("charmcraft") is None:
        _install_charmcraft()

    context_dir, project_dir, output, charmcraft_args = _parse_build_context(argv)
    logger.warning("Output argument is ignored. Set to %s.", output)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        charm_yaml = Path.cwd() / project_dir / "charmcraft.yaml"
        logger.debug("Charm YAML path: %s", charm_yaml)
        abs_context_dir = context_dir.resolve()
        logger.debug("Resolved absolute context directory: %s", abs_context_dir)
        try:
            uv_working_dir = charm_yaml.parent.resolve().relative_to(abs_context_dir)
        except ValueError:
            uv_working_dir = None
        logger.debug("UV working dir: %s", uv_working_dir)
        copy_context_to_temp(abs_context_dir, tmp_path, charm_yaml)

        copy_charm_files(tmp_path, Path.cwd(), charm_name_from_yaml(charm_yaml))
        logger.debug("Running charmcraft: %s from %s", charmcraft_args, tmp_path)
        subprocess.run(["charmcraft", "fetch-libs"], cwd=tmp_path)
        move_generated_lib(tmp_path, uv_working_dir)
        result = subprocess.run(["charmcraft"] + charmcraft_args, cwd=tmp_path)     

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
