from dataclasses import dataclass
import time
from typing import Any

import httpx


class DohResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class _CacheEntry:
    addresses: tuple[str, ...]
    expires_at: float


class DohResolver:
    def __init__(
        self,
        *,
        endpoint: str = "https://dns.google/resolve",
        timeout_seconds: float = 5.0,
        clock: Any = time.monotonic,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self._cache: dict[str, _CacheEntry] = {}

    def resolve(self, hostname: str) -> tuple[str, ...]:
        cached = self._cache.get(hostname)
        now = self._clock()
        if cached is not None and cached.expires_at > now:
            return cached.addresses

        addresses, ttl = self._resolve_name(hostname, set())
        expires_at = now + max(1, ttl)
        self._cache[hostname] = _CacheEntry(addresses, expires_at)
        return addresses

    def _resolve_name(self, hostname: str, visited: set[str]) -> tuple[tuple[str, ...], int]:
        normalized = hostname.rstrip(".").lower()
        if normalized in visited:
            raise DohResolutionError("DNS-over-HTTPS returned a CNAME loop.")
        visited.add(normalized)
        payload = self._query(normalized)
        answers = payload.get("Answer")
        if not isinstance(answers, list):
            raise DohResolutionError("DNS-over-HTTPS returned no DNS answers.")

        addresses = tuple(
            item["data"]
            for item in answers
            if isinstance(item, dict) and item.get("type") == 1 and isinstance(item.get("data"), str)
        )
        if addresses:
            ttls = [item.get("TTL") for item in answers if item.get("type") == 1]
            return addresses, min(_valid_ttl(ttls))

        aliases = [
            item["data"].rstrip(".")
            for item in answers
            if isinstance(item, dict) and item.get("type") == 5 and isinstance(item.get("data"), str)
        ]
        if not aliases:
            raise DohResolutionError("DNS-over-HTTPS returned no IPv4 addresses.")
        return self._resolve_name(aliases[0], visited)

    def _query(self, hostname: str) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(self.endpoint, params={"name": hostname, "type": "A"})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DohResolutionError("DNS-over-HTTPS lookup failed.") from exc
        if not isinstance(payload, dict) or payload.get("Status") != 0:
            raise DohResolutionError("DNS-over-HTTPS returned an unsuccessful status.")
        return payload


def _valid_ttl(values: list[Any]) -> list[int]:
    ttls = [value for value in values if isinstance(value, int) and value >= 0]
    if not ttls:
        raise DohResolutionError("DNS-over-HTTPS returned an invalid TTL.")
    return ttls
