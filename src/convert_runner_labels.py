#!/usr/bin/env python3
"""Convert the runner labels from GitHub style to Github runner charm style.

This a temporary solution.

The GitHub runner charm uses different labeling of ubuntu series than GitHub.
E.g., Github runner charm uses "jammy", while GitHub uses "ubuntu-22.04".
"""

import argparse
import json
from typing import Iterable


SERIES_MAPPING = {
    "ubuntu-latest": "jammy",
    "ubuntu-22.04": "jammy",
    "ubuntu-20.04": "focal",
}


def parse_args() -> argparse.Namespace:
    """Configure the command-line arguments.

    Returns:
        An object containing the arguments as attributes.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("labels")
    return parser.parse_args()


def convert_labels_to_charm(labels: Iterable[str]) -> Iterable[str]:
    """Convert the label style from GitHub to GitHub runner charm.

    If the labels contains the "self-hosted" label, convert the label style
    from GitHub to GitHub runner charm.

    Inputs:
        labels: Labels in GitHub style.
    Returns:
        Labels in GitHub runner charm style converted from `labels`.
    """
    if "self-hosted" in labels:
        return map(
            lambda label: SERIES_MAPPING[label] if label in SERIES_MAPPING else label,
            labels,
        )
    else:
        return labels


if __name__ == "__main__":
    args = parse_args()
    
    # TODO: Debug
    import sys
    print(args.labels, file=sys.stderr, flush=True)

    labels = json.loads(args.labels)
    converted = convert_labels_to_charm(labels)
    labels_str = json.dumps(list(converted))
    print(labels_str)
