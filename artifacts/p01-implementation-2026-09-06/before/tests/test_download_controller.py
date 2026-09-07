"""Tests for the data-download controller helpers."""

from __future__ import annotations

import pytest

from insar_pilot.ui.controllers.download_controller import (
    DownloadController,
    message_references_host,
)

CMR = "cmr.earthdata.nasa.gov"


@pytest.mark.parametrize(
    "message",
    [
        # requests connection-pool error (the common real-world shape).
        "HTTPSConnectionPool(host='cmr.earthdata.nasa.gov', port=443): Max retries exceeded",
        # A full failing URL embedded in the message.
        "Max retries exceeded with url: https://cmr.earthdata.nasa.gov/search/granules.json",
        # curl/resolver style standalone host token.
        "Could not resolve host: cmr.earthdata.nasa.gov",
    ],
)
def test_message_references_host_accepts_genuine_references(message: str) -> None:
    assert message_references_host(message, CMR) is True


@pytest.mark.parametrize(
    "message",
    [
        # Bypass attempt: trusted host smuggled into an attacker URL's query.
        "connection to https://evil.com/?cmr.earthdata.nasa.gov failed",
        # Bypass attempt: trusted host as a prefix of a look-alike domain.
        "HTTPSConnectionPool(host='cmr.earthdata.nasa.gov.evil.com', port=443): boom",
        # Bypass attempt: trusted host inside an attacker URL path.
        "failed to reach https://evil.com/cmr.earthdata.nasa.gov/x",
        # Unrelated failure.
        "Read timed out.",
    ],
)
def test_message_references_host_rejects_bypasses(message: str) -> None:
    assert message_references_host(message, CMR) is False


def test_friendly_network_error_adds_cmr_hint_for_real_error() -> None:
    message = "HTTPSConnectionPool(host='cmr.earthdata.nasa.gov', port=443): Max retries exceeded"
    detail = DownloadController._friendly_network_error(message)
    assert "NASA CMR" in detail
    assert detail.startswith(message)


def test_friendly_network_error_ignores_cmr_substring_bypass() -> None:
    message = "connection to https://evil.com/?cmr.earthdata.nasa.gov failed"
    detail = DownloadController._friendly_network_error(message)
    # No CMR hint appended; the message is returned unchanged.
    assert "NASA CMR" not in detail
    assert detail == message
