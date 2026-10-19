"""Limits and retry rules of the queue worker, in one place.

Measurement thresholds live in `app/pipeline/config.py`; these numbers are about running
jobs safely, not about measuring.
"""

# --- Queue (ADR 0003) ---

QUEUE_NAME = "submissions"

# A message is processed at most this many times. pgmq counts reads in `read_ct`; a
# message read for the (MAX_ATTEMPTS + 1)-th time is archived and its submission set to
# `failed` without trying again.
MAX_ATTEMPTS = 3

# Wall-clock limit for validating + measuring one photo. A job that runs over is killed
# and counts as a failed attempt.
JOB_TIMEOUT_S = 60

# While the worker holds a message, pgmq hides it from other readers for this long.
# It must cover the job limit plus download, upload and the result write, or an
# overlapping run could pick up the same message while it's still being processed.
VISIBILITY_TIMEOUT_S = 150

# A Cloud Run Job execution stops taking new messages after this long and exits, so one
# execution never runs into the job's task timeout (10 min by default). The next
# scheduled run picks up the rest.
MAX_RUN_S = 8 * 60

# --- Storage ---

BUCKET = "insoles"

# Network timeout for one Storage request.
STORAGE_TIMEOUT_S = 30.0

# --- Untrusted uploads (security requirements in #29) ---

# Same as the bucket's file_size_limit (10 MiB). Someone calling the Storage API directly
# can't exceed it, but the worker doesn't rely on that and stops downloading past it.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Largest image (width x height) the worker decodes. A phone photo is 12-48 MP. A
# "decompression bomb" is a tiny file that claims huge dimensions and eats all memory
# when decoded; the size is read from the file header and checked *before* decoding.
MAX_PIXELS = 50_000_000

# Quality of the clean copy shown in the UI. 90 keeps the insole's edge crisp.
JPEG_QUALITY = 90
