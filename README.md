# FitFinder

FitFinder helps cyclists find shoes that fit. You place a shoe's insole on a printed A4 template, take a photo and enter the shoe model, size and year. FitFinder then measures the insole (length, ball width, heel width, arch width, toe-box shape) and classifies it by foot shape. Over time this builds a searchable database: *which shoes fit a wide forefoot and narrow heel?*

> Status: early bootstrap. See the [project board](https://github.com/users/felixhaegele/projects) and [milestone issues](https://github.com/felixhaegele/fitfinder/issues?q=label%3Aepic).

## How it works

```
web (Next.js, Vercel) ──► Supabase (Auth, Storage, Postgres, pgmq queue)
                                   │ job: submission_created
                                   ▼
                     worker (Python, FastAPI + OpenCV, Docker, Cloud Run)
                     detect ArUco markers → homography → segment insole
                     → measure (mm) → classify → write results to Postgres
```

1. The user prints the template: A4 with four ArUco markers in the corners and a 100 mm ruler.
2. They upload a photo of an insole lying on the template. The image goes to a private storage bucket.
3. A row in `submissions` enqueues a job on a Postgres-native queue (pgmq).
4. The worker finds the markers, corrects perspective so the image is top-down at a fixed pixels-per-mm, segments the insole, measures it and classifies it.
5. Results are written back to Postgres, where the web app shows them and makes them searchable.

Architecture decisions are recorded in [`docs/adr/`](docs/adr/).

## Repository layout

| Path        | What lives there                                                        |
| ----------- | ----------------------------------------------------------------------- |
| `web/`      | Next.js (App Router) frontend, TypeScript strict, Tailwind              |
| `worker/`   | Python 3.12 measurement worker: FastAPI + OpenCV, managed with `uv`     |
| `supabase/` | Supabase CLI project: migrations, seed data, local config               |
| `print/`    | Generator for the printable A4 template (PDF)                           |
| `docs/`     | Architecture Decision Records (ADRs) and notes                          |
| `infra/`    | Terraform for cloud resources (added later)                             |
| `.github/`  | CI workflows, PR / issue templates, Dependabot                          |

## Running locally

Prerequisites (macOS):

```sh
brew install node pnpm uv supabase/tap/supabase
# plus a Docker runtime, e.g. OrbStack (brew install --cask orbstack) or Docker Desktop
cp .env.example .env.local   # then fill in values
```

- **Web:** `cd web && pnpm install && pnpm dev` → http://localhost:3000 ([details](web/README.md))
- **Worker:** `cd worker && uv sync && uv run fastapi dev app/main.py` → http://127.0.0.1:8000/health ([details](worker/README.md))
- **Database:** `supabase start`, then `supabase db reset` *(added in Milestone 3)*

## CI

Every PR runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Path filters run only the jobs for packages that changed: `web` (lint, typecheck, unit + e2e tests), `worker` (ruff, mypy, pytest) and `worker-image` (Docker build + `/health` smoke test). SonarQube Cloud then analyses code quality and coverage. Branch protection requires the single `ci-ok` job, which summarises the others.

## Contributing

- **GitHub Flow:** `main` is always deployable. Every change is a branch plus a pull request linked to an issue, e.g. `feat/12-upload-form` with `Closes #12`.
- **Conventional Commits:** `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `ci:`, `refactor:`. These later drive automated changelogs and releases.
- Before opening a PR, lint, typecheck and tests must pass for every package you touched.
- Non-trivial architecture choices get an ADR. See [ADR 0001](docs/adr/0001-record-architecture-decisions.md).

## Privacy

User photos are personal data under GDPR and the Swiss FADP. Data is hosted in the EU. Uploads require explicit consent, EXIF metadata is stripped, images are never publicly accessible, and users can delete their account and all their images.

## License

[MIT](LICENSE)
