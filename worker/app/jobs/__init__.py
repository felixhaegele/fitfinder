"""Queue consumer: takes submissions off the pgmq queue and turns them into results.

`app.pipeline` measures a photo and knows nothing about databases or files. This package
is the glue around it (ADR 0003, security requirements in #29):

- `validate`  untrusted upload bytes -> clean JPEG without metadata, or a rejection
- `process`   the seam into the pipeline: `process(image) -> Result | Rejection`
- `sandbox`   runs validation + pipeline in a child process with a time limit
- `storage`   Supabase Storage over HTTP (download, upload, delete) with the secret key
- `store`     Postgres: queue messages and submission rows
- `handler`   one message -> status transitions (queued -> processing -> done/...)
- `drain`     the Cloud Run Job entrypoint: handle messages until the queue is empty

Run it with `python -m app.jobs.drain`.
"""

import os

from app.jobs import config

# Backstop against decompression bombs inside OpenCV: refuse to decode anything bigger.
# OpenCV reads this environment variable, so it must be set before cv2 decodes anything.
# The Dockerfile sets it too; this covers local runs and the sandbox's child processes.
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", str(config.MAX_PIXELS))
