# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test fixtures."""


def pytest_addoption(parser):
    """Add test arguments."""
    parser.addoption("--charm-file", action="store")
    parser.addoption("--test-image", action="store")
    parser.addoption("--test-file-resource", action="store")
