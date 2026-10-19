"""The Cloud Run Job loop: drain the queue, then stop."""

from collections.abc import Iterator

import pytest

from app.jobs.drain import Settings, drain
from app.jobs.handler import Outcome
from app.jobs.sandbox import Processed
from app.jobs.store import Message
from tests.jobs_fakes import FakeStorage, FakeStore, done, rejected


def runner_for(*results: Processed) -> Iterator[Processed]:
    yield from results


def test_drains_until_the_queue_is_empty() -> None:
    store, storage = FakeStore(), FakeStorage()
    ids = [store.add() for _ in range(3)]
    for i, sid in enumerate(ids):
        storage.files[store.rows[sid].image_path] = b"photo"
        store.queue.append(Message(i, 1, {"submission_id": str(sid)}))
    results = runner_for(done(), rejected(), done())

    counts = drain(store, storage, lambda data: next(results))

    assert counts == {Outcome.DONE: 2, Outcome.REJECTED: 1}
    assert store.queue == []
    assert store.archived == [0, 1, 2]


def test_empty_queue_exits_immediately() -> None:
    assert drain(FakeStore(), FakeStorage(), lambda data: done()) == {}


def test_stops_taking_messages_after_the_run_limit() -> None:
    store = FakeStore()
    store.queue = [Message(i, 1, {}) for i in range(5)]
    ticks = iter([0.0, 1.0, 2.0, 100.0])

    counts = drain(
        store, FakeStorage(), lambda data: done(), max_run_s=10, clock=lambda: next(ticks)
    )

    assert counts == {Outcome.SKIPPED: 2}
    assert len(store.queue) == 3  # left for the next scheduled run


def test_settings_require_all_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_DB_URL", "")

    with pytest.raises(RuntimeError, match="SUPABASE_SECRET_KEY, SUPABASE_DB_URL"):
        Settings.from_env()


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://localhost/db")

    assert Settings.from_env() == Settings(
        "http://127.0.0.1:54321", "sb_secret_x", "postgresql://localhost/db"
    )
