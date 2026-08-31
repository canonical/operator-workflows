# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CC008 Terraform module compliance checker.

Verifies that Terraform modules follow the CC008 (Terraform module standards)
structure and interface requirements. HCL is parsed with python-hcl2, whose v8
output keeps literal double quotes around string values and block labels and
adds an ``__is_block__`` sentinel to block bodies; both are handled here.
"""

import argparse
import re
import sys
from pathlib import Path

import hcl2

REQUIRED_FILES = ("terraform.tf", "variables.tf", "outputs.tf", "main.tf", "README.md")

MANDATORY_CHARM_VARIABLES = (
    "app_name",
    "channel",
    "config",
    "constraints",
    "model_uuid",
    "revision",
    "units",
)

MANDATORY_CHARM_OUTPUTS = ("application", "provides", "requires")
MANDATORY_PRODUCT_OUTPUTS = ("metadata", "models")

_REF_PATTERN = re.compile(r"^(v?\d+\.\d+\.\d+|tf-\d+\.\d+\.\d+|[0-9a-f]{7,40})$")


def _unquote(value: str) -> str:
    """Strip the surrounding double quotes python-hcl2 keeps on string literals."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def block_names(parsed: dict, block_type: str) -> list[str]:
    """Return the ordered labels of blocks of a given type in a parsed file."""
    names: list[str] = []
    for block in parsed.get(block_type, []):
        label = next(key for key in block if key != "__is_block__")
        names.append(_unquote(label))
    return names


def check_required_files(module_dir: Path) -> list[str]:
    """Return violations for any missing required module file."""
    return [
        f"missing required file: {name}"
        for name in REQUIRED_FILES
        if not (module_dir / name).exists()
    ]


def check_terraform_block(parsed: dict) -> list[str]:
    """Return violations for the required_version and juju provider."""
    blocks = parsed.get("terraform", [])
    if not blocks:
        return ["terraform.tf: missing terraform block"]
    block = blocks[0]
    violations: list[str] = []
    if not block.get("required_version"):
        violations.append("terraform.tf: missing required_version")
    providers = block.get("required_providers")
    if isinstance(providers, list):
        providers = providers[0] if providers else {}
    juju = (providers or {}).get("juju")
    if not juju:
        violations.append("terraform.tf: missing juju provider in required_providers")
        return violations
    source = juju.get("source")
    if not source or _unquote(source) != "juju/juju":
        violations.append('terraform.tf: juju provider source must be "juju/juju"')
    version = juju.get("version")
    if not version:
        violations.append("terraform.tf: juju provider is missing a version constraint")
    elif ">= 1.0" not in re.sub(r"\s+", " ", _unquote(version)):
        violations.append("terraform.tf: juju provider version must allow >= 1.0")
    return violations


def check_alphabetical(parsed: dict, block_type: str, filename: str) -> list[str]:
    """Return a violation if blocks are not ordered alphabetically."""
    names = block_names(parsed, block_type)
    if names != sorted(names):
        return [
            (
                f"{filename}: {block_type} blocks are not alphabetical: "
                f"found {names}, expected {sorted(names)}"
            )
        ]
    return []


def is_product_module(parsed_files: list[dict]) -> bool:
    """Return True when any parsed file composes other modules."""
    return any(parsed.get("module") for parsed in parsed_files)


def check_interface(variables: list[str], outputs: list[str], product: bool) -> list[str]:
    """Return violations for mandatory variables and outputs."""
    violations: list[str] = []
    if product:
        for output in MANDATORY_PRODUCT_OUTPUTS:
            if output not in outputs:
                violations.append(f"product module missing mandatory output: {output}")
        return violations
    for variable in MANDATORY_CHARM_VARIABLES:
        if variable not in variables:
            violations.append(f"charm module missing mandatory variable: {variable}")
    for output in MANDATORY_CHARM_OUTPUTS:
        if output not in outputs:
            violations.append(f"charm module missing mandatory output: {output}")
    return violations


def check_pinned_module_sources(parsed_files: list[dict]) -> list[str]:
    """Return violations for module sources not pinned to a tag or commit."""
    violations: list[str] = []
    for parsed in parsed_files:
        for block in parsed.get("module", []):
            key = next(name for name in block if name != "__is_block__")
            body = block[key]
            raw_source = body.get("source")
            if not raw_source:
                continue
            source = _unquote(raw_source)
            if source.startswith(("./", "../")):
                continue
            name = _unquote(key)
            ref_match = re.search(r'[?&]ref=([^&"]+)', source)
            if ref_match is None:
                if not body.get("version"):
                    violations.append(
                        f'module "{name}": source must be pinned with ?ref=<tag|commit> '
                        "or a registry version"
                    )
            elif not _REF_PATTERN.match(ref_match.group(1)):
                violations.append(
                    f'module "{name}": ref "{ref_match.group(1)}" is not a tag or commit '
                    "(floating references are not allowed)"
                )
    return violations


def _load(path: Path) -> dict:
    """Parse a Terraform file with python-hcl2."""
    with path.open(encoding="utf-8") as handle:
        return hcl2.load(handle)


def check_module(module_dir: Path) -> list[str]:
    """Return all CC008 violations for a single Terraform module directory."""
    violations = check_required_files(module_dir)
    parsed = {path.name: _load(path) for path in module_dir.glob("*.tf")}
    parsed_files = list(parsed.values())

    if "terraform.tf" in parsed:
        violations += check_terraform_block(parsed["terraform.tf"])
    if "variables.tf" in parsed:
        violations += check_alphabetical(parsed["variables.tf"], "variable", "variables.tf")
    if "outputs.tf" in parsed:
        violations += check_alphabetical(parsed["outputs.tf"], "output", "outputs.tf")

    variables = [name for file in parsed_files for name in block_names(file, "variable")]
    outputs = [name for file in parsed_files for name in block_names(file, "output")]
    violations += check_interface(variables, outputs, is_product_module(parsed_files))
    violations += check_pinned_module_sources(parsed_files)
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the CC008 compliance check over the given module directories."""
    parser = argparse.ArgumentParser(description="Check Terraform modules for CC008 compliance.")
    parser.add_argument("directories", nargs="+", help="Terraform module directories to check.")
    args = parser.parse_args(argv)

    failed = False
    for directory in args.directories:
        violations = check_module(Path(directory))
        if violations:
            failed = True
            print(f"FAIL {directory}")
            for violation in violations:
                print(f"  - {violation}")
        else:
            print(f"PASS {directory}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
