import shutil
import subprocess
import sys


def _install_charmcraft() -> None:
    subprocess.run(
        ["sudo", "snap", "install", "charmcraft", "--classic"],
        check=True,
    )


def main() -> None:
    if shutil.which("charmcraft") is None:
        _install_charmcraft()

    result = subprocess.run(["charmcraft"] + sys.argv[1:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
