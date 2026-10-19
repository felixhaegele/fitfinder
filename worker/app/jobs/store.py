"""Postgres side of the worker: pgmq messages and submission rows.

`JobStore` is what the handler needs; `PostgresJobStore` implements it with psycopg over
the direct database connection (SUPABASE_DB_URL). Tests use an in-memory fake.

Two rules keep retries correct (ADR 0003):

- **Reads commit immediately** (autocommit). pgmq counts each read in `read_ct`; if the
  read sat in an open transaction and the worker crashed, the count would roll back and
  a poison message could be retried forever.
- **The final write and the archive are one transaction.** Either the result is stored
  and the message is gone, or neither happened and the message comes back for a retry.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.jobs import config
from app.jobs.process import ClassificationRow, MeasurementRow

# Statuses after which a submission is never processed again.
FINAL_STATUSES = frozenset({"done", "rejected", "failed"})


@dataclass(frozen=True)
class Message:
    msg_id: int
    read_ct: int
    payload: Any


@dataclass(frozen=True)
class Submission:
    id: UUID
    user_id: UUID
    image_path: str
    status: str


@dataclass(frozen=True)
class Finish:
    """What to write when a job ends normally."""

    status: str  # "done" or "rejected"
    rejection_reason: str | None
    processed_image_path: str | None
    measurement: MeasurementRow | None = None
    classification: ClassificationRow | None = None


class FinishOutcome(StrEnum):
    WRITTEN = "written"
    # The submission no longer exists (deleted, or its account was).
    GONE = "gone"
    # Another run already finished it (e.g. an overlapping run after a timeout).
    ALREADY_FINAL = "already_final"


class JobStore(Protocol):
    def read_next(self) -> Message | None: ...

    def archive(self, msg_id: int) -> None: ...

    def get_submission(self, submission_id: UUID) -> Submission | None: ...

    def mark_processing(self, submission_id: UUID) -> None: ...

    def requeue(self, submission_id: UUID) -> None: ...

    def finish(self, msg_id: int, submission_id: UUID, finish: Finish) -> FinishOutcome:
        """Write the result and archive the message, atomically."""
        ...

    def fail(self, msg_id: int, submission_id: UUID) -> None:
        """Give up: set `failed` (unless already final) and archive, atomically."""
        ...


def measurement_params(submission_id: UUID, m: MeasurementRow) -> tuple[object, ...]:
    """Parameters for the measurements insert, in column order.

    Pure, so the mapping is unit-tested without a database. The outline goes in as a JSON
    array of [x, y] pairs, which is what the `outline_mm` check constraint expects.
    """
    return (
        submission_id,
        m.pipeline_version,
        m.side,
        m.length_mm,
        m.ball_width_mm,
        m.heel_width_mm,
        m.arch_width_mm,
        Jsonb([[x, y] for x, y in m.outline_mm]),
        m.toe_taper,
        Jsonb(dict(m.extra)),
    )


def classification_params(measurement_id: object, c: ClassificationRow) -> tuple[object, ...]:
    """Parameters for the classifications insert, in column order."""
    return (
        measurement_id,
        c.classifier_version,
        c.width_class,
        c.arch_class,
        c.toe_box_shape,
        c.toe_shape,
    )


class PostgresJobStore:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]], queue: str) -> None:
        self._conn = conn
        self.queue = queue

    @classmethod
    def connect(cls, db_url: str, queue: str = config.QUEUE_NAME) -> Self:
        conn = psycopg.connect(db_url, autocommit=True, row_factory=dict_row)
        return cls(conn, queue)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._conn.close()

    def read_next(self) -> Message | None:
        # One message at a time: with a batch, the later messages' visibility timeout
        # would run down while the earlier ones are processed.
        row = self._conn.execute(
            "select msg_id, read_ct, message from pgmq.read(%s, %s, 1)",
            (self.queue, config.VISIBILITY_TIMEOUT_S),
        ).fetchone()
        if row is None:
            return None
        return Message(msg_id=row["msg_id"], read_ct=row["read_ct"], payload=row["message"])

    def archive(self, msg_id: int) -> None:
        self._conn.execute("select pgmq.archive(%s, %s::bigint)", (self.queue, msg_id))

    def get_submission(self, submission_id: UUID) -> Submission | None:
        row = self._conn.execute(
            "select id, user_id, image_path, status from public.submissions where id = %s",
            (submission_id,),
        ).fetchone()
        return None if row is None else Submission(**row)

    def mark_processing(self, submission_id: UUID) -> None:
        self._conn.execute(
            "update public.submissions set status = 'processing'"
            " where id = %s and status = 'queued'",
            (submission_id,),
        )

    def requeue(self, submission_id: UUID) -> None:
        # Waiting for a retry looks like waiting for the first try to the user.
        self._conn.execute(
            "update public.submissions set status = 'queued'"
            " where id = %s and status = 'processing'",
            (submission_id,),
        )

    def _lock_status(self, submission_id: UUID) -> str | None:
        # FOR UPDATE: an account deletion or an overlapping run has to wait for us, and
        # we see their committed change if they were first.
        row = self._conn.execute(
            "select status from public.submissions where id = %s for update",
            (submission_id,),
        ).fetchone()
        return None if row is None else str(row["status"])

    def finish(self, msg_id: int, submission_id: UUID, finish: Finish) -> FinishOutcome:
        with self._conn.transaction():
            status = self._lock_status(submission_id)
            if status is None or status in FINAL_STATUSES:
                self.archive(msg_id)
                return FinishOutcome.GONE if status is None else FinishOutcome.ALREADY_FINAL

            self._conn.execute(
                "update public.submissions"
                " set status = %s, rejection_reason = %s, processed_image_path = %s"
                " where id = %s",
                (
                    finish.status,
                    finish.rejection_reason,
                    finish.processed_image_path,
                    submission_id,
                ),
            )
            if finish.measurement is not None:
                m = finish.measurement
                row = self._conn.execute(
                    "insert into public.measurements (submission_id, pipeline_version, side,"
                    " length_mm, ball_width_mm, heel_width_mm, arch_width_mm, outline_mm,"
                    " toe_taper, extra)"
                    " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
                    measurement_params(submission_id, m),
                ).fetchone()
                assert row is not None  # noqa: S101 - insert ... returning always returns
                if finish.classification is not None:
                    c = finish.classification
                    self._conn.execute(
                        "insert into public.classifications (measurement_id,"
                        " classifier_version, width_class, arch_class, toe_box_shape, toe_shape)"
                        " values (%s, %s, %s, %s, %s, %s)",
                        classification_params(row["id"], c),
                    )
            self.archive(msg_id)
            return FinishOutcome.WRITTEN

    def fail(self, msg_id: int, submission_id: UUID) -> None:
        with self._conn.transaction():
            status = self._lock_status(submission_id)
            if status is not None and status not in FINAL_STATUSES:
                # No reason text: the schema allows rejection_reason only for 'rejected'.
                # The status page shows a generic message for 'failed'.
                self._conn.execute(
                    "update public.submissions set status = 'failed', rejection_reason = null"
                    " where id = %s",
                    (submission_id,),
                )
            self.archive(msg_id)
