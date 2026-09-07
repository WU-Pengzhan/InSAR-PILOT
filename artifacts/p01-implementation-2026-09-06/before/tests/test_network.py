"""Behavioral tests for NetworkConfig connection-policy resolution."""

from __future__ import annotations

from insar_pilot.download.network import NetworkConfig


def test_normalized_mode_falls_back_to_direct_for_unknown():
    assert NetworkConfig(mode="Manual").normalized_mode() == "manual"
    assert NetworkConfig(mode="ENVIRONMENT").normalized_mode() == "environment"
    assert NetworkConfig(mode="bogus").normalized_mode() == "direct"
    assert NetworkConfig(mode="").normalized_mode() == "direct"


def test_proxy_dict_only_populated_in_manual_mode():
    manual = NetworkConfig(mode="manual", http_proxy=" http://p:1 ", https_proxy="http://p:2")
    assert manual.proxy_dict() == {"http": "http://p:1", "https": "http://p:2"}
    # Direct/environment modes never expose proxies.
    assert NetworkConfig(mode="direct", http_proxy="http://p:1").proxy_dict() == {}
    assert NetworkConfig(mode="environment", http_proxy="http://p:1").proxy_dict() == {}


def test_from_dict_defaults_and_coerces_timeout():
    config = NetworkConfig.from_dict({"mode": "manual", "timeout_seconds": "45"})
    assert config.mode == "manual"
    assert config.timeout_seconds == 45.0
    # Missing keys get defaults; falsy timeout falls back to 20.
    fallback = NetworkConfig.from_dict({"timeout_seconds": 0})
    assert fallback.mode == "direct"
    assert fallback.timeout_seconds == 20.0


def test_to_dict_round_trips_through_from_dict():
    original = NetworkConfig(mode="manual", http_proxy="http://p:1", https_proxy="http://p:2", timeout_seconds=30.0)
    assert NetworkConfig.from_dict(original.to_dict()) == original


def test_session_trust_env_matches_mode():
    assert NetworkConfig(mode="direct").session().trust_env is False
    assert NetworkConfig(mode="environment").session().trust_env is True
    manual = NetworkConfig(mode="manual", https_proxy="http://p:2").session()
    assert manual.trust_env is False
    assert manual.proxies == {"https": "http://p:2"}


def test_describe_reports_each_mode(monkeypatch):
    assert "Direct connection" in NetworkConfig(mode="direct").describe()

    monkeypatch.setenv("HTTPS_PROXY", "http://env-proxy:8080")
    env_text = NetworkConfig(mode="environment").describe()
    assert "environment proxy" in env_text
    assert "http://env-proxy:8080" in env_text

    manual_text = NetworkConfig(mode="manual", https_proxy="http://p:2").describe()
    assert "manual proxy" in manual_text
    assert "http://p:2" in manual_text
