# worker

Python 3.12 measurement worker: FastAPI + OpenCV, dependencies managed with [uv](https://docs.astral.sh/uv/), tests with pytest.
It consumes jobs from the Supabase `submissions` queue, measures the insole photo and writes results to Postgres. The measurement pipeline arrives in Milestone 5.

## Develop

```sh
cd worker
uv sync                               # creates .venv (downloads Python 3.12 if needed)
uv run fastapi dev app/main.py        # http://127.0.0.1:8000/health, auto-reload
```

## Check (same as CI)

```sh
uv run ruff check .                   # lint
uv run ruff format --check .          # formatting (drop --check to fix)
uv run mypy                           # strict type checking
uv run pytest                         # tests + coverage (coverage.xml)
```

## Container

```sh
docker build -t fitfinder-worker .
docker run --rm -p 8080:8080 fitfinder-worker
curl localhost:8080/health
```

The Dockerfile is **multi-stage**. The first stage installs dependencies with uv, and the second copies only the resulting virtualenv and the code into a clean slim image. The final image has no uv or build caches, and it runs as an unprivileged `app` user. Cloud Run supplies `$PORT`, which defaults to 8080.
