"""The Cloud Run Job loop: drain the queue, then stop."""

import logging
import subprocess
import sys
from collections.abc import Iterator
from contextlib import nullcontext
from pathlib import Path

import pytest

from app.jobs import drain as drain_module
from app.jobs import storage as storage_module
from app.jobs.drain import Settings, drain, main
from app.jobs.handler import Outcome
from app.jobs.sandbox import Processed, Rejected
from app.jobs.store import Message, PostgresJobStore
from tests.jobs_fakes import FakeStorage, FakeStore, done, rejected


def runner_for(*results: Processed) -> Iterator[Processed]:
    yield from results


@pytest.fixture
def entrypoint(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeStore, list[FakeStorage]]:
    """main() wired to fakes: no database, no Supabase, no child process."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://localhost/db")
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    store, storages = FakeStore(), []

    def storage_client(url: str, key: str) -> nullcontext[FakeStorage]:
        storages.append(FakeStorage())
        return nullcontext(storages[-1])

    monkeypatch.setattr(PostgresJobStore, "connect", lambda url: nullcontext(store))
    monkeypatch.setattr(storage_module, "SupabaseStorage", storage_client)
    monkeypatch.setattr(drain_module, "sandboxed_runner", lambda: lambda data: done())
    return store, storages


def test_main_exits_on_an_empty_queue_without_the_storage_client(
    entrypoint: tuple[FakeStore, list[FakeStorage]], caplog: pytest.LogCaptureFixture
) -> None:
    _, storages = entrypoint
    caplog.set_level(logging.INFO, logger="app.jobs.drain")

    assert main() == 0
    assert storages == []
    assert caplog.messages == ["finished: queue empty"]


def test_main_handles_queued_work(
    entrypoint: tuple[FakeStore, list[FakeStorage]],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, storages = entrypoint
    sid = store.add()
    store.queue.append(Message(7, 1, {"submission_id": str(sid)}))
    files = {store.rows[sid].image_path: b"photo"}

    def storage_with_photo(url: str, key: str) -> nullcontext[FakeStorage]:
        storages.append(FakeStorage())
        storages[-1].files.update(files)
        return nullcontext(storages[-1])

    monkeypatch.setattr(storage_module, "SupabaseStorage", storage_with_photo)
    caplog.set_level(logging.INFO, logger="app.jobs.drain")

    assert main() == 0
    assert store.archived == [7]
    assert caplog.messages[-1].startswith("finished: done=1, rejected=0")


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


def test_handles_the_message_main_already_read_first() -> None:
    store, storage = FakeStore(), FakeStorage()
    first_id, queued_id = store.add(), store.add()
    for sid in (first_id, queued_id):
        storage.files[store.rows[sid].image_path] = b"photo"
    store.queue.append(Message(1, 1, {"submission_id": str(queued_id)}))

    first = Message(0, 1, {"submission_id": str(first_id)})
    counts = drain(store, storage, lambda data: done(), first=first)

    assert counts == {Outcome.DONE: 2}
    assert store.archived == [0, 1]


def test_sandboxed_runner_rejects_bytes_that_are_no_image() -> None:
    processed = drain_module.sandboxed_runner(timeout_s=30)(b"not a photo")

    assert processed.clean_jpeg is None
    assert isinstance(processed.outcome, Rejected)


def test_importing_the_entrypoint_leaves_the_pipeline_unloaded() -> None:
    # A fresh interpreter, because this test process has long imported everything.
    # Empty runs exit before these load; a new top-level import would undo that.
    heavy = ["cv2", "numpy", "PIL", "httpx", "app.jobs.handler", "app.jobs.process"]
    code = f"import sys, app.jobs.drain; print([m for m in {heavy!r} if m in sys.modules])"
    result = subprocess.run(  # noqa: S603 - fixed command, no user input
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.stdout.strip() == "[]"


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
