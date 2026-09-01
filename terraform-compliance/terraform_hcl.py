# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Loading and shape-normalising Terraform HCL parsed by python-hcl2.

Everything in this module knows about python-hcl2's v8 output quirks and
nothing about CC008: string values and block labels keep their literal
double quotes, every block body carries an ``__is_block__`` sentinel key, and
``resource``/``data`` blocks are two-labeled and represented as nested
single-key dicts (``{type: {name: body}}``). ``cc008_check.py`` consumes the
normalised results returned here and applies the CC008 rules; keeping the two
apart means a parsing quirk can be understood and fixed without reading any
check logic.
"""

import re
from pathlib import Path

import hcl2
from cc008_spec import TypeFamily

# Matches the outermost type keyword python-hcl2 leaves in a variable's `type`
# expression, e.g. "string", "${map(string)}", "${object({...})}", "number".
_TYPE_KEYWORD_PATTERN = re.compile(r"([a-z]+)\s*\(?")


def unquote(value: str) -> str:
    """Strip the surrounding double quotes python-hcl2 keeps on string literals."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def block_label(block: dict) -> str:
    """Return the single label of a one-labeled block (e.g. variable/output/module)."""
    return next(key for key in block if key != "__is_block__")


def block_body(block: dict) -> dict:
    """Return the body dict of a one-labeled block, keyed by its label."""
    return block[block_label(block)]


def block_names(parsed: dict, block_type: str) -> list[str]:
    """Return the ordered labels of blocks of a given type in a parsed file."""
    return [unquote(block_label(block)) for block in parsed.get(block_type, [])]


def variable_bodies(parsed_files: list[dict]) -> dict[str, dict]:
    """Return a mapping of variable name to its parsed body dict.

    Later declarations of the same name (across files) win, matching the
    order files are discovered in.
    """
    return {
        unquote(block_label(block)): block_body(block)
        for parsed in parsed_files
        for block in parsed.get("variable", [])
    }


def resource_type_labels(parsed_files: list[dict], block_type: str) -> list[str]:
    """Return the resource/data type label of every block of a given type.

    ``resource``/``data`` blocks have two labels (type, name); python-hcl2
    represents each as a single-key dict ``{type: {name: body}}``, so the
    single key at this level is the resource/data type.
    """
    return [
        unquote(block_label(block))
        for parsed in parsed_files
        for block in parsed.get(block_type, [])
    ]


def module_sources(parsed_files: list[dict]) -> list[str]:
    """Return source values discovered in module blocks."""
    sources: list[str] = []
    for parsed in parsed_files:
        for block in parsed.get("module", []):
            source = block_body(block).get("source")
            if source:
                sources.append(unquote(source))
    return sources


def type_family(type_expr: str) -> TypeFamily | None:
    """Return the broad TypeFamily of a variable's `type` expression, if known.

    ``TypeFamily``'s own ``_missing_`` hook resolves Terraform's collection
    keywords (``map``, ``object``, etc.) to ``TypeFamily.COLLECTION``, so
    no separate lookup table is needed here.
    """
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
    """Return a mapping of filename to parsed contents for a module's .tf files."""
    return {path.name: load_file(path) for path in module_dir.glob("*.tf")}
