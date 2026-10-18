"""Cloud Run Job entrypoint: process queued submissions until the queue is empty, then exit.

    python -m app.jobs.drain

Cloud Scheduler starts this about once a minute (ADR 0003, deployed in #33). With nothing
queued it exits within seconds. Several runs may overlap; pgmq's visibility timeout
makes sure each message is handled by one run at a time.

Exit code 0 means every message read was handled (done, rejected, retried or failed).
Anything else, such as the database being unreachable, exits non-zero, so the Cloud Run
execution shows up as failed.

Environment (see .env.example): SUPABASE_URL, SUPABASE_SECRET_KEY, SUPABASE_DB_URL.
"""

import logging
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from app.jobs import config
from app.jobs.handler import Outcome, Runner, handle
from app.jobs.process import DEFAULT_ANALYZER
from app.jobs.sandbox import Processed, analyse_upload, run_isolated
from app.jobs.storage import Storage, SupabaseStorage
from app.jobs.store import JobStore, PostgresJobStore

log = logging.getLogger("app.jobs.drain")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    secret_key: str
    db_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        names = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL")
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        return cls(*(os.environ[name] for name in names))


def sandboxed_runner(timeout_s: float = config.JOB_TIMEOUT_S) -> Runner:
    """Validation + pipeline in a child process that's killed after `timeout_s`."""

    def run(data: bytes) -> Processed:
        return run_isolated(analyse_upload, data, DEFAULT_ANALYZER, timeout_s=timeout_s)

    return run


def drain(
    store: JobStore,
    storage: Storage,
    runner: Runner,
    max_run_s: float = config.MAX_RUN_S,
    clock: Callable[[], float] = time.monotonic,
) -> Counter[Outcome]:
    """Handle messages until the queue is empty or `max_run_s` has passed."""
    counts: Counter[Outcome] = Counter()
    started = clock()
    while clock() - started < max_run_s:
        message = store.read_next()
        if message is None:
            break
        counts[handle(message, store, storage, runner)] += 1
    return counts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    with (
        PostgresJobStore.connect(settings.db_url) as store,
        SupabaseStorage(settings.supabase_url, settings.secret_key) as storage,
    ):
        counts = drain(store, storage, sandboxed_runner())
    summary = ", ".join(f"{o.value}={counts[o]}" for o in Outcome) if counts else "queue empty"
    log.info("finished: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
