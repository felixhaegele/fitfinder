# 0003. Queue submissions with pgmq and drain them with a scheduled job

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

Measuring an insole photo takes seconds and needs Python + OpenCV, so it runs in a separate worker, not in the web request (ADR 0002). We need:

1. A reliable hand-off from "user created a submission" to "worker processes it". No submission may be silently forgotten, and a crash halfway must lead to a retry, not a lost job.
2. A way for the worker to *notice* new work. The worker runs on Cloud Run, which can scale to zero, so it can't simply sit and listen for free.

ADR 0002 already chose pgmq (a queue inside Postgres) over a separate queue service. This ADR settles the details and how the worker gets triggered.

## Decision

**Queue.** We will use a pgmq queue named `submissions`. An `AFTER INSERT` trigger on `public.submissions` sends one message `{"submission_id": "<uuid>"}` in the same transaction as the insert. The message carries only the id; the worker loads the current row, so a message never holds stale data.

**Retries.** The worker reads with a visibility timeout: a message it has read is hidden from other readers for that time. On success the worker archives the message. If the worker crashes, the message becomes visible again and is retried. When a message's `read_ct` exceeds **3**, the worker archives it and sets the submission to `failed`. A photo the pipeline *rejects* (markers not found, too blurry, …) is a normal outcome (`rejected` with a reason), not a retry.

**Triggering the worker (option C).** Cloud Scheduler starts a **Cloud Run Job** once a minute. The job reads messages until the queue is empty, processes them, and exits. When there's nothing to do, it starts, finds an empty queue and exits within seconds.

**Access.** The `pgmq` schema isn't exposed to `anon` / `authenticated`. Only the trigger (security definer) and the worker's database connection use the queue.

## Alternatives considered

- **A. Always-on worker polling the queue:** simplest code and lowest latency, but a Cloud Run instance must run all the time (min-instances = 1), which costs money every hour for a hobby-scale workload.
- **B. Database wakes the worker (`pg_net` HTTP call from the trigger) + `pg_cron` safety net every minute:** results within seconds and scales to zero, but needs the worker URL and a shared secret in Supabase Vault, an authenticated HTTP endpoint on the worker, and a cron job in the database. Not ruled out, just more moving parts than v1 needs. Tracked as a follow-up in #42.
- **Polling `submissions` with `SELECT … FOR UPDATE SKIP LOCKED` instead of pgmq:** works, but we'd re-implement visibility timeouts, retry counts and archiving that pgmq already provides.

## Consequences

- Users wait **up to about a minute** before processing starts. The status page (#30) must make "queued" feel normal (e.g. "usually ready within a minute or two").
- The worker's production entry point is a **batch command** ("drain the queue, then exit") run as a Cloud Run Job, not an HTTP server. The FastAPI app stays for local development and as the starting point for option B.
- Cloud Scheduler + Cloud Run Job are added to the deploy work (#33). The job runs ~1,440 times a day; each run that finds an empty queue only costs a few seconds of CPU, so cost should stay close to the free tier, but we should check the bill after the first month.
- Moving to option B later changes only *how the worker is started*. The queue, message format and retry rules stay the same.
- Messages are archived (not deleted) after processing, so `pgmq.a_submissions` grows over time. Fine at our volume; prune it when it matters.
