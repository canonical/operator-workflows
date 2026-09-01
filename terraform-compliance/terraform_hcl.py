# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Load Terraform HCL and normalise python-hcl2's output quirks.

Knows about python-hcl2 (quoted labels/values, the ``__is_block__`` sentinel,
two-labeled resource/data blocks) but nothing about CC008.
"""

import re
from pathlib import Path

import hcl2
from cc008_spec import TypeFamily

# Outermost type keyword in a variable's `type`, e.g. "string", "${map(...)}".
_TYPE_KEYWORD_PATTERN = re.compile(r"([a-z]+)\s*\(?")


def unquote(value: str) -> str:
    """Strip the double quotes python-hcl2 keeps on string literals."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def block_label(block: dict) -> str:
    """Return the single label of a one-labeled block."""
    return next(key for key in block if key != "__is_block__")


def block_body(block: dict) -> dict:
    """Return the body dict of a one-labeled block."""
    return block[block_label(block)]


def block_names(parsed: dict, block_type: str) -> list[str]:
    """Return the ordered labels of blocks of a given type."""
    return [unquote(block_label(block)) for block in parsed.get(block_type, [])]


def variable_bodies(parsed_files: list[dict]) -> dict[str, dict]:
    """Map variable name to its parsed body (later declarations win)."""
    return {
        unquote(block_label(block)): block_body(block)
        for parsed in parsed_files
        for block in parsed.get("variable", [])
    }


def resource_type_labels(parsed_files: list[dict], block_type: str) -> list[str]:
    """Return the resource/data *type* label of each block of a given type."""
    return [
        unquote(block_label(block))
        for parsed in parsed_files
        for block in parsed.get(block_type, [])
    ]


def module_sources(parsed_files: list[dict]) -> list[str]:
    """Return source values from module blocks."""
    sources: list[str] = []
    for parsed in parsed_files:
        for block in parsed.get("module", []):
            source = block_body(block).get("source")
            if source:
                sources.append(unquote(source))
    return sources


def type_family(type_expr: str) -> TypeFamily | None:
    """Return the broad TypeFamily of a variable's `type` expression."""
    match = _TYPE_KEYWORD_PATTERN.match(unquote(type_expr).removeprefix("${").strip())
    if not match:
        return None
    try:
        return TypeFamily(match.group(1))
    except ValueError:
        return None


def load_file(path: Path) -> dict:
    """Parse a single Terraform file with python-hcl2."""
    with path.open(encoding="utf-8") as handle:
        return hcl2.load(handle)


def load_module_files(module_dir: Path) -> dict[str, dict]:
    """Map filename to parsed contents for a module's .tf files."""
    return {path.name: load_file(path) for path in module_dir.glob("*.tf")}
