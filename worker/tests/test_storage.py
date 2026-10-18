"""Storage client against a fake HTTP server (httpx.MockTransport)."""

import json

import httpx
import pytest

from app.jobs.storage import ObjectNotFound, ObjectTooLarge, SupabaseStorage, object_url

SECRET = "sb_secret_test"  # noqa: S105 - not a real key


def client(handler: httpx.MockTransport) -> SupabaseStorage:
    return SupabaseStorage("http://supabase.test/", SECRET, transport=handler)


def test_download_sends_the_secret_key_and_returns_the_bytes() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"photo")

    with client(httpx.MockTransport(handler)) as storage:
        assert storage.download("u1/photo 1.jpg", max_bytes=100) == b"photo"

    assert seen[0].url.path == "/storage/v1/object/insoles/u1/photo 1.jpg"
    assert seen[0].url.raw_path == b"/storage/v1/object/insoles/u1/photo%201.jpg"
    assert seen[0].headers["apikey"] == SECRET
    assert seen[0].headers["authorization"] == f"Bearer {SECRET}"


def test_download_stops_past_the_byte_limit_whatever_content_length_says() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 1000, headers={"content-length": "10"})

    with client(httpx.MockTransport(handler)) as storage, pytest.raises(ObjectTooLarge):
        storage.download("u1/a.jpg", max_bytes=100)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        # What Supabase Storage actually answers for a missing object.
        httpx.Response(400, json={"statusCode": "404", "error": "not_found"}),
    ],
)
def test_download_maps_missing_objects(response: httpx.Response) -> None:
    storage = client(httpx.MockTransport(lambda r: response))
    with storage, pytest.raises(ObjectNotFound):
        storage.download("u1/a.jpg", max_bytes=100)


def test_download_raises_other_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="not json")

    storage = client(httpx.MockTransport(handler))
    with storage, pytest.raises(httpx.HTTPStatusError):
        storage.download("u1/a.jpg", max_bytes=100)


def test_upload_overwrites_and_delete_uses_prefixes() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    with client(httpx.MockTransport(handler)) as storage:
        storage.upload("u1/processed/s1.jpg", b"jpeg", "image/jpeg")
        storage.delete("u1/processed/s1.jpg")

    upload, delete = seen
    assert upload.method == "POST"
    assert upload.url.path == "/storage/v1/object/insoles/u1/processed/s1.jpg"
    assert upload.headers["x-upsert"] == "true"
    assert upload.headers["content-type"] == "image/jpeg"
    assert upload.content == b"jpeg"
    assert delete.method == "DELETE"
    assert delete.url.path == "/storage/v1/object/insoles"
    assert json.loads(delete.content) == {"prefixes": ["u1/processed/s1.jpg"]}


@pytest.mark.parametrize(
    "path", ["../other/a.jpg", "u1/../../a.jpg", "/u1/a.jpg", "u1//a.jpg", "u1\\a.jpg", ""]
)
def test_rejects_paths_that_could_escape_the_bucket(path: str) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        object_url("insoles", path)
