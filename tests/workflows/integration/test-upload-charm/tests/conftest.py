# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test fixtures."""


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--charm-file", action="store")
    parser.addoption(
        "--keep-models",
        action="store_true",
        default=False,
        help="keep temporarily-created models",
    )
    parser.addoption(
        "--use-existing",
        action="store_true",
        default=False,
        help="use existing models and not created models",
    )
    parser.addoption(
        "--model",
        action="store",
        help="temporarily-created model name",
    )
