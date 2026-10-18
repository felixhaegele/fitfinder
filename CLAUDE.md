# CLAUDE.md — FitFinder

Website that helps cyclists find fitting shoes. Users photograph a shoe's insole on a printed A4 template, enter model / size / year, and the system measures the insole and classifies it by foot shape. This is also a learning project: infrastructure and SDLC matter as much as features.

## Scope

- **v1 (now):** upload insole photo → measure → classify → browse/search shoes by fit.  
- **v2:** crowd data, better classifier, recommendations.  
- **v3 (out of scope):** smartphone foot scan \+ personalized matching. Don't build for it, but don't make data-model choices that block it (keep raw images, measurements and classifier versions separate).

## Architecture

web (Next.js, Vercel) ──► Supabase (Auth, Storage, Postgres, pgmq queue)

                                   │ job: submission\_created

                                   ▼

                     worker (Python, FastAPI \+ OpenCV, Docker, Cloud Run)

                     detect ArUco markers → homography → segment insole

                     → measure (mm) → classify → write results to Postgres

## Repo layout

/web        Next.js (App Router), TypeScript strict, Tailwind, Supabase JS client

/worker     Python 3.12, FastAPI, OpenCV, uv for deps, pytest

/supabase   Supabase CLI project: migrations/, seed.sql, config.toml

/print      Generator for the printable A4 template (ArUco markers \+ scale ruler) → PDF

/infra      Terraform (Cloud Run, Artifact/GHCR, DNS) — added later

/docs       ADRs (docs/adr/NNNN-title.md), architecture notes

.github     workflows/, PR template, issue templates, dependabot.yml

## Commands

\# Database (requires Docker)

supabase start                 \# local stack

supabase db reset              \# re-apply migrations \+ seed

supabase migration new \<name\>  \# never edit an applied migration; add a new one

supabase gen types typescript \--local \> web/src/lib/database.types.ts

\# Web

cd web && pnpm install && pnpm dev

pnpm lint && pnpm typecheck && pnpm test && pnpm test:e2e

\# Worker

cd worker && uv sync && uv run fastapi dev app/main.py

uv run ruff check . && uv run ruff format \--check . && uv run mypy . && uv run pytest

## Conventions

- **Git:** GitHub Flow. Never commit to `main`. One branch \+ PR per issue: `feat/12-upload-form`. Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `ci:`, `refactor:`). Reference the issue in the PR (`Closes #12`). Keep PRs small.  
- **Before opening a PR:** lint, typecheck and tests must pass locally for every package touched.  
- **Database:** every table has Row-Level Security enabled with explicit policies. Schema changes only via migrations. Regenerate TS types after a migration.  
- **Measurements** are stored in millimetres as numeric, with `classifier_version` on every classification row so old submissions can be re-processed.  
- **Images:** strip EXIF before storage. Raw uploads in a private bucket; never public URLs for user images — use signed URLs.  
- **Secrets:** never in code or committed `.env` files. Local: `.env.local` (gitignored); CI: GitHub environment secrets. Update `.env.example` when adding a variable.  
- **Privacy (GDPR / Swiss FADP):** EU region, explicit upload consent, user can delete their account and all images.  
- **Decisions:** non-trivial architecture choices get a short ADR in `docs/adr/`.

## Measurement pipeline notes

- Template: A4 with 4 ArUco markers (DICT\_4X4\_50, IDs 0–3) at known mm positions in the corners. Detect markers → compute homography → warp to a top-down image at a fixed px/mm.  
- Reject photos early with a clear user-facing reason (markers not found, insole touches edge, too blurry, too dark).  
- Measurements v1: length, ball width, heel width, midfoot/arch width, toe-box shape. Classification v1 is rule-based on ratios; keep thresholds in one config file.  
- `worker/tests/fixtures/` holds reference photos with known measurements (`expected.json`). These are regression tests — a change that moves results beyond tolerance must be deliberate.

## Working style for Claude

- For any task larger than a small fix: propose a plan first, then implement.  
- Prefer boring, well-documented tools. Explain *why* when introducing infra concepts — the owner is learning.  
- When a step needs the owner (creating accounts, adding secrets, clicking in a dashboard), stop and list exactly what to do.

## Parallel sessions

The owner often runs several Claude sessions on this repo at once. Each session works in its own git worktree (`.claude/worktrees/<branch>`, gitignored).

- **Claim before you start.** Before starting an issue, check `gh pr list` and `git branch -a`. If a branch or PR for that issue exists, it's taken: ask the owner instead of starting. Once you start, push the branch and open a **draft PR** early, so other sessions can see the issue is in progress.  
- **Stay in your lane.** Never commit to, rebase or delete another session's branch or worktree.  
- **Shared files cause conflicts:** `.github/workflows/ci.yml`, `supabase/config.toml`, `supabase/migrations/`, `.env.example`, lockfiles. Keep changes there small, and rebase on `main` right before merging. Migrations are ordered by timestamp, so if another migration landed on `main` after yours was created, check that yours still applies after it (`supabase db reset`).  
- **Hand-offs go in GitHub.** Write a decision another session depends on (e.g. template marker positions used by the measurement pipeline) in the PR description or an issue comment, not only in chat.  
- **Urgent questions:** other sessions can be reached directly (`ListAgents`, then `SendMessage`). Ask; don't edit their work.  
- **Priorities come from the owner.** If two sessions could take the same next issue, ask.
