# worker

Python 3.12 measurement worker: FastAPI + OpenCV, dependencies managed with `uv`, tests with pytest.
It consumes jobs from the Supabase `submissions` queue, measures the insole photo and writes results to Postgres.

Scaffolded in Milestone 2; the measurement pipeline arrives in Milestone 5. See the root [README](../README.md).
