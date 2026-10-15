# 0002. Initial architecture

- **Status:** Accepted
- **Date:** 2026-10-15

## Context

FitFinder v1 must:

1. Let a user upload a photo of a shoe insole lying on a printed A4 template, together with shoe model, size and year.
2. Measure the insole in millimetres (length, ball / heel / arch width, toe-box shape) and classify it by foot shape.
3. Let anyone browse and search shoes by fit.

Constraints:

- **Computer vision** needs Python and OpenCV (ArUco marker detection, homography, contour analysis). Processing takes seconds, not milliseconds, so it should not block a web request.
- **Privacy:** photos are personal data under GDPR and the Swiss FADP. They need EU hosting, private storage, consent and deletion.
- **Solo developer, learning project:** prefer managed services, a free or near-free tier at low volume, and boring, well-documented tools.
- **Future (v3):** smartphone foot scans. Raw images, measurements and classifier output must stay separate so they can be re-processed.

## Decision

We will use four parts, in one monorepo:

```
web (Next.js, Vercel) ──► Supabase (Auth, Storage, Postgres, pgmq queue)
                                   │ job: submission_created
                                   ▼
                     worker (Python, FastAPI + OpenCV, Docker, Cloud Run)
```

- **Web: Next.js (App Router, TypeScript) on Vercel.** It is the default React framework, Vercel offers zero-config deploys with a preview URL per PR, and it can do server-side rendering for the searchable shoe catalogue.
- **Backend-as-a-service: Supabase**, in an EU region. One managed product gives us:
  - Postgres as the system of record, with **Row-Level Security** so the browser can query the database directly and still only see what it's allowed to.
  - Auth (email magic link).
  - Storage, with a private bucket for raw photos accessed via signed URLs.
  - **pgmq**, a message queue implemented *inside* Postgres. Inserting a submission enqueues a job in the same transaction, so a submission can't exist without its job, and there is no separate queue infrastructure to run.
- **Worker: Python 3.12 + FastAPI + OpenCV in a Docker container on Google Cloud Run** (EU region). The worker reads jobs from the queue, downloads the image, runs the measurement pipeline and writes results back. Cloud Run runs containers on demand and scales to zero, so we pay roughly nothing when idle. Docker makes the OpenCV native dependencies reproducible.
- **Data model separation:** `submissions` (raw upload and metadata), `measurements` (mm values from a given pipeline version) and `classifications` (with `classifier_version`) are separate tables, so we can re-run measurement or classification without touching the originals.
- **Monorepo** (`web/`, `worker/`, `supabase/`, `print/`, `infra/`). One PR can change the schema, the worker and the UI together, and CI uses path filters so each package is only built when it changes.

## Alternatives considered

- **Supabase Edge Functions for measurement:** they run Deno/TypeScript with tight CPU and time limits, and OpenCV isn't practically available there.
- **Run CV inside a Next.js API route on Vercel:** this runs Node rather than Python, has function size and time limits, and would tie long jobs to user requests.
- **Separate queue (Redis/BullMQ, Google Pub/Sub, SQS):** it would be one more service to run and secure, and enqueueing could not share a transaction with the insert. pgmq is enough at our volume. Revisit if throughput demands it.
- **All-Python stack (Django/FastAPI serving the web UI):** one language, but a weaker frontend ecosystem and no preview-per-PR deploys out of the box.
- **Firebase:** it uses a document store rather than relational SQL, and searching and aggregating measurements is far easier in Postgres.
- **Self-hosted VPS:** cheapest at scale, but we would have to handle patching, TLS, backups and uptime ourselves.

## Consequences

- Three vendors (Vercel, Supabase, Google Cloud), each with its own account, secrets and region settings. Region choice must stay EU everywhere.
- Correct RLS policies are security-critical, because the browser talks to Postgres directly. Every table needs RLS plus tests for its policies.
- The worker needs a privileged (service-role) database connection, which must stay server-side.
- Processing is asynchronous, so the UI must show submission status (queued → processing → done / rejected with a reason).
- Local development needs Docker (Supabase CLI stack, worker image).
- Follow-up ADRs expected: queue consumption model, image segmentation approach, deployment (container registry, Workload Identity Federation), Terraform.
