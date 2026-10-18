"""HTTP entrypoint for the worker.

Cloud Run needs an HTTP server listening on $PORT; /health lets it (and us)
check that the container started correctly.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from app.observability import init_sentry

# Before creating the app, so the FastAPI integration can hook into it.
init_sentry()

app = FastAPI(title="FitFinder worker")


class Health(BaseModel):
    status: str


@app.get("/health")
def health() -> Health:
    return Health(status="ok")
