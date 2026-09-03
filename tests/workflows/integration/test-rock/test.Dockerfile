# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

FROM scratch
COPY test.txt /test.txt
LABEL org.opencontainers.image.title="operator-workflows-test"
