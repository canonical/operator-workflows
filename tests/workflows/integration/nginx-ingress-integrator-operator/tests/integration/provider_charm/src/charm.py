#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Optional

from charms.tls_certificates_interface.v3.tls_certificates import (
    CertificateCreationRequestEvent,
    TLSCertificatesProvidesV3,
)
from ops.charm import CharmBase, InstallEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from self_signed_certificates import generate_ca, generate_certificate, generate_private_key

CERTIFICATE_VALIDITY = 0.005
CA_COMMON_NAME = "pizza"

logger = logging.getLogger(__name__)


class SampleTLSCertificatesProviderCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.certificates = TLSCertificatesProvidesV3(self, "certificates")
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(
            self.certificates.on.certificate_creation_request,
            self._on_certificate_creation_request,
        )

    @property
    def _self_signed_ca_certificate(self) -> str:
        return self._get_value_from_relation_data("self_signed_ca_certificate") or ""

    @property
    def _self_signed_ca_private_key(self) -> Optional[str]:
        return self._get_value_from_relation_data("self_signed_ca_private_key")

    @property
    def _self_signed_root_certificates_are_stored(self) -> bool:
        """Returns whether self-signed certificates are stored in relation data.

        Returns:
            bool: Whether all certificates are set.
        """
        replicas = self.model.get_relation("replicas")
        if not replicas:
            logger.info("Replicas relation not created")
            return False
        if not self._self_signed_ca_certificate:
            logger.info("CA Certificate not stored")
            return False
        if not self._self_signed_ca_private_key:
            logger.info("CA Private key not stored")
            return False
        return True

    @property
    def _replicas_relation_created(self) -> bool:
        return self._relation_created("replicas")

    def _store_self_signed_ca_certificate(self, certificate: str) -> None:
        self._store_item_in_peer_relation_data(key="self_signed_ca_certificate", value=certificate)

    def _store_self_signed_ca_private_key(self, private_key: str) -> None:
        self._store_item_in_peer_relation_data(key="self_signed_ca_private_key", value=private_key)

    def _store_item_in_peer_relation_data(self, key: str, value: str) -> None:
        """Stores key/value in peer relation data.

        Args:
            key (str): Relation data key
            value (str): Relation data value

        Returns:
            None
        """
        peer_relation = self.model.get_relation("replicas")
        if not peer_relation:
            raise RuntimeError("No peer relation")
        peer_relation.data[self.app].update({key: value.strip()})

    def _relation_created(self, relation_name: str) -> bool:
        """Returns whether given relation was created.

        Args:
            relation_name (str): Relation name

        Returns:
            bool: True/False
        """
        try:
            return bool(self.model.relations[relation_name])
        except KeyError:
            return False

    def _get_value_from_relation_data(self, key: str) -> Optional[str]:
        """Returns value from relation data.

        Args:
            key (str): Relation data key

        Returns:
            str: Relation data value
        """
        replicas = self.model.get_relation("replicas")
        if not replicas:
            return None
        relation_data = replicas.data[self.app].get(key, None)
        if relation_data:
            return relation_data.strip()
        return None

    def _generate_self_signed_certificates(self, certificate_signing_request: str) -> str:
        """Generates self-signed certificates.

        Args:
            certificate_signing_request (str): Certificate signing request

        Returns:
            str: Certificate
        """
        if not self._self_signed_ca_private_key:
            raise ValueError("CA Private key not stored")
        if not self._self_signed_ca_certificate:
            raise ValueError("CA Certificate not stored")
        certificate = generate_certificate(
            ca=self._self_signed_ca_certificate.encode(),
            ca_key=self._self_signed_ca_private_key.encode(),
            csr=certificate_signing_request.encode(),
            validity=CERTIFICATE_VALIDITY,
        )
        logger.info("Generated self-signed certificates")
        return certificate.decode()

    def _generate_root_certificates(self) -> None:
        """Generates root certificate to be used to sign certificates.

        Returns:
            None
        """
        private_key = generate_private_key()
        ca_certificate = generate_ca(private_key=private_key, subject=CA_COMMON_NAME)
        self._store_self_signed_ca_certificate(ca_certificate.decode())
        self._store_self_signed_ca_private_key(private_key.decode())
        logger.info("Root certificates generated and stored.")

    def _on_install(self, event: InstallEvent) -> None:
        """Triggered on InstallEvent.

        Args:
            event (InstallEvent): Juju event.

        Returns:
            None
        """
        if not self._replicas_relation_created:
            self.unit.status = WaitingStatus("Replicas relation not yet created")
            event.defer()
            return
        if self.unit.is_leader():
            self._generate_root_certificates()
        self.unit.status = BlockedStatus("Waiting for relation to be created")

    def _on_certificate_creation_request(self, event: CertificateCreationRequestEvent) -> None:
        logger.info("Received Certificate Creation Request")
        if not self.unit.is_leader():
            return
        replicas_relation = self.model.get_relation("replicas")
        if not replicas_relation:
            self.unit.status = WaitingStatus("Waiting for peer relation to be created")
            event.defer()
            return
        if not self._self_signed_root_certificates_are_stored:
            self.unit.status = WaitingStatus("Root Certificates are not yet set")
            event.defer()
            return
        certificate = self._generate_self_signed_certificates(event.certificate_signing_request)
        ca_chain = [self._self_signed_ca_certificate, certificate]
        self.certificates.set_relation_certificate(
            certificate_signing_request=event.certificate_signing_request,
            certificate=certificate,
            ca=self._self_signed_ca_certificate,
            chain=ca_chain,
            relation_id=event.relation_id,
            recommended_expiry_notification_time=0,
        )
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(SampleTLSCertificatesProviderCharm)
