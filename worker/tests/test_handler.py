"""Status transitions, retries and dead-lettering of one queue message (ADR 0003)."""

from uuid import UUID

import pytest

from app.jobs import config
from app.jobs.handler import Outcome, Runner, handle, processed_image_path
from app.jobs.sandbox import JobTimeoutError, Processed
from app.jobs.store import Message
from app.jobs.validate import MESSAGES, ImageRejectionCode
from tests.jobs_fakes import (
    CLASSIFICATION,
    CLEAN_JPEG,
    MEASUREMENT,
    FakeStorage,
    FakeStore,
    done,
    rejected,
)

UPLOAD = b"\xff\xd8\xff untrusted upload"


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def queued(store: FakeStore, storage: FakeStorage, status: str = "queued") -> UUID:
    sid = store.add(status)
    storage.files[store.rows[sid].image_path] = UPLOAD
    return sid


def message(sid: UUID | str, read_ct: int = 1, msg_id: int = 7) -> Message:
    return Message(msg_id=msg_id, read_ct=read_ct, payload={"submission_id": str(sid)})


def returning(processed: Processed) -> Runner:
    def run(data: bytes) -> Processed:
        assert data == UPLOAD
        return processed

    return run


def raising(exc: Exception) -> Runner:
    def run(data: bytes) -> Processed:
        raise exc

    return run


def must_not_run(data: bytes) -> Processed:
    raise AssertionError("the runner must not be called")


def test_success_stores_clean_copy_marks_done_and_archives(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)

    outcome = handle(message(sid), store, storage, returning(done()))

    row = store.rows[sid]
    path = f"{row.user_id}/processed/{sid}.jpg"
    assert outcome is Outcome.DONE
    assert [s for _, s in store.status_history] == ["processing", "done"]
    assert row.processed_image_path == path
    assert storage.files[path] == CLEAN_JPEG
    assert row.rejection_reason is None
    assert row.measurement is None  # this fake result has no measurement
    assert store.archived == [7]


def test_success_writes_measurement_and_classification_when_available(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)

    handle(message(sid), store, storage, returning(done(measured=True)))

    assert store.rows[sid].measurement == MEASUREMENT
    assert store.rows[sid].classification == CLASSIFICATION


def test_rejection_is_final_with_reason_and_keeps_the_clean_copy(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)

    outcome = handle(message(sid), store, storage, returning(rejected()))

    row = store.rows[sid]
    assert outcome is Outcome.REJECTED
    assert row.status == "rejected"
    assert row.rejection_reason == "Too dark."
    assert row.processed_image_path == processed_image_path(
        store.get_submission(sid)  # type: ignore[arg-type]
    )
    assert store.archived == [7]


def test_invalid_upload_is_rejected_without_a_processed_copy(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)

    handle(message(sid), store, storage, returning(rejected(clean=False)))

    assert store.rows[sid].status == "rejected"
    assert store.rows[sid].processed_image_path is None
    assert len(storage.files) == 1  # only the original upload


def test_missing_upload_is_rejected_not_retried(store: FakeStore, storage: FakeStorage) -> None:
    sid = store.add()  # no file in storage

    outcome = handle(message(sid), store, storage, must_not_run)

    assert outcome is Outcome.REJECTED
    assert store.rows[sid].rejection_reason == MESSAGES[ImageRejectionCode.IMAGE_MISSING]
    assert store.archived == [7]


def test_oversized_download_is_rejected(store: FakeStore, storage: FakeStorage) -> None:
    sid = queued(store, storage)
    storage.too_large.add(store.rows[sid].image_path)

    handle(message(sid), store, storage, must_not_run)

    assert store.rows[sid].rejection_reason == MESSAGES[ImageRejectionCode.IMAGE_TOO_LARGE]


@pytest.mark.parametrize("attempt", range(1, config.MAX_ATTEMPTS))
def test_error_before_last_attempt_requeues_without_archiving(
    store: FakeStore, storage: FakeStorage, attempt: int
) -> None:
    sid = queued(store, storage)

    outcome = handle(message(sid, attempt), store, storage, raising(JobTimeoutError("60 s")))

    assert outcome is Outcome.RETRY
    assert [s for _, s in store.status_history] == ["processing", "queued"]
    assert store.archived == []  # pgmq shows it again after the visibility timeout


def test_error_on_last_attempt_marks_failed_and_archives(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)

    outcome = handle(
        message(sid, config.MAX_ATTEMPTS), store, storage, raising(RuntimeError("boom"))
    )

    assert outcome is Outcome.FAILED
    assert store.rows[sid].status == "failed"
    assert store.rows[sid].rejection_reason is None
    assert store.archived == [7]


def test_error_after_upload_on_last_attempt_removes_the_copy(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)
    store.fail_on_finish = True

    outcome = handle(message(sid, config.MAX_ATTEMPTS), store, storage, returning(done()))

    path = processed_image_path(store.get_submission(sid))  # type: ignore[arg-type]
    assert outcome is Outcome.FAILED
    assert storage.deleted == [path]
    assert path not in storage.files


def test_message_read_too_often_is_dead_lettered_without_processing(
    store: FakeStore, storage: FakeStorage
) -> None:
    # E.g. the worker crashed (out of memory) on every previous attempt.
    sid = queued(store, storage, status="processing")

    outcome = handle(message(sid, config.MAX_ATTEMPTS + 1), store, storage, must_not_run)

    assert outcome is Outcome.FAILED
    assert store.rows[sid].status == "failed"
    assert store.archived == [7]


@pytest.mark.parametrize("status", ["done", "rejected", "failed"])
def test_already_final_submission_is_archived_untouched(
    store: FakeStore, storage: FakeStorage, status: str
) -> None:
    sid = queued(store, storage, status=status)

    outcome = handle(message(sid), store, storage, must_not_run)

    assert outcome is Outcome.SKIPPED
    assert store.rows[sid].status == status
    assert store.archived == [7]


def test_deleted_submission_is_archived(store: FakeStore, storage: FakeStorage) -> None:
    outcome = handle(message(UUID(int=1)), store, storage, must_not_run)

    assert outcome is Outcome.SKIPPED
    assert store.archived == [7]


@pytest.mark.parametrize(
    "payload", [None, "x", {}, {"submission_id": "not-a-uuid"}, {"submission_id": 5}]
)
def test_invalid_payload_is_archived(
    store: FakeStore, storage: FakeStorage, payload: object
) -> None:
    outcome = handle(Message(3, 1, payload), store, storage, must_not_run)

    assert outcome is Outcome.SKIPPED
    assert store.archived == [3]


def test_submission_deleted_mid_job_removes_the_uploaded_copy(
    store: FakeStore, storage: FakeStorage
) -> None:
    # ADR 0006: the user deletes their account while the photo is being measured.
    sid = queued(store, storage)
    path = processed_image_path(store.get_submission(sid))  # type: ignore[arg-type]

    def delete_account() -> None:
        del store.rows[sid]

    store.before_finish = delete_account
    outcome = handle(message(sid), store, storage, returning(done()))

    assert outcome is Outcome.SKIPPED
    assert storage.deleted == [path]
    assert path not in storage.files
    assert store.archived == [7]


def test_finished_by_another_run_keeps_the_shared_file(
    store: FakeStore, storage: FakeStorage
) -> None:
    sid = queued(store, storage)

    def other_run_finishes() -> None:
        store.rows[sid].status = "done"

    store.before_finish = other_run_finishes
    outcome = handle(message(sid), store, storage, returning(done()))

    assert outcome is Outcome.SKIPPED
    assert storage.deleted == []
    assert store.archived == [7]
