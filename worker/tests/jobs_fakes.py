"""In-memory stand-ins for the database and Storage, for handler and drain tests.

They follow the same rules as the real ones (conditional status updates, finish + archive
together), so the tests check the handler's decisions, not SQL. The SQL itself is
covered by the integration test against the local Supabase stack.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.jobs.process import ClassificationRow, MeasurementRow, Result
from app.jobs.sandbox import Processed, Rejected
from app.jobs.storage import ObjectNotFound, ObjectTooLarge
from app.jobs.store import FINAL_STATUSES, Finish, FinishOutcome, Message, Submission


@dataclass
class Row:
    user_id: UUID
    image_path: str
    status: str = "queued"
    rejection_reason: str | None = None
    processed_image_path: str | None = None
    measurement: MeasurementRow | None = None
    classification: ClassificationRow | None = None


@dataclass
class FakeStore:
    rows: dict[UUID, Row] = field(default_factory=dict)
    queue: list[Message] = field(default_factory=list)
    archived: list[int] = field(default_factory=list)
    status_history: list[tuple[UUID, str]] = field(default_factory=list)
    # Called inside finish(), before the row is locked: simulates a concurrent deletion.
    before_finish: Any = None
    fail_on_finish: bool = False

    def add(self, status: str = "queued") -> UUID:
        sid, uid = uuid4(), uuid4()
        self.rows[sid] = Row(user_id=uid, image_path=f"{uid}/{sid}.jpg", status=status)
        return sid

    def _set(self, sid: UUID, status: str) -> None:
        self.rows[sid].status = status
        self.status_history.append((sid, status))

    def read_next(self) -> Message | None:
        return self.queue.pop(0) if self.queue else None

    def archive(self, msg_id: int) -> None:
        self.archived.append(msg_id)

    def get_submission(self, submission_id: UUID) -> Submission | None:
        row = self.rows.get(submission_id)
        if row is None:
            return None
        return Submission(submission_id, row.user_id, row.image_path, row.status)

    def mark_processing(self, submission_id: UUID) -> None:
        if self.rows[submission_id].status == "queued":
            self._set(submission_id, "processing")

    def requeue(self, submission_id: UUID) -> None:
        if self.rows[submission_id].status == "processing":
            self._set(submission_id, "queued")

    def finish(self, msg_id: int, submission_id: UUID, finish: Finish) -> FinishOutcome:
        if self.before_finish:
            self.before_finish()
        if self.fail_on_finish:
            raise ConnectionError("database went away")
        row = self.rows.get(submission_id)
        if row is None or row.status in FINAL_STATUSES:
            self.archive(msg_id)
            return FinishOutcome.GONE if row is None else FinishOutcome.ALREADY_FINAL
        self._set(submission_id, finish.status)
        row.rejection_reason = finish.rejection_reason
        row.processed_image_path = finish.processed_image_path
        row.measurement = finish.measurement
        row.classification = finish.classification
        self.archive(msg_id)
        return FinishOutcome.WRITTEN

    def fail(self, msg_id: int, submission_id: UUID) -> None:
        row = self.rows.get(submission_id)
        if row is not None and row.status not in FINAL_STATUSES:
            self._set(submission_id, "failed")
            row.rejection_reason = None
        self.archive(msg_id)


@dataclass
class FakeStorage:
    files: dict[str, bytes] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    too_large: set[str] = field(default_factory=set)

    def download(self, path: str, max_bytes: int) -> bytes:
        if path in self.too_large:
            raise ObjectTooLarge(path)
        if path not in self.files:
            raise ObjectNotFound(path)
        return self.files[path]

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        assert content_type == "image/jpeg"
        self.files[path] = data

    def delete(self, path: str) -> None:
        self.deleted.append(path)
        self.files.pop(path, None)


CLEAN_JPEG = b"\xff\xd8\xff clean copy"

MEASUREMENT = MeasurementRow("test-1", 270.0, 100.0, 65.0, 80.0)
CLASSIFICATION = ClassificationRow("test-1", "regular", "medium", "round")


def done(measured: bool = False) -> Processed:
    return Processed(
        CLEAN_JPEG,
        Result(
            measurement=MEASUREMENT if measured else None,
            classification=CLASSIFICATION if measured else None,
            markers_found=(0, 1, 2, 3),
            insole_area_mm2=20_000.0,
        ),
    )


def rejected(clean: bool = True) -> Processed:
    return Processed(CLEAN_JPEG if clean else None, Rejected("too_dark", "Too dark.", "p90=40"))
