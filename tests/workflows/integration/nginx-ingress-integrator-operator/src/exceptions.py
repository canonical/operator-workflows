# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exceptions used by the nginx-ingress-integrator charm."""


class InvalidIngressError(Exception):
    """Custom error that indicates invalid ingress definition.

    Args:
        msg: error message.
    """

    def __init__(self, msg: str):
        """Construct the InvalidIngressError object.

        Args:
            msg: error message.
        """
        self.msg = msg
