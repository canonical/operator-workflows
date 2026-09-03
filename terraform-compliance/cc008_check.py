# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CC008 Terraform module compliance checker (the *how*; rules live in cc008_spec)."""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from cc008_spec import (
    CC008_SPEC,
    NO_DEFAULT_CHECK,
    ModuleType,
    VariableRule,
)
from terraform_hcl import (
    block_body,
    block_label,
    block_names,
    load_module_files,
    module_sources,
    resource_type_labels,
    type_family,
    unquote,
    variable_bodies,
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


def check_required_files(module_dir: Path) -> list[str]:
    """Return violations for any missing required module file."""
    if not module_dir.exists():
        return [f"module directory does not exist: {module_dir}"]
    if not module_dir.is_dir():
        return [f"module path is not a directory: {module_dir}"]
    return [
        f"missing required file: {name}"
        for name in CC008_SPEC.required_files
        if not (module_dir / name).exists()
    ]


# Matches one constraint clause, e.g. ">= 1.0", "> 1.0.0", "~> 1.12", "1.0.0".
_CONSTRAINT_PATTERN = re.compile(
    r"^(~>|>=|>|=|!=|<=|<)?\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?$"
)


def _allows_juju_v1_or_above(constraint: str) -> bool:
    """True if the version constraint permits juju provider >= 1.0.0.

    A constraint with only an upper bound (e.g. "< 3.0") is rejected.
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
    requirements = CC008_SPEC.terraform_block
    source = juju.get("source")
    if not source or unquote(source) != requirements.provider_source:
        violations.append(
            f'terraform.tf: juju provider source must be "{requirements.provider_source}"'
        )
    version = juju.get("version")
    if not version:
        violations.append("terraform.tf: juju provider is missing a version constraint")
    elif not _allows_juju_v1_or_above(unquote(version)):
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


def _defines_tying_resources(parsed_files: list[dict]) -> bool:
    """Return True if any file declares a Product-module tying resource/data block."""
    return any(
        label in CC008_SPEC.tying_resource_types
        for block_type in ("resource", "data")
        for label in resource_type_labels(parsed_files, block_type)
    )


def classify_module_type(parsed_files: list[dict]) -> ModuleType:
    """Classify a module as CHARM (no module blocks), PRODUCT (composes
    modules and defines a tying resource), or COMPONENT (composes only).
    """
    if not is_composed_module(parsed_files):
        return ModuleType.CHARM
    if _defines_tying_resources(parsed_files):
        return ModuleType.PRODUCT
    return ModuleType.COMPONENT


def _check_variable_rule(
    rule: VariableRule, body: dict, module_type: ModuleType
) -> list[str]:
    """Return violations for one variable's type/required/default rules."""
    violations: list[str] = []
    prefix = f'{module_type} module variable "{rule.name}"'

    declared_type = body.get("type")
    if rule.type_family is not None and declared_type is not None:
        family = type_family(declared_type)
        if family is not None and family != rule.type_family:
            violations.append(
                f"{prefix}: expected a {rule.type_family.value}-like type, "
                f"found {unquote(declared_type)}"
            )

    has_default = "default" in body
    if rule.required and has_default:
        violations.append(f"{prefix}: must not declare a default (this variable is required)")
    elif rule.default is not NO_DEFAULT_CHECK and has_default and body["default"] != rule.default:
        violations.append(
            f"{prefix}: default must be {rule.default!r}, found {body['default']!r}"
        )
    return violations


def check_interface(
    variables: dict[str, dict], outputs: list[str], module_type: ModuleType
) -> list[str]:
    """Return violations for mandatory/optional variables and outputs.

    ``variables`` maps name to parsed body (see ``variable_bodies``).
    """
    interface = CC008_SPEC.module_interfaces[module_type]
    violations: list[str] = []
    for rule in interface.variables:
        if rule.name not in variables:
            if rule.optional:
                continue
            violations.append(
                f"{module_type} module missing mandatory variable: {rule.name}"
            )
            continue
        violations.extend(_check_variable_rule(rule, variables[rule.name], module_type))
    for output in interface.outputs:
        if output.name not in outputs and not output.optional:
            violations.append(
                f"{module_type} module missing mandatory output: {output.name}"
            )
    if interface.strict_variables:
        known = {rule.name for rule in interface.variables}
        violations.extend(
            f"{module_type} module declares unexpected variable: {name}"
            for name in variables
            if name not in known
        )
    if interface.strict_outputs:
        known = {output.name for output in interface.outputs}
        violations.extend(
            f"{module_type} module declares unexpected output: {name}"
            for name in outputs
            if name not in known
        )
    return violations


# Terraform source addresses that are VCS/URL (not registry) sources. `version`
# only applies to registry sources, so these must be pinned with an explicit ref.
_VCS_OR_URL_SOURCE_PATTERN = re.compile(
    r"^(?:git|hg|s3|gcs)::"  # forced source type, e.g. git::https://...
    r"|^git@"                # scp-style git, e.g. git@github.com:org/repo.git
    r"|^\w+://"              # any URL scheme, e.g. https://, ssh://
    r"|^github\.com/"        # GitHub shorthand
)


def _is_vcs_or_url_source(source: str) -> bool:
    """True if a module source is a VCS/URL source rather than a registry one."""
    return _VCS_OR_URL_SOURCE_PATTERN.search(source) is not None


def check_pinned_module_sources(parsed_files: list[dict]) -> list[str]:
    """Return violations for module sources not pinned to a tag or commit."""
    violations: list[str] = []
    for parsed in parsed_files:
        for block in parsed.get("module", []):
            body = block_body(block)
            raw_source = body.get("source")
            if not raw_source:
                continue
            source = unquote(raw_source)
            if source.startswith(("./", "../")):
                continue
            name = unquote(block_label(block))
            ref_match = re.search(r'[?&]ref=([^&"]+)', source)
            if _is_vcs_or_url_source(source):
                if ref_match is None:
                    violations.append(
                        f'module "{name}": source must be pinned with ?ref=<tag|commit>'
                    )
                elif ref_match.group(1).lower() in CC008_SPEC.floating_ref_names:
                    violations.append(
                        f'module "{name}": ref "{ref_match.group(1)}" looks like a '
                        "branch name, not a pinned tag or commit (floating "
                        "references are not allowed)"
                    )
            elif ref_match is None:
                if not body.get("version"):
                    violations.append(
                        f'module "{name}": source must be pinned with a registry version'
                    )
            elif ref_match.group(1).lower() in CC008_SPEC.floating_ref_names:
                violations.append(
                    f'module "{name}": ref "{ref_match.group(1)}" looks like a '
                    "branch name, not a pinned tag or commit (floating "
                    "references are not allowed)"
                )
    return violations


def inspect_module(module_dir: Path) -> ModuleReport:
    """Return a detailed CC008 report for a Terraform module directory."""
    parsed = load_module_files(module_dir)
    parsed_files = list(parsed.values())
    variable_bodies_by_name = variable_bodies(parsed_files)
    variables = list(variable_bodies_by_name)
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
            tuple(check_interface(variable_bodies_by_name, outputs, module_type)),
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
        sources=tuple(module_sources(parsed_files)),
    )


def check_module(module_dir: Path) -> list[str]:
    """Return all CC008 violations for a single Terraform module directory."""
    return inspect_module(module_dir).violations


def _escape_annotation(message: str) -> str:
    """Escape a message for use in a GitHub Actions ``::error`` annotation."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


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
        print(f"::error title=CC008 configuration::{_escape_annotation(message)}")
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
                annotation = _escape_annotation(f"{directory}: {violation}")
                print(f"::error title=CC008 compliance::{annotation}")
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
