"""Supabase Storage over its HTTP API, with the secret key.

Why HTTP and not SQL? `storage.objects` only holds metadata; the file itself lives in an
object store behind the Storage API. Deleting the row would leave the file behind
(ADR 0006), so downloads, uploads and deletes all go through the API.

The secret key bypasses Row-Level Security. It's only ever read from the environment
on the server and sent to Supabase, never logged.
"""

from types import TracebackType
from typing import Protocol, Self
from urllib.parse import quote

import httpx

from app.jobs import config


class ObjectNotFound(Exception):  # noqa: N818
    pass


class ObjectTooLarge(Exception):  # noqa: N818
    pass


class Storage(Protocol):
    def download(self, path: str, max_bytes: int) -> bytes:
        """Raises ObjectNotFound, or ObjectTooLarge once more than max_bytes arrived."""
        ...

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        """Create or overwrite the file (a retry may upload the same path again)."""
        ...

    def delete(self, path: str) -> None: ...


def object_url(bucket: str, path: str) -> str:
    """URL path of a file, rejecting anything that could escape the bucket path."""
    segments = path.split("/")
    if path.startswith("/") or "\\" in path or any(s in ("", ".", "..") for s in segments):
        raise ValueError(f"unsafe storage path: {path!r}")
    return f"/object/{quote(bucket, safe='')}/{quote(path, safe='/')}"


class SupabaseStorage:
    def __init__(
        self,
        supabase_url: str,
        secret_key: str,
        bucket: str = config.BUCKET,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.bucket = bucket
        self._client = httpx.Client(
            base_url=supabase_url.rstrip("/") + "/storage/v1",
            # Same headers the supabase-js client sends with a secret key.
            headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
            timeout=config.STORAGE_TIMEOUT_S,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._client.close()

    def download(self, path: str, max_bytes: int) -> bytes:
        # Streamed, so a huge file is cut off at max_bytes instead of filling memory.
        # Content-Length is only a hint from the server; the byte count is what counts.
        with self._client.stream("GET", object_url(self.bucket, path)) as response:
            if _is_not_found(response):
                raise ObjectNotFound(path)
            response.raise_for_status()
            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise ObjectTooLarge(f"{path}: more than {max_bytes} bytes")
                chunks.append(chunk)
        return b"".join(chunks)

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        response = self._client.post(
            object_url(self.bucket, path),
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        response.raise_for_status()

    def delete(self, path: str) -> None:
        object_url(self.bucket, path)  # validates the path
        # Deleting a missing file is not an error: the API returns an empty list.
        response = self._client.request(
            "DELETE", f"/object/{quote(self.bucket, safe='')}", json={"prefixes": [path]}
        )
        response.raise_for_status()


def _is_not_found(response: httpx.Response) -> bool:
    if response.status_code == httpx.codes.NOT_FOUND:
        return True
    # Supabase Storage reports a missing object as 400 with {"statusCode": "404"}.
    if response.status_code == httpx.codes.BAD_REQUEST:
        response.read()
        try:
            body = response.json()
        except ValueError:
            return False
        return isinstance(body, dict) and str(body.get("statusCode")) == "404"
    return False
