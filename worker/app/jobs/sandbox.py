"""Validate + measure one upload, in a child process with a time limit.

Why a separate process? Decoding and measuring happen inside C code (Pillow, OpenCV).
Python can't interrupt a running C call: neither a timer signal nor a thread stops it.
A child process can always be killed. So a hostile or just unlucky photo that makes a
decoder spin, or crashes it outright, costs one failed attempt instead of a hung job.

This is about time limits and crashes, not a security boundary: the child runs as the
same user with the same environment as the parent.
"""

import multiprocessing
import multiprocessing.connection
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.jobs.process import DEFAULT_ANALYZER, Analyzer, Result, process
from app.jobs.validate import InvalidImage, clean_image
from app.pipeline.rejections import Rejection


@dataclass(frozen=True)
class Rejected:
    """A photo we won't measure, with the message shown to the user."""

    code: str
    message: str
    # For logs only.
    detail: str = ""


@dataclass(frozen=True)
class Processed:
    # Clean JPEG for the UI; None if the upload wasn't a usable image at all.
    clean_jpeg: bytes | None
    outcome: Result | Rejected


class JobTimeoutError(Exception):
    pass


class JobCrashedError(Exception):
    pass


def analyse_upload(data: bytes, analyze: Analyzer = DEFAULT_ANALYZER) -> Processed:
    """Untrusted bytes -> clean copy + pipeline outcome. Runs inside the child process."""
    try:
        clean = clean_image(data)
    except InvalidImage as e:
        return Processed(None, Rejected(str(e.code), e.message, e.detail))

    bgr = np.ascontiguousarray(clean.rgb[:, :, ::-1])  # OpenCV expects BGR
    outcome = process(bgr, analyze)
    if isinstance(outcome, Rejection):
        return Processed(clean.jpeg, Rejected(str(outcome.code), outcome.message, outcome.detail))
    return Processed(clean.jpeg, outcome)


def _child(conn: multiprocessing.connection.Connection, fn: Callable[..., Any], args: Any) -> None:
    try:
        conn.send(("ok", fn(*args)))
    except BaseException as e:
        conn.send(("error", f"{type(e).__name__}: {e}"))
    finally:
        conn.close()


def run_isolated[T](fn: Callable[..., T], *args: Any, timeout_s: float) -> T:
    """Run `fn(*args)` in a fresh process. Kill it after `timeout_s` seconds.

    `fn` and its arguments must be picklable (module-level functions, plain data).
    Raises JobTimeoutError if it ran too long and JobCrashedError if it raised or died.
    """
    # "spawn" starts a clean interpreter instead of copying this one (fork). Slower to
    # start (~1 s to import OpenCV) but safe with threads and the same on macOS and Linux.
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    child = ctx.Process(target=_child, args=(sender, fn, args), daemon=True)
    child.start()
    sender.close()  # our copy; now recv() sees EOF if the child dies without sending
    try:
        if not receiver.poll(timeout_s):
            raise JobTimeoutError(f"no result after {timeout_s} s")
        try:
            status, payload = receiver.recv()
        except EOFError as e:
            raise JobCrashedError("child process died without a result") from e
    finally:
        child.join(timeout=1)  # a child that sent its result exits by itself
        if child.is_alive():
            child.kill()
            child.join()
        receiver.close()
    if status != "ok":
        raise JobCrashedError(str(payload))
    result: T = payload
    return result
