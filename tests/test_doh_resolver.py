import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.database import _create_doh_connection, create_database_engine
from app.services.doh_resolver import DohResolutionError, DohResolver


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    responses = []
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, *_args, **_kwargs):
        type(self).calls += 1
        return type(self).responses.pop(0)


def test_doh_resolves_multiple_addresses_and_caches_until_ttl(monkeypatch):
    _Client.calls = 0
    _Client.responses = [
        _Response(
            {
                "Status": 0,
                "Answer": [
                    {"type": 1, "TTL": 10, "data": "192.0.2.1"},
                    {"type": 1, "TTL": 20, "data": "192.0.2.2"},
                ],
            }
        )
    ]
    monkeypatch.setattr("app.services.doh_resolver.httpx.Client", _Client)
    now = [100.0]
    resolver = DohResolver(clock=lambda: now[0])

    assert resolver.resolve("example.test") == ("192.0.2.1", "192.0.2.2")
    assert resolver.resolve("example.test") == ("192.0.2.1", "192.0.2.2")
    assert _Client.calls == 1
    now[0] = 111.0
    _Client.responses.append(
        _Response({"Status": 0, "Answer": [{"type": 1, "TTL": 30, "data": "192.0.2.3"}]})
    )
    assert resolver.resolve("example.test") == ("192.0.2.3",)
    assert _Client.calls == 2


def test_doh_follows_cname_to_a_record(monkeypatch):
    _Client.calls = 0
    _Client.responses = [
        _Response({"Status": 0, "Answer": [{"type": 5, "TTL": 30, "data": "alias.test."}]}),
        _Response({"Status": 0, "Answer": [{"type": 1, "TTL": 30, "data": "192.0.2.4"}]}),
    ]
    monkeypatch.setattr("app.services.doh_resolver.httpx.Client", _Client)
    assert DohResolver().resolve("example.test") == ("192.0.2.4",)
    assert _Client.calls == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"Status": 2},
        {"Status": 0, "Answer": [{"type": 1, "TTL": "bad", "data": "192.0.2.1"}]},
        {"Status": 0, "Answer": []},
    ],
)
def test_doh_rejects_malformed_responses(monkeypatch, payload):
    _Client.responses = [_Response(payload)]
    monkeypatch.setattr("app.services.doh_resolver.httpx.Client", _Client)
    with pytest.raises(DohResolutionError):
        DohResolver().resolve("example.test")


def test_doh_timeout_is_sanitized(monkeypatch):
    class TimeoutClient(_Client):
        def get(self, *_args, **_kwargs):
            import httpx

            raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr("app.services.doh_resolver.httpx.Client", TimeoutClient)
    with pytest.raises(DohResolutionError):
        DohResolver().resolve("example.test")


def test_database_dns_workaround_is_rejected_in_production():
    with pytest.raises(ValueError):
        Settings(app_env="production", database_dns_over_https=True)


def test_database_doh_connection_keeps_hostname_for_tls(monkeypatch):
    import psycopg

    captured = {}

    def fake_connect(conninfo, **kwargs):
        captured["conninfo"] = conninfo
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    url = make_url(
        "postgresql+psycopg://user:password@example.test:5432/db?sslmode=require"
    )
    connection = _create_doh_connection(url, type("Resolver", (), {"resolve": lambda _, host: ("192.0.2.5",)})())

    assert connection is not None
    assert "example.test" in captured["conninfo"]
    assert "postgresql+psycopg" not in captured["conninfo"]
    assert "sslmode=require" in captured["conninfo"]
    assert captured["kwargs"] == {"hostaddr": "192.0.2.5"}
