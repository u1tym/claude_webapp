from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.logger import LOG_FILE, close_logging, setup_logging  # noqa: E402

TINY_PNG = base64.b64encode(bytes.fromhex("89504e470d0a1a0a")).decode("ascii")


def _ensure_user(username: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM public.users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row is not None:
                return int(row["id"])
            cur.execute(
                "INSERT INTO public.users (username, password_hash) VALUES (%s, 'x') RETURNING id",
                (username,),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def _ensure_feature_assignment(user_id: int, feature_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.features (id, title, url, icon, icon_media_type)
                VALUES (%s, %s, %s, ''::bytea, 'image/png')
                ON CONFLICT (id) DO NOTHING
                """,
                (feature_id, feature_id, f"/portal_{feature_id.replace('-', '_')}/"),
            )
            cur.execute(
                """
                INSERT INTO public.menu_assignments (user_id, feature_id, display_order)
                VALUES (%s, %s, 1)
                ON CONFLICT DO NOTHING
                """,
                (user_id, feature_id),
            )


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


@pytest.fixture()
def allowed_username() -> str:
    return f"gm_test_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def unassigned_username() -> str:
    return f"gm_test_noaccess_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def allowed_user_id(allowed_username: str) -> int:
    user_id = _ensure_user(allowed_username)
    _ensure_feature_assignment(user_id, "goods-management")
    return user_id


@pytest.fixture()
def unassigned_user_id(unassigned_username: str) -> int:
    return _ensure_user(unassigned_username)


def _client_as(monkeypatch: pytest.MonkeyPatch, username: str | None):
    from app.main import app
    from fastapi.testclient import TestClient

    cfg = load_config()
    patched = cfg.__class__(
        db_server=cfg.db_server,
        db_name=cfg.db_name,
        db_port=cfg.db_port,
        db_username=cfg.db_username,
        db_password=cfg.db_password,
        cors_origins=cfg.cors_origins,
        session_timeout_minutes=cfg.session_timeout_minutes,
        debug_user=username,
        log_max_bytes=cfg.log_max_bytes,
        log_backup_count=cfg.log_backup_count,
    )
    monkeypatch.setattr("app.deps.load_config", lambda: patched)
    return TestClient(app)


def test_settings_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_as(monkeypatch, None)
    res = client.get("/settings")
    assert res.status_code == 200
    assert "session_id" not in res.text


def test_persons_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_as(monkeypatch, None)
    res = client.get("/persons")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_persons_require_assignment(
    monkeypatch: pytest.MonkeyPatch, unassigned_user_id: int, unassigned_username: str
) -> None:
    client = _client_as(monkeypatch, unassigned_username)
    res = client.get("/persons")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_full_flow_crud_relations_delete_constraints(
    monkeypatch: pytest.MonkeyPatch,
    allowed_user_id: int,
    allowed_username: str,
    log_dir: Path,
) -> None:
    client = _client_as(monkeypatch, allowed_username)

    person = client.post("/persons", json={"name": "山田花子"})
    assert person.status_code == 201
    person_id = person.json()["id"]

    empty_name = client.post("/persons", json={"name": "  "})
    assert empty_name.status_code == 400

    artist = client.post("/artists", json={"name": "サンプルズ", "person_ids": [person_id]})
    assert artist.status_code == 201
    artist_id = artist.json()["id"]
    assert [p["id"] for p in artist.json()["persons"]] == [person_id]

    media = client.post("/media", json={"name": "1stシングル"})
    assert media.status_code == 201
    media_id = media.json()["id"]

    related_artists = client.get(f"/persons/{person_id}/related-artists")
    assert related_artists.status_code == 200
    assert [a["id"] for a in related_artists.json()["items"]] == [artist_id]

    # no goods yet, so related media is empty even though the artist exists
    related_media_before = client.get(f"/persons/{person_id}/related-media")
    assert related_media_before.json()["items"] == []

    goods = client.post(
        "/goods",
        json={"media_id": media_id, "artist_id": artist_id, "title": "サンプルグッズ"},
    )
    assert goods.status_code == 201
    goods_id = goods.json()["id"]
    assert goods.json()["release_date"] != ""
    assert goods.json()["images"] == []

    related_media_after = client.get(f"/persons/{person_id}/related-media")
    assert [m["id"] for m in related_media_after.json()["items"]] == [media_id]

    listed_all = client.get("/goods", params={"person_id": person_id})
    assert listed_all.status_code == 200
    assert [g["goods_id"] for g in listed_all.json()["items"]] == [goods_id]

    listed_by_artist = client.get(
        "/goods", params={"person_id": person_id, "artist_id": artist_id, "media_id": media_id}
    )
    assert [g["goods_id"] for g in listed_by_artist.json()["items"]] == [goods_id]

    image = client.post(f"/goods/{goods_id}/images", json={"image_type": "image/png", "image_data": TINY_PNG})
    assert image.status_code == 201
    image_id = image.json()["id"]

    detail_with_image = client.get(f"/goods/{goods_id}")
    assert len(detail_with_image.json()["images"]) == 1

    # deleting the referenced artist/media fails while the goods row exists
    assert client.delete(f"/artists/{artist_id}").status_code == 409
    assert client.delete(f"/media/{media_id}").status_code == 409
    assert client.delete(f"/persons/{person_id}").status_code == 409

    remove_image = client.delete(f"/goods/{goods_id}/images/{image_id}")
    assert remove_image.status_code == 204
    assert client.get(f"/goods/{goods_id}").json()["images"] == []

    deleted_goods = client.delete(f"/goods/{goods_id}")
    assert deleted_goods.status_code == 204
    assert client.get(f"/goods/{goods_id}").status_code == 404

    # now that no goods references them, artist/media/person can be deleted
    assert client.delete(f"/artists/{artist_id}").status_code == 204
    assert client.delete(f"/media/{media_id}").status_code == 204
    assert client.delete(f"/persons/{person_id}").status_code == 204

    text = _log_text(log_dir)
    assert "商品削除成功" in text
    assert TINY_PNG not in text
