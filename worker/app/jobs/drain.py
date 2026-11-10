"""Cloud Run Job entrypoint: process queued submissions until the queue is empty, then exit.

    python -m app.jobs.drain

Cloud Scheduler starts this every few minutes (ADR 0003, deployed in #33; schedule in
infra/variables.tf). Most runs find nothing to do, so main() checks the queue before
loading the measuring pipeline (numpy, OpenCV, Pillow) and the storage client: on a fresh
Cloud Run instance those imports take seconds, and every second is billed. Keep them out
of this module's top-level imports (tests/test_drain.py checks). Several runs may overlap;
pgmq's visibility timeout makes sure each message is handled by one run at a time.

Exit code 0 means every message read was handled (done, rejected, retried or failed).
Anything else, such as the database being unreachable, exits non-zero, so the Cloud Run
execution shows up as failed.

Environment (see .env.example): SUPABASE_URL, SUPABASE_SECRET_KEY, SUPABASE_DB_URL.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.jobs import config
from app.jobs.store import JobStore, Message, PostgresJobStore
from app.observability import init_sentry

if TYPE_CHECKING:
    from app.jobs.handler import Outcome, Runner
    from app.jobs.sandbox import Processed
    from app.jobs.storage import Storage

log = logging.getLogger("app.jobs.drain")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    secret_key: str
    db_url: str

    @classmethod
    def from_env(cls) -> Settings:
        names = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL")
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        return cls(*(os.environ[name] for name in names))


def sandboxed_runner(timeout_s: float = config.JOB_TIMEOUT_S) -> Runner:
    """Validation + pipeline in a child process that's killed after `timeout_s`."""
    from app.jobs.process import DEFAULT_ANALYZER
    from app.jobs.sandbox import analyse_upload, run_isolated

    def run(data: bytes) -> Processed:
        return run_isolated(analyse_upload, data, DEFAULT_ANALYZER, timeout_s=timeout_s)

    return run


def drain(
    store: JobStore,
    storage: Storage,
    runner: Runner,
    max_run_s: float = config.MAX_RUN_S,
    clock: Callable[[], float] = time.monotonic,
    first: Message | None = None,
) -> Counter[Outcome]:
    """Handle messages until the queue is empty or `max_run_s` has passed.

    `first` is a message the caller has already read; it's handled before reading more.
    """
    from app.jobs.handler import handle

    counts: Counter[Outcome] = Counter()
    started = clock()
    message = first
    while clock() - started < max_run_s:
        if message is None:
            message = store.read_next()
            if message is None:
                break
        counts[handle(message, store, storage, runner)] += 1
        message = None
    return counts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_sentry(auto_integrations=False)  # no-op without SENTRY_DSN (#35)
    settings = Settings.from_env()
    with PostgresJobStore.connect(settings.db_url) as store:
        first = store.read_next()
        if first is None:
            log.info("finished: queue empty")
            return 0

        from app.jobs.handler import Outcome
        from app.jobs.storage import SupabaseStorage

        with SupabaseStorage(settings.supabase_url, settings.secret_key) as storage:
            counts = drain(store, storage, sandboxed_runner(), first=first)
    summary = ", ".join(f"{o.value}={counts[o]}" for o in Outcome)
    log.info("finished: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
