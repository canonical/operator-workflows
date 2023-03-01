# Copyright 2023 Weii Wang
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

import ops.testing
from charm import SimpleCharmCharm
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        # Enable more accurate simulation of container networking.
        # For more information, see https://juju.is/docs/sdk/testing#heading--simulate-can-connect
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)

        self.harness = Harness(SimpleCharmCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_httpbin_pebble_ready(self):
        # Expected plan after Pebble ready with default config
        expected_plan = {
            "services": {
                "httpbin": {
                    "override": "replace",
                    "summary": "httpbin",
                    "command": "gunicorn -b 0.0.0.0:80 httpbin:app -k gevent",
                    "startup": "enabled",
                    "environment": {"GUNICORN_CMD_ARGS": "--log-level info"},
                }
            },
        }
        # Simulate the container coming up and emission of pebble-ready event
        self.harness.container_pebble_ready("httpbin")
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan("httpbin").to_dict()
        # Check we've got the plan we expected
        self.assertEqual(expected_plan, updated_plan)
        # Check the service was started
        service = self.harness.model.unit.get_container("httpbin").get_service("httpbin")
        self.assertTrue(service.is_running())
        # Ensure we set an ActiveStatus with no message
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_config_changed_valid_can_connect(self):
        # Ensure the simulated Pebble API is reachable
        self.harness.set_can_connect("httpbin", True)
        # Trigger a config-changed event with an updated value
        self.harness.update_config({"log-level": "debug"})
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan("httpbin").to_dict()
        updated_env = updated_plan["services"]["httpbin"]["environment"]
        # Check the config change was effective
        self.assertEqual(updated_env, {"GUNICORN_CMD_ARGS": "--log-level debug"})
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_config_changed_valid_cannot_connect(self):
        # Trigger a config-changed event with an updated value
        self.harness.update_config({"log-level": "debug"})
        # Check the charm is in WaitingStatus
        self.assertIsInstance(self.harness.model.unit.status, WaitingStatus)

    def test_config_changed_invalid(self):
        # Ensure the simulated Pebble API is reachable
        self.harness.set_can_connect("httpbin", True)
        # Trigger a config-changed event with an updated value
        self.harness.update_config({"log-level": "foobar"})
        # Check the charm is in BlockedStatus
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)
