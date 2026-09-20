from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.thumbnail_service import MAX_THUMBNAIL_BYTES

from conftest import TestUser

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"
PNG = b"\x89PNGfake-png"


def _video(client) -> int:
    return client.post("/videos", json={"title": "動画", "duration_ms": 1000}).json()["id"]


def _put(client, video_id: int, data: bytes, **form):
    return client.put(
        f"/videos/{video_id}/thumbnail",
        files={"data": ("t", data, "application/octet-stream")},
        data=form,
    )


def test_put_and_get_thumbnail(user: TestUser) -> None:
    video_id = _video(user.client)
    res = _put(user.client, video_id, JPEG, width="320", height="180")
    assert res.status_code == 200
    assert res.json() == {"video_id": video_id, "mime_type": "image/jpeg", "width": 320, "height": 180}
    got = user.client.get(f"/videos/{video_id}/thumbnail")
    assert got.status_code == 200
    assert got.content == JPEG
    assert got.headers["content-type"] == "image/jpeg"
    assert got.headers["cache-control"] == "private"
    assert user.client.get(f"/videos/{video_id}").json()["has_thumbnail"] is True


def test_put_replaces_existing_thumbnail(user: TestUser) -> None:
    video_id = _video(user.client)
    _put(user.client, video_id, JPEG)
    res = _put(user.client, video_id, PNG, mime_type="image/png")
    assert res.status_code == 200
    got = user.client.get(f"/videos/{video_id}/thumbnail")
    assert got.content == PNG
    assert got.headers["content-type"] == "image/png"


def test_missing_thumbnail_is_404(user: TestUser) -> None:
    video_id = _video(user.client)
    assert user.client.get(f"/videos/{video_id}/thumbnail").status_code == 404
    assert user.client.get("/videos/99999999/thumbnail").status_code == 404


def test_thumbnail_is_private(user: TestUser, other_user: TestUser) -> None:
    video_id = _video(user.client)
    _put(user.client, video_id, JPEG)
    assert other_user.client.get(f"/videos/{video_id}/thumbnail").status_code == 404
    assert _put(other_user.client, video_id, PNG).status_code == 404
    assert TestClient(app).get(f"/videos/{video_id}/thumbnail").status_code == 401


def test_thumbnail_validation(user: TestUser) -> None:
    video_id = _video(user.client)
    assert _put(user.client, video_id, b"").status_code == 400
    assert _put(user.client, video_id, b"x" * (MAX_THUMBNAIL_BYTES + 1)).status_code == 400
    assert _put(user.client, video_id, JPEG, mime_type="text/plain").status_code == 400
    assert _put(user.client, video_id, JPEG, width="0").status_code == 400
    assert _put(user.client, video_id, JPEG, height="-5").status_code == 400
    assert user.client.put(f"/videos/{video_id}/thumbnail").status_code == 400
    assert _put(user.client, video_id, b"x" * MAX_THUMBNAIL_BYTES).status_code == 200
