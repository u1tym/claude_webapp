from __future__ import annotations

from app.errors import InvalidInputError, NotFoundError, ReferencedError
from app.logger import safe_text, write
from app.repos import (
    ArtistRow,
    MediaRow,
    PersonRow,
    artist_referenced,
    get_artist,
    get_media,
    get_person,
    insert_artist,
    insert_media,
    insert_person,
    list_artist_person_ids,
    list_artists,
    list_media,
    list_persons,
    list_persons_by_ids,
    logical_delete_artist,
    logical_delete_media,
    logical_delete_person,
    media_referenced,
    person_referenced,
    persons_exist,
    set_artist_persons,
    update_artist_name,
    update_media_name,
    update_person_name,
)


def _validate_name(name: str) -> str:
    trimmed = name.strip()
    if trimmed == "":
        raise InvalidInputError("名称が空")
    return trimmed


def _person_body(row: PersonRow) -> dict[str, object]:
    return {"id": row.id, "name": row.name}


def _artist_simple_body(row: ArtistRow) -> dict[str, object]:
    return {"id": row.id, "name": row.name}


def _media_body(row: MediaRow) -> dict[str, object]:
    return {"id": row.id, "name": row.name}


def _artist_detail_body(user_id: int, row: ArtistRow) -> dict[str, object]:
    person_ids = list_artist_person_ids(row.id)
    persons = list_persons_by_ids(user_id, person_ids)
    return {
        "id": row.id,
        "name": row.name,
        "persons": [_person_body(p) for p in persons],
    }


# ---- persons ------------------------------------------------------------------


def list_persons_view(user_id: int) -> list[dict[str, object]]:
    write("INF", f"人物一覧要求 user_id={user_id}")
    items = [_person_body(row) for row in list_persons(user_id)]
    write("INF", f"人物一覧成功 user_id={user_id} count={len(items)}")
    return items


def create_person(user_id: int, name: str) -> dict[str, object]:
    write("INF", f"人物登録要求 user_id={user_id} name={safe_text(name)}")
    trimmed = _validate_name(name)
    row = insert_person(user_id, trimmed)
    write("INF", f"人物登録成功 user_id={user_id} person_id={row.id}")
    return _person_body(row)


def rename_person(user_id: int, person_id: int, name: str) -> dict[str, object]:
    write("INF", f"人物名称変更要求 user_id={user_id} person_id={person_id}")
    existing = get_person(user_id, person_id)
    if existing is None:
        write("WRN", f"人物名称変更失敗 user_id={user_id} person_id={person_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_name(name)
    update_person_name(person_id, user_id, trimmed)
    updated = get_person(user_id, person_id)
    assert updated is not None
    write("INF", f"人物名称変更成功 user_id={user_id} person_id={person_id}")
    return _person_body(updated)


def remove_person(user_id: int, person_id: int) -> None:
    write("INF", f"人物削除要求 user_id={user_id} person_id={person_id}")
    existing = get_person(user_id, person_id)
    if existing is None:
        write("WRN", f"人物削除失敗 user_id={user_id} person_id={person_id} 理由=対象なし")
        raise NotFoundError
    if person_referenced(user_id, person_id):
        write("WRN", f"人物削除失敗 user_id={user_id} person_id={person_id} 理由=参照あり")
        raise ReferencedError
    logical_delete_person(person_id, user_id)
    write("INF", f"人物削除成功 user_id={user_id} person_id={person_id}")


# ---- artists ------------------------------------------------------------------


def list_artists_view(user_id: int) -> list[dict[str, object]]:
    write("INF", f"アーティスト一覧要求 user_id={user_id}")
    items = [_artist_simple_body(row) for row in list_artists(user_id)]
    write("INF", f"アーティスト一覧成功 user_id={user_id} count={len(items)}")
    return items


def get_artist_view(user_id: int, artist_id: int) -> dict[str, object]:
    write("INF", f"アーティスト詳細要求 user_id={user_id} artist_id={artist_id}")
    row = get_artist(user_id, artist_id)
    if row is None:
        write("WRN", f"アーティスト詳細失敗 user_id={user_id} artist_id={artist_id} 理由=対象なし")
        raise NotFoundError
    write("INF", f"アーティスト詳細成功 user_id={user_id} artist_id={artist_id}")
    return _artist_detail_body(user_id, row)


def create_artist(user_id: int, name: str, person_ids: list[int]) -> dict[str, object]:
    write("INF", f"アーティスト登録要求 user_id={user_id} name={safe_text(name)}")
    trimmed = _validate_name(name)
    if not persons_exist(user_id, person_ids):
        write("WRN", f"アーティスト登録失敗 user_id={user_id} 理由=対象外の人物指定")
        raise NotFoundError
    row = insert_artist(user_id, trimmed)
    set_artist_persons(user_id, row.id, person_ids)
    write("INF", f"アーティスト登録成功 user_id={user_id} artist_id={row.id}")
    return _artist_detail_body(user_id, row)


def update_artist(user_id: int, artist_id: int, name: str, person_ids: list[int]) -> dict[str, object]:
    write("INF", f"アーティスト変更要求 user_id={user_id} artist_id={artist_id}")
    existing = get_artist(user_id, artist_id)
    if existing is None:
        write("WRN", f"アーティスト変更失敗 user_id={user_id} artist_id={artist_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_name(name)
    if not persons_exist(user_id, person_ids):
        write("WRN", f"アーティスト変更失敗 user_id={user_id} artist_id={artist_id} 理由=対象外の人物指定")
        raise NotFoundError
    update_artist_name(artist_id, user_id, trimmed)
    set_artist_persons(user_id, artist_id, person_ids)
    updated = get_artist(user_id, artist_id)
    assert updated is not None
    write("INF", f"アーティスト変更成功 user_id={user_id} artist_id={artist_id}")
    return _artist_detail_body(user_id, updated)


def remove_artist(user_id: int, artist_id: int) -> None:
    write("INF", f"アーティスト削除要求 user_id={user_id} artist_id={artist_id}")
    existing = get_artist(user_id, artist_id)
    if existing is None:
        write("WRN", f"アーティスト削除失敗 user_id={user_id} artist_id={artist_id} 理由=対象なし")
        raise NotFoundError
    if artist_referenced(user_id, artist_id):
        write("WRN", f"アーティスト削除失敗 user_id={user_id} artist_id={artist_id} 理由=参照あり")
        raise ReferencedError
    logical_delete_artist(artist_id, user_id)
    write("INF", f"アーティスト削除成功 user_id={user_id} artist_id={artist_id}")


# ---- media --------------------------------------------------------------------


def list_media_view(user_id: int) -> list[dict[str, object]]:
    write("INF", f"媒体一覧要求 user_id={user_id}")
    items = [_media_body(row) for row in list_media(user_id)]
    write("INF", f"媒体一覧成功 user_id={user_id} count={len(items)}")
    return items


def create_media(user_id: int, name: str) -> dict[str, object]:
    write("INF", f"媒体登録要求 user_id={user_id} name={safe_text(name)}")
    trimmed = _validate_name(name)
    row = insert_media(user_id, trimmed)
    write("INF", f"媒体登録成功 user_id={user_id} media_id={row.id}")
    return _media_body(row)


def rename_media(user_id: int, media_id: int, name: str) -> dict[str, object]:
    write("INF", f"媒体名称変更要求 user_id={user_id} media_id={media_id}")
    existing = get_media(user_id, media_id)
    if existing is None:
        write("WRN", f"媒体名称変更失敗 user_id={user_id} media_id={media_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_name(name)
    update_media_name(media_id, user_id, trimmed)
    updated = get_media(user_id, media_id)
    assert updated is not None
    write("INF", f"媒体名称変更成功 user_id={user_id} media_id={media_id}")
    return _media_body(updated)


def remove_media(user_id: int, media_id: int) -> None:
    write("INF", f"媒体削除要求 user_id={user_id} media_id={media_id}")
    existing = get_media(user_id, media_id)
    if existing is None:
        write("WRN", f"媒体削除失敗 user_id={user_id} media_id={media_id} 理由=対象なし")
        raise NotFoundError
    if media_referenced(user_id, media_id):
        write("WRN", f"媒体削除失敗 user_id={user_id} media_id={media_id} 理由=参照あり")
        raise ReferencedError
    logical_delete_media(media_id, user_id)
    write("INF", f"媒体削除成功 user_id={user_id} media_id={media_id}")
