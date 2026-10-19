"""The pipeline seam and the sandbox around it."""

import os
import time

import cv2
import numpy as np
import pytest

from app.jobs.process import Analysis, Result, no_analysis, process
from app.jobs.sandbox import (
    JobCrashedError,
    JobTimeoutError,
    Processed,
    Rejected,
    analyse_upload,
    run_isolated,
)
from app.pipeline.rejections import Rejection, RejectionCode
from app.pipeline.segment import Segmentation
from app.pipeline.warp import PageWarp
from tests.jobs_fakes import CLASSIFICATION, MEASUREMENT
from tests.regression import RenderedFixture


def analyzer_stub(warp: PageWarp, segmentation: Segmentation, /) -> Analysis:
    return Analysis(MEASUREMENT, CLASSIFICATION)


def classification_only(warp: PageWarp, segmentation: Segmentation, /) -> Analysis:
    return Analysis(classification=CLASSIFICATION)


def analyzer_rejecting(warp: PageWarp, segmentation: Segmentation, /) -> Analysis:
    raise Rejection(RejectionCode.INSOLE_NOT_FOUND, "stub")


def jpeg(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def test_process_measurable_photo_without_analyzer_returns_empty_result(
    measurable: RenderedFixture,
) -> None:
    result = process(measurable.photo.image, no_analysis)

    assert isinstance(result, Result)
    assert result.measurement is None
    assert result.classification is None
    assert len(result.markers_found) >= 3
    assert result.insole_area_mm2 > 8000


def test_process_passes_analyzer_rows_through(measurable: RenderedFixture) -> None:
    result = process(measurable.photo.image, analyzer_stub)

    assert isinstance(result, Result)
    assert result.measurement == MEASUREMENT
    assert result.classification == CLASSIFICATION


def test_process_returns_analyzer_rejections(measurable: RenderedFixture) -> None:
    result = process(measurable.photo.image, analyzer_rejecting)

    assert isinstance(result, Rejection)
    assert result.code is RejectionCode.INSOLE_NOT_FOUND


def test_process_refuses_a_classification_without_measurement(
    measurable: RenderedFixture,
) -> None:
    with pytest.raises(ValueError, match="measurement"):
        process(measurable.photo.image, classification_only)


def test_process_returns_pipeline_rejections(rejected: RenderedFixture) -> None:
    result = process(rejected.photo.image)

    assert isinstance(result, Rejection)
    assert result.code == rejected.fixture.expected.rejection


def test_analyse_upload_turns_a_photo_into_a_clean_copy_and_result(
    measurable: RenderedFixture,
) -> None:
    processed = analyse_upload(jpeg(measurable.photo.image))

    assert processed.clean_jpeg is not None
    assert processed.clean_jpeg.startswith(b"\xff\xd8\xff")
    assert isinstance(processed.outcome, Result)


def test_analyse_upload_keeps_the_clean_copy_of_a_rejected_photo(
    rejected: RenderedFixture,
) -> None:
    processed = analyse_upload(jpeg(rejected.photo.image))

    assert processed.clean_jpeg is not None
    assert isinstance(processed.outcome, Rejected)
    assert processed.outcome.code == rejected.fixture.expected.rejection
    assert processed.outcome.message  # user-facing text


def test_analyse_upload_rejects_non_images_without_a_copy() -> None:
    processed = analyse_upload(b"<html>not a photo</html>")

    assert processed == Processed(None, processed.outcome)
    assert isinstance(processed.outcome, Rejected)
    assert processed.outcome.code == "unsupported_image"


# --- run_isolated: real child processes ---


def slow(seconds: float) -> str:
    time.sleep(seconds)
    return "finished"


def explode() -> None:
    raise RuntimeError("decoder bug")


def die() -> None:
    os._exit(3)  # like a segfault in C code: no exception, no result


def test_run_isolated_returns_the_childs_result() -> None:
    assert run_isolated(slow, 0, timeout_s=30) == "finished"


def test_run_isolated_kills_a_job_over_the_time_limit() -> None:
    started = time.monotonic()
    with pytest.raises(JobTimeoutError):
        run_isolated(slow, 60, timeout_s=3)
    assert time.monotonic() - started < 15


def test_run_isolated_reports_exceptions_in_the_child() -> None:
    with pytest.raises(JobCrashedError, match="decoder bug"):
        run_isolated(explode, timeout_s=30)


def test_run_isolated_reports_a_child_that_died() -> None:
    with pytest.raises(JobCrashedError, match="died"):
        run_isolated(die, timeout_s=30)


def test_run_isolated_runs_the_real_upload_analysis() -> None:
    processed = run_isolated(analyse_upload, b"GIF89a...", timeout_s=30)

    assert isinstance(processed.outcome, Rejected)
    assert processed.outcome.code == "unsupported_image"
