# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Generic Terraform module compliance checker (the *how*; rules live in terraform_spec).

Every check function takes an explicit ``spec`` argument (defaulting to
``DEFAULT_SPEC``), so this module has no hardcoded dependency on any
particular standard, including CC008.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from terraform_hcl import (
    block_body,
    block_label,
    block_names,
    load_module_files,
    module_sources,
    output_bodies,
    terraform_type,
    unquote,
    variable_bodies,
)
from terraform_spec import (
    DEFAULT_FORBIDDEN,
    DEFAULT_SPEC,
    DEFAULT_UNCHECKED,
    ModuleSpec,
    ModuleType,
    VariableRule,
)


@dataclass(frozen=True)
class CheckResult:
    """Result of one category of compliance checks."""

    slug: str
    name: str
    violations: tuple[str, ...]
    skip_reason: str | None = None


CHECK_SLUGS = (
    "required-files",
    "module-type",
    "terraform-configuration",
    "variable-ordering",
    "output-ordering",
    "module-interface",
    "module-sources",
)


@dataclass(frozen=True)
class ModuleReport:
    """Detailed compliance report for one Terraform module."""

    module_type: ModuleType | None
    checks: tuple[CheckResult, ...]
    variables: tuple[str, ...]
    outputs: tuple[str, ...]
    sources: tuple[str, ...]

    @property
    def violations(self) -> list[str]:
        """Return all violations across check categories."""
        return [violation for check in self.checks for violation in check.violations]


def check_required_files(
    module_dir: Path, spec: ModuleSpec = DEFAULT_SPEC
) -> list[str]:
    """Return violations for any missing required module file."""
    if not module_dir.exists():
        return [f"module directory does not exist: {module_dir}"]
    if not module_dir.is_dir():
        return [f"module path is not a directory: {module_dir}"]
    return [
        f"missing required file: {name}"
        for name in spec.required_files
        if not (module_dir / name).exists()
    ]


# Matches one constraint clause, e.g. ">= 1.0", "> 1.0.0", "~> 1.12", "1.0.0".
_CONSTRAINT_PATTERN = re.compile(
    r"^(~>|>=|>|=|!=|<=|<)?\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?$"
)


def _allows_minimum_version(constraint: str, minimum: str) -> bool:
    """True if the version constraint permits at least the minimum version.

    A constraint with only an upper bound (e.g. "< 3.0") is rejected.
    """
    minimum_match = _CONSTRAINT_PATTERN.match(minimum)
    if minimum_match is None:
        return False
    _, min_major, min_minor, min_patch = minimum_match.groups()
    minimum_version = (int(min_major), int(min_minor or 0), int(min_patch or 0))
    for clause in constraint.split(","):
        match = _CONSTRAINT_PATTERN.match(clause.strip())
        if not match:
            continue
        operator, major, minor, patch = match.groups()
        version = (int(major), int(minor or 0), int(patch or 0))
        if operator in (None, ">=", ">", "=", "~>") and version >= minimum_version:
            return True
    return False


def check_terraform_block(parsed: dict, spec: ModuleSpec = DEFAULT_SPEC) -> list[str]:
    """Return violations for the required_version and juju provider."""
    blocks = parsed.get("terraform", [])
    if not blocks:
        return ["terraform.tf: missing terraform block"]
    block = blocks[0]
    violations: list[str] = []
    if len(blocks) != 1:
        violations.append(
            f"terraform.tf: expected exactly one terraform block, found {len(blocks)}"
        )
    if not block.get("required_version"):
        violations.append("terraform.tf: missing required_version")
    providers = block.get("required_providers")
    if isinstance(providers, list):
        providers = providers[0] if providers else {}
    juju = (providers or {}).get("juju")
    if not juju:
        violations.append("terraform.tf: missing juju provider in required_providers")
        return violations
    requirements = spec.terraform_block
    source = juju.get("source")
    if not source or unquote(source) != requirements.provider_source:
        violations.append(
            f'terraform.tf: juju provider source must be "{requirements.provider_source}"'
        )
    version = juju.get("version")
    if not version:
        violations.append("terraform.tf: juju provider is missing a version constraint")
    elif not _allows_minimum_version(
        unquote(version), requirements.minimum_provider_version
    ):
        violations.append(
            "terraform.tf: juju provider version must allow >= "
            f"{requirements.minimum_provider_version}"
        )
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


UNIDENTIFIED_MODULE_TYPE_MESSAGE = (
    "module type is not identified: the module must either have a path element "
    "containing 'product', 'component' or 'charm', or have an outputs.tf "
    "containing '{product}' (product module), '{component}' (component module) "
    "or '{charm}' (charm module)"
)


def _path_names_type(module_type: ModuleType, lowered_parts: list[str]) -> bool:
    """Return True if a path element names the module type.

    "charm" must be a whole word so that e.g. "charmed-spark" is not a charm.
    """
    if module_type == ModuleType.CHARM:
        words = [word for part in lowered_parts for word in re.split(r"[-_.]", part)]
        return any(word in (ModuleType.CHARM, f"{ModuleType.CHARM}s") for word in words)
    return any(module_type in part for part in lowered_parts)


def _type_from_path(path_parts: tuple[str, ...]) -> ModuleType | None:
    """Return the type named by the path elements, None if absent or ambiguous."""
    lowered = [part.lower() for part in path_parts]
    named_types = [kind for kind in ModuleType if _path_names_type(kind, lowered)]
    return named_types[0] if len(named_types) == 1 else None


def _type_from_outputs(outputs_text: str, spec: ModuleSpec) -> ModuleType | None:
    """Return the type implied by markers in the outputs.tf text, if any."""
    if spec.product_output_marker in outputs_text:
        return ModuleType.PRODUCT
    if spec.component_output_marker in outputs_text:
        return ModuleType.COMPONENT
    if spec.charm_output_marker in outputs_text:
        return ModuleType.CHARM
    return None


def classify_module_type(
    module_dir: Path,
    spec: ModuleSpec = DEFAULT_SPEC,
    root: Path | None = None,
) -> ModuleType | None:
    """Classify a module, or return None when its type cannot be identified.

    The type comes from the path (relative to ``root`` when given) containing
    "product", "component" or "charm", then from the markers in outputs.tf.
    """
    relative_dir = module_dir.relative_to(root) if root else module_dir
    path_type = _type_from_path(relative_dir.parts)
    if path_type:
        return path_type
    outputs_file = module_dir / "outputs.tf"
    outputs_text = outputs_file.read_text() if outputs_file.is_file() else ""
    return _type_from_outputs(outputs_text, spec)


def _check_variable_rule(
    rule: VariableRule, body: dict, module_type: ModuleType
) -> list[str]:
    """Return violations for one variable's type/required/default rules."""
    violations: list[str] = []
    prefix = f'{module_type} module variable "{rule.name}"'

    declared_type = body.get("type")
    if rule.allowed_type is not None and not isinstance(declared_type, str):
        violations.append(f"{prefix}: missing type declaration")
    elif rule.allowed_type is not None:
        declared_terraform_type = terraform_type(declared_type)
        if declared_terraform_type != rule.allowed_type:
            violations.append(
                f"{prefix}: expected type {rule.allowed_type}, "
                f"found {declared_terraform_type or unquote(declared_type)}"
            )

    has_default = "default" in body
    if rule.default is DEFAULT_FORBIDDEN and has_default:
        violations.append(
            f"{prefix}: must not declare a default (this variable is required)"
        )
    elif (
        rule.default is not DEFAULT_UNCHECKED
        and has_default
        and body["default"] != rule.default
    ):
        violations.append(
            f"{prefix}: default must be {rule.default!r}, found {body['default']!r}"
        )
    if rule.nullable is not None and body.get("nullable", True) is not rule.nullable:
        violations.append(f"{prefix}: nullable must be {str(rule.nullable).lower()}")
    return violations


def check_interface(
    variables: dict[str, dict],
    outputs: list[str],
    module_type: ModuleType,
    spec: ModuleSpec = DEFAULT_SPEC,
) -> list[str]:
    """Return violations for mandatory/optional variables and outputs.

    ``variables`` maps name to parsed body (see ``variable_bodies``).
    """
    interface = spec.module_interfaces[module_type]
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
    # The spec allows arbitrary extra variables/outputs, but retired names
    # (e.g. endpoints, split into provides/requires under CC008) must not be used.
    violations.extend(
        f"{module_type} module declares deprecated variable: {name}"
        for name in variables
        if name in spec.deprecated_names
    )
    violations.extend(
        f"{module_type} module declares deprecated output: {name}"
        for name in outputs
        if name in spec.deprecated_names
    )
    return violations


def check_output_shapes(
    parsed_files: list[dict],
    module_type: ModuleType,
    spec: ModuleSpec = DEFAULT_SPEC,
) -> list[str]:
    """Return violations for output value shapes that can be checked statically."""
    outputs = output_bodies(parsed_files)
    violations: list[str] = []
    for rule in spec.module_interfaces[module_type].outputs:
        if rule.name not in outputs:
            continue
        value = outputs[rule.name].get("value")
        if rule.expected_resource_type is not None:
            resource_reference = re.compile(
                rf"^\$\{{{re.escape(rule.expected_resource_type)}\.[^.}}]+\}}$"
            )
            if not isinstance(value, str) or not resource_reference.fullmatch(value):
                violations.append(
                    f'{module_type} module output "{rule.name}": must reference a '
                    f"complete {rule.expected_resource_type} resource"
                )
        if rule.literal_map_entry_fields and isinstance(value, dict):
            required_fields = set(rule.literal_map_entry_fields)
            for entry_name, entry in value.items():
                if (
                    isinstance(entry, str)
                    and entry.startswith("${")
                    and entry.endswith("}")
                ):
                    continue
                if not isinstance(entry, dict) or not required_fields.issubset(entry):
                    fields = ", ".join(rule.literal_map_entry_fields)
                    violations.append(
                        f'{module_type} module output "{rule.name}" entry '
                        f'"{entry_name}": must be an object containing {fields}'
                    )
        if rule.required_keys and isinstance(value, dict):
            missing_keys = [key for key in rule.required_keys if key not in value]
            extra_keys = (
                [key for key in value if key not in rule.required_keys]
                if not rule.allow_extra_keys
                else []
            )
            if missing_keys or extra_keys:
                fields = ", ".join(rule.required_keys)
                qualifier = (
                    "containing" if rule.allow_extra_keys else "containing exactly"
                )
                violations.append(
                    f'{module_type} module output "{rule.name}": must be an object '
                    f"{qualifier} {fields}"
                )
    return violations


def _is_vcs_or_url_source(source: str) -> bool:
    """True if a module source is a VCS/URL source rather than a registry one."""
    _VCS_OR_URL_SOURCE_PATTERN = re.compile(
        r"^git::"
        r"|^git@"
        r"|^\w+://"
        r"|^github\.com/"
    )
    return _VCS_OR_URL_SOURCE_PATTERN.search(source) is not None


def check_pinned_module_sources(
    parsed_files: list[dict], spec: ModuleSpec = DEFAULT_SPEC
) -> list[str]:
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
                elif ref_match.group(1).lower() in spec.floating_ref_names:
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
            elif ref_match.group(1).lower() in spec.floating_ref_names:
                violations.append(
                    f'module "{name}": ref "{ref_match.group(1)}" looks like a '
                    "branch name, not a pinned tag or commit (floating "
                    "references are not allowed)"
                )
    return violations


def inspect_module(
    module_dir: Path, spec: ModuleSpec = DEFAULT_SPEC, root: Path | None = None
) -> ModuleReport:
    """Return a detailed compliance report for a Terraform module directory."""
    parsed = load_module_files(module_dir)
    parsed_files = list(parsed.values())
    variable_bodies_by_name = variable_bodies(parsed_files)
    variables = list(variable_bodies_by_name)
    outputs = [name for file in parsed_files for name in block_names(file, "output")]
    module_type = classify_module_type(module_dir, spec, root)

    checks = (
        CheckResult(
            "required-files",
            "Required files",
            tuple(check_required_files(module_dir, spec)),
        ),
        CheckResult(
            "module-type",
            "Module type",
            ()
            if module_type
            else (
                UNIDENTIFIED_MODULE_TYPE_MESSAGE.format(
                    product=spec.product_output_marker,
                    component=spec.component_output_marker,
                    charm=spec.charm_output_marker,
                ),
            ),
        ),
        CheckResult(
            "terraform-configuration",
            "Terraform configuration",
            tuple(check_terraform_block(parsed["terraform.tf"], spec))
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
            tuple(
                check_interface(variable_bodies_by_name, outputs, module_type, spec)
                + check_output_shapes(parsed_files, module_type, spec)
            )
            if module_type
            else (),
            None if module_type else "module type is not identified",
        ),
        CheckResult(
            "module-sources",
            "Module sources",
            tuple(check_pinned_module_sources(parsed_files, spec)),
        ),
    )
    return ModuleReport(
        module_type=module_type,
        checks=checks,
        variables=tuple(variables),
        outputs=tuple(outputs),
        sources=tuple(module_sources(parsed_files)),
    )


def check_module(
    module_dir: Path, spec: ModuleSpec = DEFAULT_SPEC, root: Path | None = None
) -> list[str]:
    """Return all violations for a single Terraform module directory."""
    return inspect_module(module_dir, spec, root).violations


def _escape_annotation(message: str) -> str:
    """Escape a message for use in a GitHub Actions ``::error`` annotation."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(argv: list[str] | None = None) -> int:
    """Run the Terraform module compliance check over the given directories."""
    parser = argparse.ArgumentParser(
        description="Check Terraform modules for compliance with the configured spec."
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
        "--root",
        type=Path,
        help=(
            "Repository root; module paths are made relative to it when "
            "identifying module types (defaults to the paths as given)."
        ),
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
        print(
            f"::error title=Terraform compliance configuration::{_escape_annotation(message)}"
        )
        return 2

    label = f"check '{args.check}'" if args.check else "all checks"
    print(f"Checking {len(directories)} Terraform module(s) for compliance ({label})")
    failed_count = 0
    for directory in directories:
        report = inspect_module(Path(directory), root=args.root)
        checks = (
            [check for check in report.checks if check.slug == args.check]
            if args.check
            else report.checks
        )
        module_violations = [
            violation for check in checks for violation in check.violations
        ]
        print(f"\nChecking {directory} ({report.module_type or 'unidentified'} module)")
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
                print(f"::error title=Terraform compliance::{annotation}")
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
