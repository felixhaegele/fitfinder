"""End to end against the local Supabase stack: enqueue -> drain -> rows and files.

Runs only when the stack is up and these are set (values from `supabase status`):

    SUPABASE_URL=http://127.0.0.1:54321
    SUPABASE_SECRET_KEY=sb_secret_...
    SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

Otherwise (e.g. in CI, where the worker job has no database) the tests are skipped.

The local stack may be shared with other work, so the tests never drain the real
`submissions` queue: each test gets its own temporary pgmq queue, and the message the
insert trigger puts on the real queue is removed again right away. Everything created
(user, rows, files, queue) is deleted afterwards.
"""

import io
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import cv2
import psycopg
import pytest
from PIL import Image
from psycopg.rows import dict_row

from app.jobs import config
from app.jobs.drain import drain, sandboxed_runner
from app.jobs.process import ClassificationRow, MeasurementRow
from app.jobs.storage import SupabaseStorage
from app.jobs.store import Finish, FinishOutcome, PostgresJobStore
from tests.regression import measurable_fixtures, render_fixture

ENV = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL")


def _stack_available() -> bool:
    if not all(os.environ.get(name) for name in ENV):
        return False
    try:
        psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=2).close()
    except psycopg.OperationalError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _stack_available(), reason="local Supabase stack not running or env not set"
)

Conn = psycopg.Connection[dict[str, Any]]


@dataclass
class Stack:
    conn: Conn
    store: PostgresJobStore
    storage: SupabaseStorage
    user_id: uuid.UUID
    shoe_model_id: uuid.UUID
    files: list[str]

    def submit(self, photo: bytes) -> uuid.UUID:
        """Upload a photo and create its submission, like the web app does (#28)."""
        sid = uuid.uuid4()
        path = f"{self.user_id}/{sid}.jpg"
        self.storage.upload(path, photo, "image/jpeg")
        self.files += [path, f"{self.user_id}/processed/{sid}.jpg"]
        self.conn.execute(
            "insert into public.submissions (id, user_id, shoe_model_id, size, size_system,"
            " image_path, consent_at, insole_condition)"
            " values (%s, %s, %s, 42, 'eu', %s, now(), 'new')",
            (sid, self.user_id, self.shoe_model_id, path),
        )
        # Keep the shared queue clean; send the job to this test's queue instead.
        self.conn.execute(
            "delete from pgmq.q_submissions where message->>'submission_id' = %s", (str(sid),)
        )
        self.conn.execute(
            "select pgmq.send(%s, %s::jsonb)", (self.store.queue, f'{{"submission_id": "{sid}"}}')
        )
        return sid

    def submission(self, sid: uuid.UUID) -> dict[str, Any]:
        row = self.conn.execute(
            "select status, rejection_reason, processed_image_path"
            " from public.submissions where id = %s",
            (sid,),
        ).fetchone()
        assert row is not None
        return row

    def archived(self) -> int:
        row = self.conn.execute(f"select count(*) as n from pgmq.a_{self.store.queue}").fetchone()  # noqa: S608
        assert row is not None
        return int(row["n"])


@pytest.fixture
def stack() -> Iterator[Stack]:
    conn: Conn = psycopg.connect(
        os.environ["SUPABASE_DB_URL"], autocommit=True, row_factory=dict_row
    )
    queue = f"submissions_test_{uuid.uuid4().hex[:12]}"
    user_id = uuid.uuid4()
    conn.execute("select pgmq.create(%s)", (queue,))
    conn.execute(
        "insert into auth.users (id, email) values (%s, %s)",
        (user_id, f"worker-test-{user_id}@example.com"),
    )
    shoe = conn.execute(
        "insert into public.shoe_models (brand, model, year, created_by)"
        " values ('Worker test', %s, 2026, %s) returning id",
        (str(user_id), user_id),
    ).fetchone()
    assert shoe is not None
    storage = SupabaseStorage(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    s = Stack(conn, PostgresJobStore(conn, queue), storage, user_id, shoe["id"], [])
    try:
        yield s
    finally:
        for path in s.files:
            storage.delete(path)
        conn.execute("delete from auth.users where id = %s", (user_id,))  # cascades
        conn.execute("delete from public.shoe_models where id = %s", (shoe["id"],))
        conn.execute("select pgmq.drop_queue(%s)", (queue,))
        storage.__exit__(None, None, None)
        conn.close()


def photo_jpeg() -> bytes:
    rendered = render_fixture(measurable_fixtures()[0])
    ok, buf = cv2.imencode(".jpg", rendered.photo.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def test_drain_processes_photos_end_to_end(stack: Stack) -> None:
    good = stack.submit(photo_jpeg())
    junk = stack.submit(b"<?php system($_GET['c']); ?>")  # stored as .jpg, isn't one

    counts = drain(stack.store, stack.storage, sandboxed_runner())

    assert sum(counts.values()) == 2
    done = stack.submission(good)
    assert done["status"] == "done"
    assert done["processed_image_path"] == f"{stack.user_id}/processed/{good}.jpg"
    clean = stack.storage.download(done["processed_image_path"], config.MAX_UPLOAD_BYTES)
    assert len(Image.open(io.BytesIO(clean)).getexif()) == 0

    bad = stack.submission(junk)
    assert bad["status"] == "rejected"
    assert "isn't a supported image" in bad["rejection_reason"]
    assert bad["processed_image_path"] is None

    assert stack.archived() == 2
    assert stack.store.read_next() is None


def test_message_read_too_often_is_dead_lettered(stack: Stack) -> None:
    sid = stack.submit(photo_jpeg())
    for _ in range(config.MAX_ATTEMPTS):  # three earlier attempts that crashed
        stack.conn.execute("select * from pgmq.read(%s, 0, 1)", (stack.store.queue,))

    drain(stack.store, stack.storage, sandboxed_runner())

    assert stack.submission(sid)["status"] == "failed"
    assert stack.archived() == 1


def _unknown_required_columns(conn: Conn, table: str, known: set[str]) -> list[str]:
    rows = conn.execute(
        "select column_name from information_schema.columns where table_schema = 'public'"
        " and table_name = %s and is_nullable = 'NO' and column_default is null",
        (table,),
    ).fetchall()
    return sorted({r["column_name"] for r in rows} - known)


def test_finish_writes_measurement_and_classification_rows(stack: Stack) -> None:
    # The local stack may have migrations from other branches applied (e.g. #52 adds
    # required columns). The insert can't succeed until the worker writes those too.
    ahead = _unknown_required_columns(
        stack.conn,
        "measurements",
        {"submission_id", "pipeline_version"}
        | {"length_mm", "ball_width_mm", "heel_width_mm", "arch_width_mm"},
    )
    if ahead:
        pytest.skip(f"local schema is ahead of this branch: measurements{ahead} required")
    sid = stack.submit(photo_jpeg())
    message = stack.store.read_next()
    assert message is not None
    finish = Finish(
        status="done",
        rejection_reason=None,
        processed_image_path=f"{stack.user_id}/processed/{sid}.jpg",
        measurement=MeasurementRow("it-1", 271.5, 101.2, 66.0, 80.4, 0.42, {"k": 1}),
        classification=ClassificationRow("it-1", "regular", "medium", "round"),
    )

    assert stack.store.finish(message.msg_id, sid, finish) is FinishOutcome.WRITTEN
    # A second finish (overlapping run) doesn't overwrite or duplicate anything.
    assert stack.store.finish(message.msg_id, sid, finish) is FinishOutcome.ALREADY_FINAL

    row = stack.conn.execute(
        "select m.length_mm, m.extra, c.width_class from public.measurements m"
        " join public.classifications c on c.measurement_id = m.id"
        " where m.submission_id = %s",
        (sid,),
    ).fetchall()
    assert len(row) == 1
    assert float(row[0]["length_mm"]) == 271.5
    assert row[0]["extra"] == {"k": 1}
    assert row[0]["width_class"] == "regular"
    assert stack.archived() == 1


def test_finish_reports_a_submission_deleted_mid_job(stack: Stack) -> None:
    sid = stack.submit(photo_jpeg())
    message = stack.store.read_next()
    assert message is not None
    stack.conn.execute("delete from public.submissions where id = %s", (sid,))

    outcome = stack.store.finish(message.msg_id, sid, Finish("done", None, None))

    assert outcome is FinishOutcome.GONE
    assert stack.archived() == 1


def test_requeue_and_fail(stack: Stack) -> None:
    sid = stack.submit(photo_jpeg())
    message = stack.store.read_next()
    assert message is not None

    stack.store.mark_processing(sid)
    assert stack.submission(sid)["status"] == "processing"
    stack.store.requeue(sid)
    assert stack.submission(sid)["status"] == "queued"
    stack.store.fail(message.msg_id, sid)
    assert stack.submission(sid) == {
        "status": "failed",
        "rejection_reason": None,
        "processed_image_path": None,
    }
    assert stack.archived() == 1
