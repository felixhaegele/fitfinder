"""End to end against the local Supabase stack: enqueue -> drain -> rows and files.

Runs only when the stack is up and these are set (values from `supabase status`):

    SUPABASE_URL=http://127.0.0.1:54321
    SUPABASE_SECRET_KEY=sb_secret_...
    SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

Otherwise (e.g. in CI's `worker` job, which has no database) the tests are skipped.
CI runs them in the `supabase` job with REQUIRE_SUPABASE=1: there, an unreachable stack
fails the run instead, because a skipped module would look like a pass.

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
from pathlib import Path
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
from app.pipeline import config as pipeline_config
from tests.regression import TOLERANCE_MM, Fixture, load_fixture, render_fixture

ENV = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL")


def _stack_available() -> bool:
    if not all(os.environ.get(name) for name in ENV):
        return False
    try:
        psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=2).close()
    except psycopg.OperationalError:
        return False
    return True


_STACK_AVAILABLE = _stack_available()
if os.environ.get("REQUIRE_SUPABASE") == "1" and not _STACK_AVAILABLE:
    raise RuntimeError(
        "REQUIRE_SUPABASE=1 but the Supabase stack isn't reachable: set "
        + ", ".join(ENV)
        + " from `supabase status`"
    )

pytestmark = pytest.mark.skipif(
    not _STACK_AVAILABLE, reason="local Supabase stack not running or env not set"
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


FIXTURES = Path(__file__).parent / "fixtures"
LEFT = "left_round_straight"
RIGHT = "right_round_gradient"


def fixture(name: str) -> Fixture:
    return load_fixture(FIXTURES / name)


def photo_jpeg(name: str = RIGHT) -> bytes:
    rendered = render_fixture(fixture(name))
    ok, buf = cv2.imencode(".jpg", rendered.photo.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


@pytest.mark.parametrize("name", [LEFT, RIGHT])
def test_drain_measures_and_classifies(stack: Stack, name: str) -> None:
    """Photo -> queue -> worker -> measurements + classifications rows (#84)."""
    sid = stack.submit(photo_jpeg(name))

    drain(stack.store, stack.storage, sandboxed_runner())

    assert stack.submission(sid)["status"] == "done"
    rows = stack.conn.execute(
        "select m.*, c.classifier_version, c.width_class, c.arch_class, c.toe_box_shape,"
        " c.toe_shape from public.measurements m"
        " join public.classifications c on c.measurement_id = m.id"
        " where m.submission_id = %s",
        (sid,),
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    expected = fixture(name)
    assert row["pipeline_version"] == pipeline_config.PIPELINE_VERSION
    assert row["classifier_version"] == pipeline_config.CLASSIFIER_VERSION
    assert row["side"] == expected.shape.side
    for key in ("length_mm", "heel_width_mm", "arch_width_mm", "ball_width_mm"):
        assert abs(float(row[key]) - expected.expected.measurements[key]) <= TOLERANCE_MM[key]
    outline = row["outline_mm"]
    assert len(outline) == 256
    assert outline[0] == [0, 0]
    assert set(row["extra"]) == {"toe_width_85_mm", "toe_width_90_mm", "toe_width_95_mm"}
    assert float(row["toe_taper"]) == pytest.approx(
        row["extra"]["toe_width_90_mm"] / float(row["ball_width_mm"]), abs=1e-4
    )
    for key, label in expected.expected.classes.items():
        assert row[key] == label, key


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
    # Every required column must be one the worker writes. A migration that adds another
    # one (as #52 did) fails here instead of failing every insert in production.
    assert not _unknown_required_columns(
        stack.conn,
        "measurements",
        {"submission_id", "pipeline_version", "side", "outline_mm"}
        | {"length_mm", "ball_width_mm", "heel_width_mm", "arch_width_mm"},
    )
    assert not _unknown_required_columns(
        stack.conn,
        "classifications",
        {"measurement_id", "classifier_version", "width_class", "arch_class"}
        | {"toe_box_shape", "toe_shape"},
    )
    sid = stack.submit(photo_jpeg())
    message = stack.store.read_next()
    assert message is not None
    finish = Finish(
        status="done",
        rejection_reason=None,
        processed_image_path=f"{stack.user_id}/processed/{sid}.jpg",
        measurement=MeasurementRow(
            pipeline_version="it-1",
            side="left",
            length_mm=271.5,
            ball_width_mm=101.2,
            heel_width_mm=66.0,
            arch_width_mm=80.4,
            outline_mm=((0.0, 0.0), *((float(i), float(i)) for i in range(1, 256))),
            toe_taper=0.42,
            extra={"k": 1},
        ),
        classification=ClassificationRow("it-1", "regular", "medium", "round", "roman"),
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
