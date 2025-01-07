#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for tesing charm upload."""

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus


class TestUploadCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Initialize the charm.

        Args:
            args: charm initialization arguments.
        """
        super().__init__(*args)
        self.unit.status = ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    main(TestUploadCharm)
