"""Public acquisition provenance excludes fetch URLs and authentication material."""

from typing import Any


def public_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: public_metadata(v)
            for k, v in value.items()
            if k.lower()
            not in {
                "url",
                "download_url",
                "password",
                "token",
                "authorization",
                "cookie",
                "access_token",
                "refresh_token",
                "secret",
                "http_proxy",
                "https_proxy",
            }
        }
    if isinstance(value, (list, tuple)):
        return [public_metadata(v) for v in value]
    return value
