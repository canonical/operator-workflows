# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# mypy: disable-error-code="union-attr"
# pylint: disable=redefined-outer-name,subprocess-run-check,consider-using-with,duplicate-code

"""General configuration module for integration tests."""
from pathlib import Path

import kubernetes
import pytest_asyncio
import yaml
from juju.model import Model
from ops.model import ActiveStatus
from pytest import fixture
from pytest_operator.plugin import OpsTest

# Mype can't recognize the name as a string type, so we should skip the type check.
ACTIVE_STATUS_NAME = ActiveStatus.name  # type: ignore[has-type]
ANY_APP_NAME = "any"
INGRESS_APP_NAME = "ingress"
NEW_HOSTNAME = "any.other"
NEW_INGRESS = "any-other-ingress"
NEW_PORT = 18080


@fixture(scope="module")
def metadata():
    """Provide charm metadata."""
    yield yaml.safe_load(Path("./metadata.yaml").read_text(encoding="utf8"))


@fixture(scope="module")
def app_name(metadata):
    """Provide app name from the metadata."""
    yield metadata["name"]


@pytest_asyncio.fixture(scope="module", name="model")
async def model_fixture(ops_test: OpsTest) -> Model:
    """The current test model."""
    assert ops_test.model
    return ops_test.model


@fixture(scope="module")
def run_action(ops_test: OpsTest):
    """Create a async function to run action and return results."""

    async def _run_action(application_name, action_name, **params):
        """Run a juju action.

        Args:
            application_name: Name of the Juju application.
            action_name: Name of the action to execute.
            params: Extra parameters for the action.

        Returns:
            The results of the action.
        """
        application = ops_test.model.applications[application_name]
        action = await application.units[0].run_action(action_name, **params)
        await action.wait()
        return action.results

    return _run_action


@fixture(scope="module")
def wait_for_ingress(ops_test: OpsTest):
    """Create an async function, that will wait until ingress resource with certain name exists."""
    kubernetes.config.load_kube_config()
    kube = kubernetes.client.NetworkingV1Api()

    async def _wait_for_ingress(ingress_name):
        """Wait for the Ingress to be configured.

        Args:
            ingress_name: Name of the Ingress.
        """
        await ops_test.model.block_until(
            lambda: ingress_name
            in [
                ingress.metadata.name
                for ingress in kube.list_namespaced_ingress(ops_test.model_name).items
            ],
            wait_period=5,
            timeout=10 * 60,
        )

    return _wait_for_ingress


@fixture(scope="module")
def get_ingress_annotation(ops_test: OpsTest):
    """Create a function that will retrieve all annotation from a ingress by its name."""
    assert ops_test.model
    kubernetes.config.load_kube_config()
    kube = kubernetes.client.NetworkingV1Api()
    model_name = ops_test.model_name

    def _get_ingress_annotation(ingress_name: str):
        """Get the annotations from an Ingress.

        Args:
            ingress_name: Name of the Ingress.

        Returns:
            the list of annotations from the requested Ingress.
        """
        return kube.read_namespaced_ingress(
            ingress_name, namespace=model_name
        ).metadata.annotations

    return _get_ingress_annotation


@pytest_asyncio.fixture(scope="module")
async def wait_ingress_annotation(ops_test: OpsTest, get_ingress_annotation):
    """Create an async function that will wait until certain annotation exists on ingress."""
    assert ops_test.model

    async def _wait_ingress_annotation(ingress_name: str, annotation_name: str):
        """Wait until the ingress annotations are done.

        Args:
            ingress_name: Name of the ingress.
            annotation_name: Name of the ingress' annotation.
        """
        await ops_test.model.block_until(
            lambda: annotation_name in get_ingress_annotation(ingress_name),
            wait_period=5,
            timeout=300,
        )

    return _wait_ingress_annotation


@pytest_asyncio.fixture(scope="module")
async def build_and_deploy_ingress(model: Model, ops_test: OpsTest):
    """Create an async function to build the nginx ingress integrator charm then deploy it.

    Args:
        model: Juju model for the test.
        ops_test: Operator Framework for the test.
    """

    async def _build_and_deploy_ingress():
        """Build and deploy the Ingress charm.

        Returns:
            The fully deployed Ingress charm.
        """
        charm = await ops_test.build_charm(".")
        return await model.deploy(
            str(charm), application_name="ingress", series="focal", trust=True
        )

    return _build_and_deploy_ingress


@pytest_asyncio.fixture(scope="module")
async def deploy_any_charm(model: Model):
    """Create an async function to deploy any-charm.

    The function accepts a string as the initial src-overwrite configuration.
    """

    async def _deploy_any_charm(src_overwrite):
        """Deploy the any-charm for testing.

        Args:
            src_overwrite: files to overwrite for testing purposes.

        Returns:
            The any-charm application.
        """
        return await model.deploy(
            "any-charm",
            application_name="any",
            channel="beta",
            config={"python-packages": "pydantic<2.0", "src-overwrite": src_overwrite},
        )

    return _deploy_any_charm
