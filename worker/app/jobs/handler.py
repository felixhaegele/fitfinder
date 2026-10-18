"""One queue message -> one finished (or retried) submission.

Status transitions written here:

    queued --> processing --> done        photo measured, message archived
                          --> rejected    photo unusable, reason shown to the user, archived
                          --> queued      unexpected error: the message comes back after
                                          its visibility timeout (attempt 1 or 2)
                          --> failed      error on the last attempt, or read more than
                                          MAX_ATTEMPTS times (e.g. the worker kept
                                          crashing), archived = dead letter

A rejection is a normal outcome, not an error: it's never retried (ADR 0003). Archived
messages stay in `pgmq.a_submissions`, which doubles as the dead-letter record; a failed
submission's message is found there by its submission id.

If the submission disappears mid-job (the user deleted it or their account, ADR 0006),
the processed copy we just uploaded is deleted again and the message archived.
"""

import logging
from collections.abc import Callable
from enum import StrEnum
from uuid import UUID

from app.jobs import config
from app.jobs.process import Result
from app.jobs.sandbox import Processed, Rejected
from app.jobs.storage import ObjectNotFound, ObjectTooLarge, Storage
from app.jobs.store import FINAL_STATUSES, Finish, FinishOutcome, JobStore, Message, Submission
from app.jobs.validate import MESSAGES, ImageRejectionCode

log = logging.getLogger(__name__)

# Untrusted bytes -> clean copy + outcome. In production: validation and pipeline in a
# child process with a time limit (see drain.py). In tests: a plain function.
Runner = Callable[[bytes], Processed]


class Outcome(StrEnum):
    DONE = "done"
    REJECTED = "rejected"
    RETRY = "retry"
    FAILED = "failed"
    SKIPPED = "skipped"  # nothing to do: bad message, submission gone or already final


def processed_image_path(submission: Submission) -> str:
    """Where the clean copy goes. Convention from the processed_image_path migration."""
    return f"{submission.user_id}/processed/{submission.id}.jpg"


def _submission_id(payload: object) -> UUID | None:
    if not isinstance(payload, dict):
        return None
    try:
        return UUID(str(payload["submission_id"]))
    except (KeyError, ValueError):
        return None


def _rejected(code: ImageRejectionCode, detail: str = "") -> Processed:
    return Processed(None, Rejected(str(code), MESSAGES[code], detail))


def handle(message: Message, store: JobStore, storage: Storage, runner: Runner) -> Outcome:
    submission_id = _submission_id(message.payload)
    if submission_id is None:
        # Can't be fixed by retrying. Archive so it doesn't come back every minute.
        log.error("msg %s: invalid payload, archived", message.msg_id)
        store.archive(message.msg_id)
        return Outcome.SKIPPED

    ctx = f"msg {message.msg_id} submission {submission_id} attempt {message.read_ct}"

    if message.read_ct > config.MAX_ATTEMPTS:
        log.error("%s: more than %d attempts, marked failed", ctx, config.MAX_ATTEMPTS)
        store.fail(message.msg_id, submission_id)
        return Outcome.FAILED

    submission = store.get_submission(submission_id)
    if submission is None or submission.status in FINAL_STATUSES:
        log.info("%s: submission gone or already final, archived", ctx)
        store.archive(message.msg_id)
        return Outcome.SKIPPED

    uploaded: str | None = None
    try:
        store.mark_processing(submission_id)
        processed = _analyse(submission, storage, runner)

        if processed.clean_jpeg is not None:
            uploaded = processed_image_path(submission)
            storage.upload(uploaded, processed.clean_jpeg, "image/jpeg")

        finish = _finish(processed, uploaded)
        written = store.finish(message.msg_id, submission_id, finish)
    except Exception:
        log.exception("%s: attempt failed", ctx)
        if message.read_ct >= config.MAX_ATTEMPTS:
            store.fail(message.msg_id, submission_id)
            _delete_quietly(storage, uploaded, ctx)
            return Outcome.FAILED
        try:
            store.requeue(submission_id)
        except Exception:
            log.exception("%s: couldn't reset status to queued", ctx)
        # Not archived: pgmq makes the message visible again after its timeout.
        return Outcome.RETRY

    if written is FinishOutcome.GONE:
        log.info("%s: submission deleted during the job, removing its files", ctx)
        _delete_quietly(storage, uploaded, ctx)
        return Outcome.SKIPPED
    if written is FinishOutcome.ALREADY_FINAL:
        # Another run finished first and stored the same path; leave its file alone.
        log.info("%s: already finished by another run", ctx)
        return Outcome.SKIPPED

    if isinstance(processed.outcome, Rejected):
        log.info("%s: rejected (%s) %s", ctx, processed.outcome.code, processed.outcome.detail)
        return Outcome.REJECTED
    log.info(
        "%s: done (markers %s, insole %.0f mm2, measurement %s)",
        ctx,
        list(processed.outcome.markers_found),
        processed.outcome.insole_area_mm2,
        "stored" if processed.outcome.measurement else "not wired yet",
    )
    return Outcome.DONE


def _analyse(submission: Submission, storage: Storage, runner: Runner) -> Processed:
    try:
        data = storage.download(submission.image_path, config.MAX_UPLOAD_BYTES)
    except ObjectNotFound:
        # The web app uploads first and inserts the row second, so a missing file means
        # it was deleted or the row was created without one. Retrying won't help.
        return _rejected(ImageRejectionCode.IMAGE_MISSING, submission.image_path)
    except ObjectTooLarge as e:
        return _rejected(ImageRejectionCode.IMAGE_TOO_LARGE, str(e))
    return runner(data)


def _finish(processed: Processed, uploaded: str | None) -> Finish:
    outcome = processed.outcome
    if isinstance(outcome, Result):
        return Finish(
            status="done",
            rejection_reason=None,
            processed_image_path=uploaded,
            measurement=outcome.measurement,
            classification=outcome.classification,
        )
    # Keep the clean copy of a rejected photo: it helps the user see what went wrong.
    return Finish(
        status="rejected", rejection_reason=outcome.message, processed_image_path=uploaded
    )


def _delete_quietly(storage: Storage, path: str | None, ctx: str) -> None:
    if path is None:
        return
    try:
        storage.delete(path)
    except Exception:
        # The file sits in the user's own folder; account deletion's second purge or a
        # manual cleanup removes it.
        log.exception("%s: couldn't delete %s", ctx, path)
