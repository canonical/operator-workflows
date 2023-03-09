#!/usr/bin/env python3
"""Convert the runner labels from GitHub runner charm style to Github style.

This a temporary solution.

The GitHub runner charm uses different labeling of ubuntu series than GitHub.
E.g., Github runner charm uses "jammy", while GitHub uses "ubuntu-22.04".
"""

import argparse


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


def convert_labels_to_charm(labels: list[str]) -> list[str]:
    """Convert the label style from GitHub to GitHub runner charm.

    Inputs:
        labels: A list of labels in GitHub style.
    Returns:
        A list of labels in GitHub runner charm style converted from `labels`.
    """
    return [
        SERIES_MAPPING[label] if label in SERIES_MAPPING else label for label in labels
    ]


if __name__ == "__main__":
    args = parse_args()
    converted = convert_labels_to_charm(args.labels)
    print(converted)
