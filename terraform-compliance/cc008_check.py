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
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import hcl2

REQUIRED_FILES = ("terraform.tf", "variables.tf", "outputs.tf", "main.tf", "README.md")


class ModuleType(str, Enum):
    """The CC008 module categories this checker distinguishes."""

    CHARM = "charm"
    COMPONENT = "component"
    PRODUCT = "product"


@dataclass(frozen=True)
class MandatoryInterface:
    """The mandatory variables and outputs a CC008 module type must declare."""

    variables: tuple[str, ...]
    outputs: tuple[str, ...]


# Single source of truth for CC008's mandatory interface per module type. Add
# a new ModuleType member and an entry here to support another module kind.
MANDATORY_INTERFACES: dict[ModuleType, MandatoryInterface] = {
    ModuleType.CHARM: MandatoryInterface(
        variables=(
            "app_name",
            "channel",
            "config",
            "constraints",
            "model_uuid",
            "revision",
            "units",
        ),
        outputs=("application", "provides", "requires"),
    ),
    ModuleType.COMPONENT: MandatoryInterface(
        variables=("model_uuid",),
        outputs=("components",),
    ),
    ModuleType.PRODUCT: MandatoryInterface(
        variables=("logging-config", "proxy", "risk"),
        outputs=("metadata", "models"),
    ),
}


_FLOATING_REF_NAMES = frozenset(
    {"main", "master", "trunk", "develop", "development", "head"}
)


@dataclass(frozen=True)
class CheckResult:
    """Result of one category of CC008 checks."""

    slug: str
    name: str
    violations: tuple[str, ...]
    skip_reason: str | None = None


CHECK_SLUGS = (
    "required-files",
    "terraform-configuration",
    "variable-ordering",
    "output-ordering",
    "module-interface",
    "module-sources",
)


@dataclass(frozen=True)
class ModuleReport:
    """Detailed CC008 report for one Terraform module."""

    module_type: ModuleType
    checks: tuple[CheckResult, ...]
    variables: tuple[str, ...]
    outputs: tuple[str, ...]
    sources: tuple[str, ...]

    @property
    def violations(self) -> list[str]:
        """Return all violations across check categories."""
        return [violation for check in self.checks for violation in check.violations]


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
    if not module_dir.exists():
        return [f"module directory does not exist: {module_dir}"]
    if not module_dir.is_dir():
        return [f"module path is not a directory: {module_dir}"]
    return [
        f"missing required file: {name}"
        for name in REQUIRED_FILES
        if not (module_dir / name).exists()
    ]


# Matches one constraint clause, e.g. ">= 1.0", "> 1.0.0", "~> 1.12", "1.0.0".
_CONSTRAINT_PATTERN = re.compile(
    r"^(~>|>=|>|=|!=|<=|<)?\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?$"
)


def _allows_juju_v1_or_above(constraint: str) -> bool:
    """Return True if a version constraint string permits juju provider >= 1.0.0.

    Handles comma-separated constraint lists (e.g. ">= 1.0, < 3.0") by checking
    whether any clause establishes a lower bound at or above 1.0.0. A
    constraint with only an upper bound (e.g. "< 3.0") does not guarantee
    >= 1.0.0 and is therefore rejected.
    """
    for clause in constraint.split(","):
        match = _CONSTRAINT_PATTERN.match(clause.strip())
        if not match:
            continue
        operator, major, minor, patch = match.groups()
        version = (int(major), int(minor or 0), int(patch or 0))
        if operator in (None, ">=", ">", "=", "~>") and version >= (1, 0, 0):
            return True
    return False


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
    elif not _allows_juju_v1_or_above(_unquote(version)):
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


def is_composed_module(parsed_files: list[dict]) -> bool:
    """Return True when any parsed file composes other modules."""
    return any(parsed.get("module") for parsed in parsed_files)


def _resource_type_labels(parsed_files: list[dict], block_type: str) -> list[str]:
    """Return the resource/data type label of every block of a given type.

    ``resource``/``data`` blocks have two labels (type, name); python-hcl2
    represents each as a single-key dict ``{type: {name: body}}``, so the
    single key at this level is the resource/data type.
    """
    return [
        _unquote(next(iter(block)))
        for parsed in parsed_files
        for block in parsed.get(block_type, [])
    ]


# Per CC008, Product modules "contain the definition of the various resources
# required to tie components and charm modules together (e.g. juju models,
# juju secrets, integrations, etc)". A Product module may not create the
# model itself (it can just take model_uuid as an input, per CC008's own
# "create or consume a model" wording), so juju_model alone is not a reliable
# signal; any of these tying resource/data types is treated as one.
_PRODUCT_TYING_RESOURCE_TYPES = frozenset(
    {"juju_model", "juju_secret", "juju_integration", "juju_offer"}
)


def _defines_tying_resources(parsed_files: list[dict]) -> bool:
    """Return True if any file declares a Product-module tying resource/data block."""
    return any(
        label in _PRODUCT_TYING_RESOURCE_TYPES
        for block_type in ("resource", "data")
        for label in _resource_type_labels(parsed_files, block_type)
    )


def classify_module_type(parsed_files: list[dict]) -> ModuleType:
    """Classify a module as CHARM, COMPONENT, or PRODUCT.

    A module with no ``module`` blocks is a charm module. A module that
    composes other modules is a product module if it also defines at least
    one resource/data block that ties components together (juju_model,
    juju_secret, juju_integration, juju_offer); otherwise it is a component
    module (bundles charm modules without any such tying resources).
    """
    if not is_composed_module(parsed_files):
        return ModuleType.CHARM
    if _defines_tying_resources(parsed_files):
        return ModuleType.PRODUCT
    return ModuleType.COMPONENT


def check_interface(
    variables: list[str], outputs: list[str], module_type: ModuleType
) -> list[str]:
    """Return violations for mandatory variables and outputs."""
    interface = MANDATORY_INTERFACES[module_type]
    violations: list[str] = []
    for variable in interface.variables:
        if variable not in variables:
            violations.append(
                f"{module_type} module missing mandatory variable: {variable}"
            )
    for output in interface.outputs:
        if output not in outputs:
            violations.append(f"{module_type} module missing mandatory output: {output}")
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
            elif ref_match.group(1).lower() in _FLOATING_REF_NAMES:
                violations.append(
                    f'module "{name}": ref "{ref_match.group(1)}" looks like a branch name, '
                    "not a pinned tag or commit (floating references are not allowed)"
                )
    return violations


def _load(path: Path) -> dict:
    """Parse a Terraform file with python-hcl2."""
    with path.open(encoding="utf-8") as handle:
        return hcl2.load(handle)


def _module_sources(parsed_files: list[dict]) -> list[str]:
    """Return source values discovered in module blocks."""
    sources: list[str] = []
    for parsed in parsed_files:
        for block in parsed.get("module", []):
            key = next(name for name in block if name != "__is_block__")
            source = block[key].get("source")
            if source:
                sources.append(_unquote(source))
    return sources


def inspect_module(module_dir: Path) -> ModuleReport:
    """Return a detailed CC008 report for a Terraform module directory."""
    parsed = {path.name: _load(path) for path in module_dir.glob("*.tf")}
    parsed_files = list(parsed.values())
    variables = [
        name for file in parsed_files for name in block_names(file, "variable")
    ]
    outputs = [name for file in parsed_files for name in block_names(file, "output")]
    module_type = classify_module_type(parsed_files)

    checks = (
        CheckResult(
            "required-files", "Required files", tuple(check_required_files(module_dir))
        ),
        CheckResult(
            "terraform-configuration",
            "Terraform configuration",
            tuple(check_terraform_block(parsed["terraform.tf"]))
            if "terraform.tf" in parsed
            else (),
            None if "terraform.tf" in parsed else "terraform.tf is missing",
        ),
        CheckResult(
            "variable-ordering",
            "Variable ordering",
            tuple(
                check_alphabetical(parsed["variables.tf"], "variable", "variables.tf")
            )
            if "variables.tf" in parsed
            else (),
            None if "variables.tf" in parsed else "variables.tf is missing",
        ),
        CheckResult(
            "output-ordering",
            "Output ordering",
            tuple(check_alphabetical(parsed["outputs.tf"], "output", "outputs.tf"))
            if "outputs.tf" in parsed
            else (),
            None if "outputs.tf" in parsed else "outputs.tf is missing",
        ),
        CheckResult(
            "module-interface",
            "Module interface",
            tuple(check_interface(variables, outputs, module_type)),
        ),
        CheckResult(
            "module-sources",
            "Module sources",
            tuple(check_pinned_module_sources(parsed_files)),
        ),
    )
    return ModuleReport(
        module_type=module_type,
        checks=checks,
        variables=tuple(variables),
        outputs=tuple(outputs),
        sources=tuple(_module_sources(parsed_files)),
    )


def check_module(module_dir: Path) -> list[str]:
    """Return all CC008 violations for a single Terraform module directory."""
    return inspect_module(module_dir).violations


def _emit_github_error(module: str, violation: str) -> None:
    """Emit a GitHub Actions error annotation for a violation."""
    message = f"{module}: {violation}".replace("%", "%25").replace("\r", "%0D")
    print(f"::error title=CC008 compliance::{message.replace(chr(10), '%0A')}")


def main(argv: list[str] | None = None) -> int:
    """Run the CC008 compliance check over the given module directories."""
    parser = argparse.ArgumentParser(
        description="Check Terraform modules for CC008 compliance."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show variables, outputs, and module sources discovered during parsing.",
    )
    parser.add_argument(
        "--check",
        choices=CHECK_SLUGS,
        help="Run only this check category (see --list-checks). Runs all categories if omitted.",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="Print the available --check slugs and exit.",
    )
    parser.add_argument(
        "directories", nargs="*", help="Terraform module directories to check."
    )
    args = parser.parse_args(argv)

    if args.list_checks:
        for slug in CHECK_SLUGS:
            print(slug)
        return 0

    directories = [directory for directory in args.directories if directory.strip()]

    if not directories:
        message = "no Terraform module directories were provided"
        print(f"ERROR: {message}")
        print(f"::error title=CC008 configuration::{message}")
        return 2

    label = f"check '{args.check}'" if args.check else "all checks"
    print(
        f"Checking {len(directories)} Terraform module(s) for CC008 compliance ({label})"
    )
    failed_count = 0
    for directory in directories:
        report = inspect_module(Path(directory))
        checks = (
            [check for check in report.checks if check.slug == args.check]
            if args.check
            else report.checks
        )
        module_violations = [
            violation for check in checks for violation in check.violations
        ]
        print(f"\nChecking {directory} ({report.module_type} module)")
        if args.verbose:
            print(f"  Variables: {', '.join(report.variables) or 'none'}")
            print(f"  Outputs: {', '.join(report.outputs) or 'none'}")
            print(f"  Module sources: {', '.join(report.sources) or 'none'}")
        for check in checks:
            if check.skip_reason:
                print(f"  SKIP {check.name} ({check.skip_reason})")
                continue
            print(f"  {'FAIL' if check.violations else 'PASS'} {check.name}")
            for violation in check.violations:
                print(f"  - {violation}")
                _emit_github_error(directory, violation)
        if module_violations:
            failed_count += 1
            print(f"FAIL {directory}")
        else:
            print(f"PASS {directory}")

    passed_count = len(directories) - failed_count
    print(
        f"\nSummary: {len(directories)} checked, "
        f"{passed_count} passed, {failed_count} failed"
    )
    return 1 if failed_count else 0


if __name__ == "__main__":
    sys.exit(main())
