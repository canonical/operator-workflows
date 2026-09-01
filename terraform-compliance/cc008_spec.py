# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CC008 Terraform module standards, expressed as data.

This module is the single source of truth for *what* CC008 requires: which
files a module must have, the mandatory variables/outputs per module type
(and their type family/required/default constraints), which resource types
tie components together in a Product module, and which module-source refs
count as floating (disallowed) branch names.

Deliberately contains no checking logic (no HCL parsing, no comparisons, no
``if`` statements beyond what a dataclass needs) - only value objects and
their instantiation. ``cc008_check.py`` imports ``CC008_SPEC`` and contains
all of the *how* (parsing, constraint math, alphabetical comparison, etc).
This split means the CC008 contract enforced by this checker can be read and
reviewed in full by reading this file alone, without following any code
execution.
"""

from dataclasses import dataclass
from enum import StrEnum, nonmember


class ModuleType(StrEnum):
    """The CC008 module categories this checker distinguishes."""

    CHARM = "charm"
    COMPONENT = "component"
    PRODUCT = "product"


class TypeFamily(StrEnum):
    """Broad Terraform type families, used to lightly validate variable types.

    Deliberately coarse (a bucket, not an exact type match) to avoid the kind
    of false positives already seen with shape-based validation elsewhere in
    this checker: CC008 does not mandate one specific collection/object shape
    for most of these variables, so this only catches obvious mismatches such
    as a numeric variable declared as a string.
    """

    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"
    COLLECTION = "collection"  # map(...), list(...), set(...), object({...})

    # Terraform's own collection/structural type keywords, all bucketed into
    # COLLECTION. Wrapped in `nonmember` so this stays a plain class
    # attribute instead of becoming a spurious enum member.
    _COLLECTION_KEYWORDS = nonmember(
        frozenset({"map", "list", "set", "object", "tuple"})
    )

    @classmethod
    def _missing_(cls, value: object) -> "TypeFamily | None":
        """Resolve Terraform's collection/structural keywords to COLLECTION.

        Lets ``TypeFamily("map")``, ``TypeFamily("object")``, etc. resolve
        directly to ``TypeFamily.COLLECTION`` without a separate lookup table
        in the checker.
        """
        if value in cls._COLLECTION_KEYWORDS:
            return cls.COLLECTION
        return None


class _NoDefaultCheck:
    """Sentinel type meaning "don't check the default value".

    A dedicated class (rather than a bare ``object()``) so its ``repr`` is
    readable in test failure output and dataclass reprs, instead of an opaque
    ``<object object at 0x...>``.
    """

    def __repr__(self) -> str:
        return "NO_DEFAULT_CHECK"


# ``None`` is itself a legitimate Terraform default that some rules DO check
# for (e.g. a variable pinned to default exactly ``None``), so it cannot
# double as "no opinion on the default" - hence this separate sentinel.
NO_DEFAULT_CHECK = _NoDefaultCheck()


@dataclass(frozen=True)
class VariableRule:
    """Constraints CC008 places on one mandatory variable."""

    name: str
    type_family: TypeFamily | None = None
    required: bool = False  # must have no `default` at all (nullable is not enough)
    default: object = (
        NO_DEFAULT_CHECK  # exact value the default must equal, if declared
    )
    # If True, the variable need not be declared; when absent it is skipped,
    # when present its type/default rules still apply. (`required` is a
    # separate axis: it constrains the default of a variable that must exist.)
    optional: bool = False


@dataclass(frozen=True)
class ModuleInterface:
    """The mandatory variables and outputs a CC008 module type must declare."""

    variables: tuple[VariableRule, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class TerraformBlockRequirements:
    """CC008's requirements for a module's `terraform.tf` provider block."""

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


# The single source of truth for CC008's requirements. Add a new ModuleType
# member and a `module_interfaces` entry here to support another module kind.
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
    # Resource/data block types whose presence indicates a module ties
    # components together, per CC008's definition of Product modules.
    tying_resource_types=frozenset(
        {"juju_model", "juju_secret", "juju_integration", "juju_offer"}
    ),
    # Conventional default/floating branch names rejected as module refs.
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
                # CC008 lists `units` (number, default 1) as mandatory EXCEPT
                # for subordinate charms, where it must NOT be provided.
                # Whether a charm is subordinate is declared in its
                # metadata.yaml, which is not visible from Terraform alone, so
                # mandating `units` here would wrongly flag every subordinate
                # charm module. We therefore do not enforce it.
                # VariableRule("units", TypeFamily.NUMBER, default=1),
                # Optional CC008 charm variables: not required to exist, but
                # when present must match the type the juju_application
                # resource expects. Any other input name is allowed and
                # unchecked.
                VariableRule("base", TypeFamily.STRING, optional=True),
                VariableRule("expose", TypeFamily.COLLECTION, optional=True),
                VariableRule("resources", TypeFamily.COLLECTION, optional=True),
                VariableRule("machines", TypeFamily.COLLECTION, optional=True),
                VariableRule("endpoint_bindings", TypeFamily.COLLECTION, optional=True),
                VariableRule("storage_directives", TypeFamily.COLLECTION, optional=True),
                VariableRule("offered_endpoints", TypeFamily.COLLECTION, optional=True),
            ),
            outputs=("application", "provides", "requires"),
        ),
        ModuleType.COMPONENT: ModuleInterface(
            variables=(VariableRule("model_uuid", TypeFamily.STRING, required=True),),
            outputs=("components",),
        ),
        ModuleType.PRODUCT: ModuleInterface(
            variables=(
                VariableRule("logging-config", TypeFamily.STRING),
                VariableRule("proxy", TypeFamily.COLLECTION),
                VariableRule("risk", TypeFamily.STRING),
            ),
            outputs=("metadata", "models"),
        ),
    },
)
