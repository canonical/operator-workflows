# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CC008 Terraform module requirements, as data.

Single source of truth for *what* CC008 requires; cc008_check.py holds the
*how*. No checking logic here.
"""

from dataclasses import dataclass
from enum import StrEnum

from terraform_hcl import TypeFamily


class ModuleType(StrEnum):
    """CC008 module categories this checker distinguishes."""

    CHARM = "charm"
    COMPONENT = "component"
    PRODUCT = "product"


class _NoDefaultCheck:
    """Sentinel: don't check the default value (readable repr)."""

    def __repr__(self) -> str:
        return "NO_DEFAULT_CHECK"


# `None` is a valid Terraform default, so it can't double as "no opinion".
NO_DEFAULT_CHECK = _NoDefaultCheck()


@dataclass(frozen=True)
class VariableRule:
    """One CC008 variable requirement."""

    name: str
    type_family: TypeFamily | None = None
    required: bool = False  # must declare no `default`
    default: object = NO_DEFAULT_CHECK  # default must equal this, if declared
    optional: bool = False  # may be absent; if present, still validated


@dataclass(frozen=True)
class OutputRule:
    """One CC008 output requirement (presence only; outputs have no type)."""

    name: str
    optional: bool = False


@dataclass(frozen=True)
class ModuleInterface:
    """Mandatory/optional variables and outputs for a module type."""

    variables: tuple[VariableRule, ...]
    outputs: tuple[OutputRule, ...]


@dataclass(frozen=True)
class TerraformBlockRequirements:
    """Required `terraform.tf` provider settings."""

    provider_source: str
    minimum_provider_version: str


@dataclass(frozen=True)
class CC008Spec:
    """The full set of CC008 requirements this checker enforces."""

    required_files: tuple[str, ...]
    terraform_block: TerraformBlockRequirements
    tying_resource_types: frozenset[str]
    floating_ref_names: frozenset[str]
    module_interfaces: dict[ModuleType, ModuleInterface]


CC008_SPEC = CC008Spec(
    required_files=(
        "terraform.tf",
        "variables.tf",
        "outputs.tf",
        "main.tf",
        "README.md",
    ),
    terraform_block=TerraformBlockRequirements(
        provider_source="juju/juju",
        minimum_provider_version="1.0.0",
    ),
    # Resource/data types that mark a module as tying components together.
    tying_resource_types=frozenset(
        {"juju_model", "juju_secret", "juju_integration", "juju_offer"}
    ),
    # Floating branch names disallowed as module refs.
    floating_ref_names=frozenset(
        {"main", "master", "trunk", "develop", "development", "head"}
    ),
    module_interfaces={
        ModuleType.CHARM: ModuleInterface(
            variables=(
                VariableRule("app_name", TypeFamily.STRING),
                VariableRule("channel", TypeFamily.STRING),
                VariableRule("config", TypeFamily.COLLECTION, default={}),
                VariableRule("constraints", TypeFamily.STRING, default=None),
                VariableRule("model_uuid", TypeFamily.STRING, required=True),
                VariableRule("revision", TypeFamily.NUMBER, default=None),
                # Optional: subordinate charms must omit units, and
                # subordinate-ness isn't visible from Terraform.
                VariableRule("units", TypeFamily.NUMBER, default=1, optional=True),
                # Optional CC008 charm variables (validated only when present).
                VariableRule("base", TypeFamily.STRING, default=None, optional=True),
                VariableRule("expose", TypeFamily.COLLECTION, default={}, optional=True),
                VariableRule("resources", TypeFamily.COLLECTION, default={}, optional=True),
                VariableRule("machines", TypeFamily.COLLECTION, default=[], optional=True),
                VariableRule(
                    "endpoint_bindings", TypeFamily.COLLECTION, default={}, optional=True
                ),
                VariableRule(
                    "storage_directives", TypeFamily.COLLECTION, default={}, optional=True
                ),
                VariableRule(
                    "offered_endpoints", TypeFamily.COLLECTION, default=[], optional=True
                ),
            ),
            # provides/requires: CC008 "mandatory if the relation exists",
            # undetectable from Terraform, so optional here.
            outputs=(
                OutputRule("application"),
                OutputRule("provides", optional=True),
                OutputRule("requires", optional=True),
                OutputRule("offers", optional=True),
            ),
        ),
        ModuleType.COMPONENT: ModuleInterface(
            variables=(
                VariableRule("model_uuid", TypeFamily.STRING, required=True),
                # `<external_integrations>` is author-named, so unchecked.
                VariableRule(
                    "expose_endpoints", TypeFamily.COLLECTION, default=[], optional=True
                ),
            ),
            outputs=(
                OutputRule("components"),
                OutputRule("provides", optional=True),
                OutputRule("requires", optional=True),
                OutputRule("offers", optional=True),
            ),
        ),
        ModuleType.PRODUCT: ModuleInterface(
            variables=(
                VariableRule("logging-config", TypeFamily.STRING),
                VariableRule("proxy", TypeFamily.COLLECTION),
                VariableRule("risk", TypeFamily.STRING),
                # Product has no fixed-name optional input to check.
            ),
            outputs=(
                OutputRule("metadata"),
                OutputRule("models"),
                OutputRule("offers", optional=True),
                OutputRule("credentials", optional=True),
            ),
        ),
    },
)
