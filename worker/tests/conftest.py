"""Shared pytest fixtures.

The rendered regression fixtures are session-scoped and parametrised. pytest then runs
all tests for one insole photo before rendering the next, so each photo is drawn once
per run and only one is held in memory at a time.
"""

import os

import pytest

from tests.regression import (
    RenderedFixture,
    measurable_fixtures,
    rejected_fixtures,
    render_fixture,
)

# Tests never send events to Sentry, even if a developer has SENTRY_DSN set locally.
# Popped at import time, before any test module imports app.main (which calls init_sentry).
os.environ.pop("SENTRY_DSN", None)


@pytest.fixture(scope="session", params=measurable_fixtures(), ids=lambda f: f.name)
def measurable(request: pytest.FixtureRequest) -> RenderedFixture:
    return render_fixture(request.param)


@pytest.fixture(scope="session", params=rejected_fixtures(), ids=lambda f: f.name)
def rejected(request: pytest.FixtureRequest) -> RenderedFixture:
    return render_fixture(request.param)
