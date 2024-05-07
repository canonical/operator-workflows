# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
# mypy: disable-error-code="arg-type"

import os
import typing
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch

import kubernetes
import kubernetes.client
import ops
import pytest
from charms.tls_certificates_interface.v3.tls_certificates import (
    CertificateAvailableEvent,
    CertificateInvalidatedEvent,
)
from ops.charm import ActionEvent, RelationCreatedEvent, RelationJoinedEvent
from ops.model import SecretNotFoundError
from ops.testing import Harness

from charm import NginxIngressCharm
from controller.secret import SecretController
from tests.unit.constants import TEST_NAMESPACE
from tls_relation import TLSRelationService


class TestCertificatesRelation(unittest.TestCase):
    """Unit test cause for the certificates relation."""

    @pytest.mark.usefixtures("patch_load_incluster_config")
    def setUp(self):
        """Setup the harness object."""
        self.harness = Harness(NginxIngressCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def set_up_all_relations(self):
        """Set up certificates and nginx-route relations.

        Returns:
            A tuple containing both relation IDs.
        """
        peer_rel_id = self.harness.add_relation(
            "nginx-peers",
            "nginx-ingress-integrator",
            app_data={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )
        nginx_route_rel_id = self.harness.add_relation(
            "nginx-route",
            "gunicorn",
            app_data={
                "service-hostname": "example.com",
                "service-port": "8080",
                "service-namespace": "test",
                "service-name": "app",
            },
            unit_data={"host": '"test.svc.cluster.local"', "ip": '"10.0.0.1"'},
        )
        tls_rel_id = self.harness.add_relation(
            "certificates",
            "self-signed-certificates",
            app_data={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
            },
        )
        return nginx_route_rel_id, tls_rel_id, peer_rel_id

    def set_up_nginx_relation(self):
        """Set up nginx-route relation."""
        self.harness.add_relation(
            "nginx-route",
            "gunicorn",
            app_data={
                "service-hostname": "example.com",
                "service-port": "8080",
                "service-namespace": "test",
                "service-name": "app",
            },
            unit_data={"host": '"test.svc.cluster.local"', "ip": '"10.0.0.1"'},
        )

    def set_up_cert_relation(self):
        """Set up certificates relation."""
        self.harness.add_relation(
            "certificates",
            "self-signed-certificates",
            app_data={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
            },
        )

    def set_up_peer_relation(self):
        """Set up certificates relation."""
        self.harness.add_relation(
            "nginx-peers",
            "nginx-ingress-integrator",
            app_data={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )

    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_generate_password(self):
        tls_rel = TLSRelationService(self.harness.charm.model)
        password = tls_rel.generate_password()
        assert type(password) == str
        assert len(password) == 12

    @patch("tls_relation.TLSRelationService.update_relation_data_fields")
    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.model.Model.get_secret")
    @patch("ops.JujuVersion.has_secrets")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_cert_relation(
        self,
        mock_has_secrets,
        mock_get_secret,
        mock_update_ingress,
        mock_gen_csr,
        mock_gen_pass,
        mock_update,
    ):
        mock_gen_pass.return_value = "123456789101"
        mock_gen_csr.return_value = b"csr"
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.set_up_all_relations()
        self.harness.enable_hooks()
        mock_gen_pass.assert_called_once()
        mock_gen_csr.assert_called_once()
        assert mock_get_secret.call_count == 2

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.generate_csr")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_creation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.model.Model.get_secret")
    @patch("ops.JujuVersion.has_secrets")
    def test_certificate_relation_created_secret_error(
        self,
        mock_has_secrets,
        mock_get_secret,
        mock_ingress_update,
        mock_create_cert,
        mock_gen_csr,
        mock_get_data,
    ):
        mock_get_data.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        event = RelationCreatedEvent(relation=None, handle=None)
        self.harness.set_leader(True)
        self.harness.disable_hooks()
        self.set_up_all_relations()
        self.harness.enable_hooks()
        mock_has_secrets.return_value = True
        mock_get_secret.side_effect = SecretNotFoundError
        self.harness.charm._on_certificates_relation_created(event)
        mock_create_cert.assert_not_called()
        mock_gen_csr.assert_not_called()

    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.model.Model.get_secret")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_cert_relation_no_secrets(
        self, mock_get_secret, mock_update_ingress, mock_gen_csr, mock_gen_pass, mock_get_data
    ):
        mock_get_data.return_value = "whatever"
        mock_gen_pass.return_value = "123456789101"
        mock_gen_csr.return_value = b"csr"
        self.harness.set_leader(True)
        self.set_up_all_relations()
        mock_gen_pass.assert_called_once()
        mock_gen_csr.assert_called_once()
        mock_get_secret.assert_not_called()

    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("ops.model.Model.get_secret")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_on_certificates_relation_created_no_relation(
        self, mock_get_secret, mock_gen_csr, mock_gen_pass
    ):
        self.harness.charm._on_certificates_relation_created(MagicMock())
        mock_gen_pass.assert_not_called()
        mock_gen_csr.assert_not_called()
        mock_get_secret.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_all_certificates_invalidated_no_secret(self, mock_ingress_update):
        self.harness.set_leader(True)
        self.set_up_peer_relation()
        self.set_up_nginx_relation()
        relation_id = self.harness.add_relation("certificates", "self-signed-certificates")
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "private_key": "whatever",
                "private_key_password": "whatever",
            },
        )
        self.harness.charm._on_all_certificates_invalidated(MagicMock())

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.JujuVersion.has_secrets")
    def test_all_certificates_invalidated(
        self, mock_has_secrets, mock_ingress_update, mock_get_secret
    ):
        """
        arrange: given the harnessed charm with the nginx-route relation set
        act: when the on_certificate_invalidated method is executed
        assert: the method is executed properly
        """
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.set_up_nginx_relation()
        self.harness.charm._on_all_certificates_invalidated(MagicMock())
        mock_get_secret.assert_called_once()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._cleanup")
    @patch("charm.NginxIngressCharm._certificate_revoked")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("tls_relation.TLSRelationService.get_hostname_from_cert")
    def test_on_certificate_invalidated_revoke(
        self, mock_get_hostname, mock_update_ingress, mock_cert_revoked, mock_cleanup
    ):
        """
        arrange: given the harnessed charm with all relations set and no juju secrets
        act: when the on_certificate_invalidated method is executed with a revoked cert
        assert: the method is executed properly, calling _on_certificate_revoked
        """
        mock_get_hostname.return_value = "whatever"
        self.harness.set_leader(True)
        self.harness.add_relation("certificates", "certificates")
        event = CertificateInvalidatedEvent(
            reason="revoked",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_invalidated(event)
        mock_cert_revoked.assert_called_once()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._cleanup")
    @patch("tls_relation.TLSRelationService.certificate_expiring")
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_on_certificate_invalidated_expire(
        self, mock_update_ingress, mock_cert_expired, mock_cleanup
    ):
        """
        arrange: given the harnessed charm with all relations set and no juju secrets
        act: when the on_certificate_invalidated method is executed with an expired cert
        assert: the method is executed properly, calling _on_certificate_expired
        """
        self.harness.set_leader(True)
        self.harness.add_relation("certificates", "certificates")
        event = CertificateInvalidatedEvent(
            reason="expired",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_invalidated(event)
        mock_cert_expired.assert_called_once()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._on_certificate_expiring")
    @patch("charm.NginxIngressCharm._certificate_revoked")
    def test_on_certificate_invalidated_blocked(self, mock_cert_revoked, mock_cert_expired):
        """
        arrange: given the harnessed charm with no TLS relation
        act: when the _on_certificate_invalidated method is executed
        assert: the method is halted due to the lack of TLS relation
        """
        event = CertificateInvalidatedEvent(
            reason="expired",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_invalidated(event)
        mock_cert_expired.assert_not_called()
        mock_cert_revoked.assert_not_called()

    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_revocation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.JujuVersion.has_secrets")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_certificate_revoked(
        self,
        mock_has_secrets,
        mock_update_ingress,
        mock_cert_revocation,
        mock_cert_create,
        mock_get_secret,
    ):
        """
        arrange: given the harnessed charm with all relations set
        act: when the _certificate_revoked method is executed
        assert: the method is executed properly
        """
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.set_up_peer_relation()
        self.set_up_nginx_relation()
        relation_id = self.harness.add_relation("certificates", "self-signed-certificates")
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )
        self.harness.charm._certificate_revoked(["example.com"])
        mock_cert_revocation.assert_called_once()
        mock_get_secret.assert_called_once()

    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_revocation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.JujuVersion.has_secrets")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_certificate_revoked_no_old_csr(
        self,
        mock_get_data,
        mock_has_secrets,
        mock_update_ingress,
        mock_cert_revocation,
        mock_cert_create,
        mock_get_secret,
    ):
        """
        arrange: given the harnessed charm with all relations set and no old_csr
        act: when the _certificate_revoked method is executed
        assert: the method is halted due to old_csr not existing
        """
        mock_get_data.return_value = None
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.set_up_nginx_relation()
        relation_id = self.harness.add_relation("certificates", "self-signed-certificates")
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )
        self.harness.charm._certificate_revoked(["example.com"])
        mock_cert_revocation.assert_not_called()
        mock_get_secret.assert_not_called()

    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_revocation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.JujuVersion.has_secrets")
    @patch("tls_relation.TLSRelationService.pop_relation_data_fields")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_certificate_revoked_no_rel_data(
        self,
        mock_pop_data,
        mock_has_secrets,
        mock_update_ingress,
        mock_cert_revocation,
        mock_cert_create,
        mock_get_secret,
    ):
        """
        arrange: given the harnessed charm with all relations set but no TLS relation data
        act: when the _certificate_revoked method is executed
        assert: the method handles the exception gracefully
        """
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.set_up_nginx_relation()
        mock_pop_data.side_effect = KeyError
        relation_id = self.harness.add_relation("certificates", "self-signed-certificates")
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )
        expected_error = "Relation data for example.com already does not exist"
        with self.assertLogs(level="WARNING") as logger:
            self.harness.charm._certificate_revoked(["example.com"])
            mock_cert_revocation.assert_called_once()
            mock_get_secret.assert_called_once()
            self.assertTrue(expected_error in logger.output[0])

    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_revocation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.JujuVersion.has_secrets")
    @patch("tls_relation.TLSRelationService.pop_relation_data_fields")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_certificate_revoked_secret_error(
        self,
        mock_pop_data,
        mock_has_secrets,
        mock_update_ingress,
        mock_cert_revocation,
        mock_cert_create,
        mock_get_secret,
    ):
        """
        arrange: given the harnessed charm with all relations set
        act: when the _certificate_revoked method is executed and secret error is fired
        assert: the method handles the exception gracefully
        """
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.set_up_nginx_relation()
        mock_pop_data.side_effect = KeyError
        relation_id = self.harness.add_relation("certificates", "self-signed-certificates")
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )
        mock_get_secret.side_effect = SecretNotFoundError
        expected_error = "Juju secret for example.com already does not exist"
        with self.assertLogs(level="WARNING") as logger:
            self.harness.charm._certificate_revoked(["example.com"])
            mock_cert_revocation.assert_not_called()
            mock_get_secret.assert_called_once()
            self.assertTrue(expected_error in logger.output[0])

    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_revocation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_certificate_revoked_no_secrets(
        self,
        mock_update_ingress,
        mock_cert_revoke,
        mock_cert_create,
        mock_get_secret,
    ):
        """
        arrange: given the harnessed charm with all relations set and no juju secrets
        act: when the _certificate_revoked method is executed
        assert: the method is executed properly
        """
        self.harness.set_leader(True)
        self.set_up_peer_relation()
        self.set_up_nginx_relation()
        relation_id = self.harness.add_relation("certificates", "self-signed-certificates")
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
                "key-example.com": "whatever",
                "password-example.com": "whatever",
            },
        )
        self.harness.charm._certificate_revoked(["example.com"])
        mock_cert_revoke.assert_called_once()
        mock_get_secret.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("tls_relation.generate_private_key")
    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_renewal"
    )
    @patch("charm.NginxIngressCharm._cleanup")
    def test_certificate_revoked_no_nginx_relation(
        self,
        mock_cleanup,
        mock_cert_renewal,
        mock_cert_create,
        mock_get_secret,
        mock_gen_key,
        mock_gen_csr,
        mock_gen_password,
    ):
        """
        arrange: given the harnessed charm with no nginx-route relation
        act: when the _certificate_revoked method is executed
        assert: the method is halted due to the lack of nginx-route relation
        """
        self.set_up_cert_relation()
        self.harness.charm._certificate_revoked(["whatever"])
        mock_cert_renewal.assert_not_called()
        mock_get_secret.assert_not_called()
        mock_gen_csr.assert_not_called()
        mock_gen_key.assert_not_called()
        mock_gen_password.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("tls_relation.generate_private_key")
    @patch("ops.model.Model.get_secret")
    @patch("charm.NginxIngressCharm._on_certificates_relation_created")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_renewal"
    )
    def test_certificate_revoked_no_tls_relation(
        self,
        mock_cert_renewal,
        mock_cert_create,
        mock_get_secret,
        mock_gen_key,
        mock_gen_csr,
        mock_gen_password,
    ):
        """
        arrange: given the harnessed charm with no TLS relation
        act: when the _certificate_revoked method is executed
        assert: the method is halted due to the lack of TLS relation
        """
        self.harness.charm._certificate_revoked(["whatever"])
        mock_cert_renewal.assert_not_called()
        mock_get_secret.assert_not_called()
        mock_gen_csr.assert_not_called()
        mock_gen_key.assert_not_called()
        mock_gen_password.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_renewal"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.TLSRelationService.get_hostname_from_cert")
    @patch("tls_relation.generate_csr")
    @patch("ops.JujuVersion.has_secrets")
    @patch("ops.model.Model.get_secret")
    def test_certificate_expiring(
        self,
        mock_get_secret,
        mock_has_secrets,
        mock_gen_csr,
        mock_get_hostname,
        mock_get_data,
        mock_ingress_update,
        mock_cert_renewal,
    ):
        """
        arrange: given the harnessed charm with all relations set
        act: when the _on_certificate_expiring method is executed
        assert: the method is executed properly
        """
        mock_has_secrets.return_value = True
        mock_get_data.return_value = "whatever"
        mock_get_hostname.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        self.harness.set_leader(True)
        self.harness.disable_hooks()
        self.set_up_all_relations()
        self.harness.enable_hooks()
        event = CertificateInvalidatedEvent(
            reason="expired",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_expiring(event)
        mock_cert_renewal.assert_called_once()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_renewal"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.TLSRelationService.get_hostname_from_cert")
    @patch("tls_relation.generate_csr")
    def test_certificate_expiring_no_secrets(
        self,
        mock_gen_csr,
        mock_get_hostname,
        mock_get_data,
        mock_ingress_update,
        mock_cert_renewal,
    ):
        """
        arrange: given the harnessed charm with all relations set and no juju secrets
        act: when the _on_certificate_expiring method is executed
        assert: the method is executed properly
        """
        mock_get_data.return_value = "whatever"
        mock_get_hostname.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        self.harness.set_leader(True)
        self.set_up_all_relations()
        event = CertificateInvalidatedEvent(
            reason="expired",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_expiring(event)
        mock_cert_renewal.assert_called_once()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_renewal"
    )
    def test_certificate_expiring_no_tls_relation(self, mock_cert_renewal):
        """
        arrange: given the harnessed charm with no TLS relation
        act: when the _on_certificate_expiring method is executed
        assert: the method is halted due to the lack of TLS relation
        """
        event = CertificateInvalidatedEvent(
            reason="expired",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_expiring(event)
        mock_cert_renewal.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_renewal"
    )
    @patch("charm.NginxIngressCharm._cleanup")
    def test_certificate_expiring_no_nginx_relation(self, mock_cleanup, mock_cert_renewal):
        """
        arrange: given the harnessed charm with no nginx-route relation
        act: when the _on_certificate_expiring method is executed
        assert: the method is halted due to the lack of nginx-route relation
        """
        self.set_up_cert_relation()
        event = CertificateInvalidatedEvent(
            reason="expired",
            certificate="",
            certificate_signing_request="",
            ca="",
            chain="",
            handle=None,
        )
        self.harness.charm._on_certificate_expiring(event)
        mock_cert_renewal.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_certificate_available_no_relation(self, mock_update):
        """
        arrange: given the harnessed charm with no TLS relation
        act: when the _on_certificate_available method is executed
        assert: the method is halted due to the lack of TLS relation
        """
        event = CertificateAvailableEvent(
            certificate="", certificate_signing_request="", ca="", chain="", handle=None
        )
        self.harness.charm._on_certificate_available(event)
        mock_update.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.TLSRelationService.get_hostname_from_cert")
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_certificate_available_no_secrets(
        self, mock_update, mock_get_hostname, mock_get_data, mock_gen_csr, mock_gen_pass
    ):
        """
        arrange: given the harnessed charm with all relations set and no juju secrets
        act: when the _on_certificate_available method is executed
        assert: the method is executed properly
        """
        mock_gen_csr.return_value = b"csr"
        mock_gen_pass.return_value = "123456789101"
        mock_get_data.return_value = "whatever"
        mock_get_hostname.return_value = "whatever"
        self.harness.set_leader(True)
        self.set_up_all_relations()
        event = CertificateAvailableEvent(
            certificate="", certificate_signing_request="", ca="", chain=["whatever"], handle=None
        )
        self.harness.charm._on_certificate_available(event)
        assert mock_update.call_count == 3

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.generate_password")
    @patch("tls_relation.generate_csr")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.TLSRelationService.get_hostname_from_cert")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("ops.JujuVersion.has_secrets")
    @patch("ops.model.Model.get_secret")
    def test_certificate_available(
        self,
        mock_get_secret,
        mock_has_secrets,
        mock_update,
        mock_get_hostname,
        mock_get_data,
        mock_gen_csr,
        mock_gen_pass,
    ):
        """
        arrange: given the harnessed charm with all relations set
        act: when the _on_certificate_available method is executed
        assert: the method is executed properly
        """
        mock_gen_csr.return_value = b"csr"
        mock_gen_pass.return_value = "123456789101"
        mock_get_data.return_value = "whatever"
        mock_get_hostname.return_value = "whatever"
        mock_has_secrets.return_value = True
        self.harness.set_leader(True)
        self.harness.disable_hooks()
        self.set_up_all_relations()
        self.harness.enable_hooks()
        event = CertificateAvailableEvent(
            certificate="", certificate_signing_request="", ca="", chain=["whatever"], handle=None
        )
        self.harness.charm._on_certificate_available(event)
        mock_update.assert_called_once()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.generate_csr")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_creation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_certificate_relation_joined(
        self, mock_ingress_update, mock_create_cert, mock_gen_csr, mock_get_data
    ):
        """
        arrange: given the harnessed charm with all relations set
        act: when the _on_certificates_relation_joined method is executed
        assert: the method is executed properly
        """
        mock_get_data.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        event = RelationJoinedEvent(relation=None, handle=None)
        self.harness.set_leader(True)
        self.set_up_all_relations()
        self.harness.charm._on_certificates_relation_joined(event)
        assert mock_create_cert.call_count == 2
        assert mock_gen_csr.call_count == 2

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._cleanup")
    @patch("tls_relation.generate_csr")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_creation"
    )
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_certificate_relation_joined_no_nginx_relation(
        self, mock_ingress_update, mock_create_cert, mock_gen_csr, mock_cleanup
    ):
        """
        arrange: given the harnessed charm with no nginx-route relation
        act: when the _on_certificates_relation_joined method is executed
        assert: the method is halted due to the lack of nginx-route relation
        """
        self.harness.set_leader(True)
        self.set_up_cert_relation()
        self.harness.charm._on_certificates_relation_joined(MagicMock())
        mock_create_cert.assert_not_called()
        mock_gen_csr.assert_not_called()
        assert mock_cleanup.call_count == 3

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._cleanup")
    @patch("tls_relation.generate_csr")
    @patch(
        "charms.tls_certificates_interface.v3.tls_certificates"
        ".TLSCertificatesRequiresV3.request_certificate_creation"
    )
    def test_certificate_relation_joined_no_cert_relation(
        self, mock_create_cert, mock_gen_csr, mock_cleanup
    ):
        """
        arrange: given the harnessed charm with no TLS relation
        act: when the _on_certificates_relation_joined method is executed
        assert: the method is halted due to the lack of TLS relation
        """
        self.set_up_nginx_relation()
        self.harness.charm._on_certificates_relation_joined(MagicMock())
        mock_create_cert.assert_not_called()
        mock_gen_csr.assert_not_called()
        mock_cleanup.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._cleanup")
    @patch("charm.NginxIngressCharm._certificate_revoked")
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_config_changed_cert_relation_no_update(
        self, mock_update_ingress, mock_cert_revoked, mock_cleanup
    ):
        """
        arrange: given the harnessed charm
        act: when we change the service name and port but keep the hostname
        assert: there are no certificate updates taking place
        """
        with mock.patch.object(kubernetes.client, "NetworkingV1Api") as mock_networking_v1_api:
            self.harness.set_leader(True)
            mock_ingress = mock.Mock()
            mock_ingress.spec.rules = [
                kubernetes.client.V1IngressRule(
                    host="to-be-removed.local",
                )
            ]
            mock_ingresses = (
                mock_networking_v1_api.return_value.list_namespaced_ingress.return_value
            )
            mock_ingresses.items = [mock_ingress]
            cert_relation_id = self.harness.add_relation("certificates", "certificates")
            ingress_relation_id = self.harness.add_relation("ingress", "gunicorn")
            self.harness.add_relation_unit(ingress_relation_id, "gunicorn/0")
            relations_data = {
                "service-name": "gunicorn",
                "service-hostname": "to-be-removed.local",
                "service-port": "80",
            }
            self.harness.update_relation_data(ingress_relation_id, "gunicorn", relations_data)
            self.harness.update_relation_data(
                relation_id=cert_relation_id,
                app_or_unit=self.harness.charm.unit.name,
                key_values={
                    "csr": "whatever",
                    "certificate": "whatever",
                    "ca": "whatever",
                    "chain": "whatever",
                },
            )
            self.harness.update_config({"service-hostname": "to-be-removed.local"})
            mock_cert_revoked.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_update_cert_on_service_hostname_change(self):
        """
        arrange: given the harnessed charm
        act: when the service hostname is changed and the scan for TLS certificate updates is done
        assert: there are TLS certificates to revoke
        """
        with mock.patch.object(kubernetes.client, "NetworkingV1Api") as mock_networking_v1_api:
            tls_rel = TLSRelationService(self.harness.charm.model)
            service_hostname = "hostname"
            mock_ingress = mock.Mock()
            mock_ingress.spec.rules = [
                kubernetes.client.V1IngressRule(
                    host="to-be-removed.local",
                )
            ]
            mock_ingresses = (
                mock_networking_v1_api.return_value.list_namespaced_ingress.return_value
            )
            mock_ingresses.items = [mock_ingress]
            tls_certificates_relation = MagicMock()
            unit_name = self.harness.charm.unit
            tls_certificates_relation.return_value.data[unit_name].return_value = {"csr": "csr"}
            result = tls_rel.update_cert_on_service_hostname_change(
                service_hostname, tls_certificates_relation, TEST_NAMESPACE
            )
            assert result

    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_config_changed_cert_relation_update(self):
        """
        arrange: given the harnessed charm
        act: when the service hostname isn't changed and the scan for TLS updates is done
        assert: there are no TLS certificates to revoke
        """
        with mock.patch.object(kubernetes.client, "NetworkingV1Api") as mock_networking_v1_api:
            tls_rel = TLSRelationService(self.harness.charm.model)
            service_hostname = "to-be-removed.local"
            mock_ingress = mock.Mock()
            mock_ingress.spec.rules = [
                kubernetes.client.V1IngressRule(
                    host="to-be-removed.local",
                )
            ]
            mock_ingresses = (
                mock_networking_v1_api.return_value.list_namespaced_ingress.return_value
            )
            mock_ingresses.items = [mock_ingress]
            tls_certificates_relation = MagicMock()
            unit_name = self.harness.charm.unit
            tls_certificates_relation.return_value.data[unit_name].return_value = {"csr": "csr"}
            result = tls_rel.update_cert_on_service_hostname_change(
                [service_hostname], tls_certificates_relation, TEST_NAMESPACE
            )
            assert result == []

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.generate_csr")
    @patch("charm.NginxIngressCharm._update_ingress")
    def test_get_certificate_action(self, mock_update_ingress, mock_gen_csr, mock_get_data):
        """
        arrange: a hostname
        act: when the _on_get_certificate_action method is executed
        assert: the charm gets the certificate appropriately.
        """
        mock_get_data.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        self.harness.set_leader(True)
        _, tls_rel_id, _ = self.set_up_all_relations()
        self.harness.update_relation_data(
            relation_id=tls_rel_id,
            app_or_unit=self.harness.charm.app.name,
            key_values={
                "csr-example.com": "whatever",
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
            },
        )
        self.harness.disable_hooks()

        charm: NginxIngressCharm = typing.cast(NginxIngressCharm, self.harness.charm)

        event = MagicMock(spec=ActionEvent)
        event.params = {
            "hostname": "example.com",
        }
        charm._on_get_certificate_action(event)
        event.set_results.assert_called_with(
            {
                "certificate-example.com": "whatever",
                "ca-example.com": "whatever",
                "chain-example.com": "whatever",
            }
        )

    @pytest.mark.usefixtures("patch_load_incluster_config")
    def test_get_certificate_action_no_relation(self):
        """
        arrange: a hostname
        act: when the _on_get_certificate_action method is executed
        assert: the charm does not get the certificate due to no existing relation.
        """
        self.harness.disable_hooks()

        charm: NginxIngressCharm = typing.cast(NginxIngressCharm, self.harness.charm)

        event = MagicMock(spec=ActionEvent)
        event.params = {
            "hostname": "example.com",
        }
        charm._on_get_certificate_action(event)
        event.set_results.assert_not_called()

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.generate_csr")
    @patch("controller.secret.SecretController._list_resource")
    @patch("controller.secret.SecretController._gen_resource_from_definition")
    def test_define_resource_secret(
        self, mock_gen_res, mock_list, mock_gen_csr, mock_get_data, mock_update
    ):
        """
        arrange: given some resources to define
        act: when the define_resources method is executed
        assert: the define_resources method is executed without errors.
        """
        mock_get_data.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        charm: NginxIngressCharm = typing.cast(NginxIngressCharm, self.harness.charm)
        self.harness.set_leader(True)
        self.set_up_all_relations()
        relation = charm._get_nginx_relation()
        definition = charm._get_definition_from_relation(relation)
        with mock.patch.object(kubernetes.client, "CoreV1Api"):
            secret_controller = SecretController(TEST_NAMESPACE, "nginx-ingress")
            secret_controller.define_resource(definition=definition, key="example.com")
            assert self.harness.model.unit.status.name == ops.MaintenanceStatus().name

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("charm.NginxIngressCharm._update_ingress")
    @patch("tls_relation.TLSRelationService.get_relation_data_field")
    @patch("tls_relation.generate_csr")
    @patch("controller.secret.SecretController._list_resource")
    @patch("controller.secret.SecretController._gen_resource_from_definition")
    def test_cleanup_resources_secret(
        self, mock_gen_res, mock_list, mock_gen_csr, mock_get_data, mock_update
    ):
        """
        arrange: given some resources to clean up
        act: when the cleanup_resources method is executed
        assert: the cleanup_resources method is executed without errors.
        """
        mock_get_data.return_value = "whatever"
        mock_gen_csr.return_value = b"csr"
        self.harness.set_leader(True)
        mock_data_1 = MagicMock()
        mock_data_1.return_value.metadata.name.return_value = "example.com"
        mock_data_2 = MagicMock()
        mock_data_2.return_value.metadata.name.return_value = "example2.com"
        self.set_up_all_relations()
        mock_list.return_value = [mock_data_1, mock_data_2]
        with mock.patch.object(kubernetes.client, "CoreV1Api"):
            secret_controller = SecretController(TEST_NAMESPACE, "nginx-ingress")
            secret_controller.cleanup_resources(exclude=mock_data_2)
            assert self.harness.model.unit.status.name == ops.MaintenanceStatus().name

    @pytest.mark.usefixtures("patch_load_incluster_config")
    @patch("tls_relation.TLSRelationService._get_private_key")
    def test_get_decrypted_keys(self, mock_get_private_key):
        """
        arrange: given a list of encrypted private keys stored on disk with their passwords.
        act: when the get_decrypted_keys method is executed
        assert: the decrypted private keys returned matched decrypted private keys stored on disk.
        """
        passwords = ["password1", "password2"]
        domains = ["domain1", "domain2"]
        test_file_path = os.path.join(os.getcwd(), "tests", "files")
        encrypted_private_keys = [
            open(os.path.join(test_file_path, f"test_encrypted_private_key{i+1}.pem")).read()
            for i in range(len(domains))
        ]

        self.harness.charm._tls.keys = {
            domains[i]: encrypted_private_keys[i] for i in range(len(domains))
        }

        side_effect = [
            {"key": encrypted_private_keys[i], "password": passwords[i]}
            for i in range(len(domains))
        ]
        mock_get_private_key.side_effect = side_effect

        decrypted_private_keys = self.harness.charm._tls.get_decrypted_keys()

        assert len(decrypted_private_keys) == len(domains)

        decrypted_private_keys_from_disk = {
            domains[i]: open(os.path.join(test_file_path, f"test_private_key{i+1}.pem")).read()
            for i in range(len(domains))
        }

        assert decrypted_private_keys == decrypted_private_keys_from_disk
