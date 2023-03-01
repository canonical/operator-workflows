from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus


class TestUploadCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.unit.status = ActiveStatus()

if __name__ == "__main__":  # pragma: nocover
    main(TestUploadCharm)
