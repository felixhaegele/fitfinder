from typing import Any

import pytest
import sentry_sdk
from sentry_sdk.types import Event

from app.observability import before_send, init_sentry, scrub_string


def test_init_is_skipped_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    assert init_sentry() is False
    assert calls == []


def test_init_with_dsn_never_sends_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    # sentry_sdk.init is replaced, so nothing is initialised and nothing is sent.
    monkeypatch.setenv("SENTRY_DSN", "https://key@o1.ingest.de.sentry.io/1")
    monkeypatch.setenv("SENTRY_RELEASE", "abc123")
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    assert init_sentry() is True
    (options,) = calls
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"
    assert options["environment"] == "development"
    assert options["release"] == "abc123"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no user rider@example.com", "no user [email]"),
        ("bearer eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", "bearer [jwt]"),
        (
            "http://kong:8000/storage/v1/object/sign/insoles/u1/a.jpg?token=abc",
            "http://kong:8000/storage/v1/object/sign/[Filtered]?token=[Filtered]",
        ),
        (
            "postgresql://postgres:hunter2@127.0.0.1:54322/postgres",
            "postgresql://postgres:[Filtered]@127.0.0.1:54322/postgres",
        ),
    ],
)
def test_scrub_string(text: str, expected: str) -> None:
    assert scrub_string(text) == expected


def test_before_send_removes_personal_data() -> None:
    event: Event = {
        "message": "failed for rider@example.com",
        "user": {"id": "u1", "email": "rider@example.com", "ip_address": "1.2.3.4"},
        "request": {
            "url": "http://worker/jobs?token=secret",
            "data": {"image": "..."},
            "cookies": {"session": "x"},
            "headers": {"Authorization": "Bearer x", "User-Agent": "curl"},
        },
        "extra": {"db_url": "postgresql://u:p@h/db", "count": 2},
    }

    result = before_send(event, {})

    assert result["message"] == "failed for [email]"
    assert result["user"] == {"id": "u1"}
    assert result["request"] == {
        "url": "http://worker/jobs?token=[Filtered]",
        "headers": {"User-Agent": "curl"},
    }
    assert result["extra"] == {"db_url": "[Filtered]", "count": 2}
