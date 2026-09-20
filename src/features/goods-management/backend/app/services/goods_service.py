from __future__ import annotations

import base64
import binascii
from datetime import date

from app.errors import InvalidInputError, NotFoundError
from app.logger import safe_text, write
from app.repos import (
    ArtistRow,
    GoodsImageRow,
    GoodsListItemRow,
    GoodsRow,
    MediaRow,
    delete_goods_image,
    get_artist,
    get_goods,
    get_goods_image,
    get_media,
    get_person,
    insert_goods,
    insert_goods_image,
    list_goods,
    list_goods_images,
    logical_delete_goods,
    related_artist_ids_by_person,
    related_artists_by_person,
    related_media_by_person,
    update_goods,
)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg"}


def _validate_title(title: str) -> str:
    trimmed = title.strip()
    if trimmed == "":
        raise InvalidInputError("タイトルが空")
    return trimmed


def _artist_body(row: ArtistRow) -> dict[str, object]:
    return {"id": row.id, "name": row.name}


def _media_body(row: MediaRow) -> dict[str, object]:
    return {"id": row.id, "name": row.name}


def _image_body(row: GoodsImageRow) -> dict[str, object]:
    return {
        "id": row.id,
        "image_type": row.image_type,
        "image_data": base64.b64encode(row.image_data).decode("ascii"),
        "display_order": row.display_order,
    }


def _goods_detail_body(row: GoodsRow) -> dict[str, object]:
    images = list_goods_images(row.id)
    return {
        "id": row.id,
        "media_id": row.media_id,
        "artist_id": row.artist_id,
        "title": row.title,
        "release_date": row.release_date.isoformat(),
        "memo": row.memo,
        "is_owned": row.is_owned,
        "code_number": row.code_number,
        "images": [_image_body(image) for image in images],
    }


def _list_item_body(row: GoodsListItemRow) -> dict[str, object]:
    return {
        "goods_id": row.goods_id,
        "media_id": row.media_id,
        "media_name": row.media_name,
        "artist_id": row.artist_id,
        "artist_name": row.artist_name,
        "title": row.title,
        "release_date": row.release_date.isoformat(),
        "is_owned": row.is_owned,
        "code_number": row.code_number,
        "thumbnail_image_type": row.thumbnail_image_type,
        "thumbnail_image_data": (
            None
            if row.thumbnail_image_data is None
            else base64.b64encode(row.thumbnail_image_data).decode("ascii")
        ),
    }


# ---- person に紐づく関連アーティスト・媒体 ----------------------------------------


def related_artists(user_id: int, person_id: int) -> list[dict[str, object]]:
    write("INF", f"関連アーティスト要求 user_id={user_id} person_id={person_id}")
    if get_person(user_id, person_id) is None:
        write("WRN", f"関連アーティスト失敗 user_id={user_id} person_id={person_id} 理由=対象なし")
        raise NotFoundError
    items = [_artist_body(row) for row in related_artists_by_person(user_id, person_id)]
    write("INF", f"関連アーティスト成功 user_id={user_id} person_id={person_id} count={len(items)}")
    return items


def related_media(user_id: int, person_id: int) -> list[dict[str, object]]:
    write("INF", f"関連媒体要求 user_id={user_id} person_id={person_id}")
    if get_person(user_id, person_id) is None:
        write("WRN", f"関連媒体失敗 user_id={user_id} person_id={person_id} 理由=対象なし")
        raise NotFoundError
    items = [_media_body(row) for row in related_media_by_person(user_id, person_id)]
    write("INF", f"関連媒体成功 user_id={user_id} person_id={person_id} count={len(items)}")
    return items


# ---- goods 一覧 -------------------------------------------------------------------


def list_goods_view(
    user_id: int, person_id: int, artist_id: int | None, media_id: int | None
) -> list[dict[str, object]]:
    write(
        "INF",
        f"商品一覧要求 user_id={user_id} person_id={person_id} artist_id={artist_id} media_id={media_id}",
    )
    if get_person(user_id, person_id) is None:
        write("WRN", f"商品一覧失敗 user_id={user_id} person_id={person_id} 理由=対象なし")
        raise NotFoundError

    linked_artist_ids = related_artist_ids_by_person(user_id, person_id)
    if artist_id is None:
        artist_ids = linked_artist_ids
    else:
        if artist_id not in linked_artist_ids:
            write(
                "WRN",
                f"商品一覧失敗 user_id={user_id} person_id={person_id} artist_id={artist_id} 理由=対象なし",
            )
            raise NotFoundError
        artist_ids = [artist_id]

    if media_id is not None and get_media(user_id, media_id) is None:
        write(
            "WRN",
            f"商品一覧失敗 user_id={user_id} media_id={media_id} 理由=対象なし",
        )
        raise NotFoundError

    items = [_list_item_body(row) for row in list_goods(user_id, artist_ids, media_id)]
    write("INF", f"商品一覧成功 user_id={user_id} person_id={person_id} count={len(items)}")
    return items


# ---- goods 単件・登録・更新・削除 ----------------------------------------------------


def get_goods_view(user_id: int, goods_id: int) -> dict[str, object]:
    write("INF", f"商品詳細要求 user_id={user_id} goods_id={goods_id}")
    row = get_goods(user_id, goods_id)
    if row is None:
        write("WRN", f"商品詳細失敗 user_id={user_id} goods_id={goods_id} 理由=対象なし")
        raise NotFoundError
    write("INF", f"商品詳細成功 user_id={user_id} goods_id={goods_id}")
    return _goods_detail_body(row)


def _ensure_media_and_artist(user_id: int, media_id: int, artist_id: int) -> None:
    if get_media(user_id, media_id) is None or get_artist(user_id, artist_id) is None:
        raise NotFoundError


def create_goods(
    user_id: int,
    media_id: int,
    artist_id: int,
    title: str,
    release_date_value: date | None,
    memo: str | None,
    is_owned: bool,
    code_number: str | None,
) -> dict[str, object]:
    write("INF", f"商品登録要求 user_id={user_id} media_id={media_id} artist_id={artist_id} title={safe_text(title)}")
    trimmed = _validate_title(title)
    _ensure_media_and_artist(user_id, media_id, artist_id)
    effective_date = release_date_value if release_date_value is not None else date.today()
    row = insert_goods(user_id, media_id, artist_id, trimmed, effective_date, memo, is_owned, code_number)
    write("INF", f"商品登録成功 user_id={user_id} goods_id={row.id}")
    return _goods_detail_body(row)


def update_goods_view(
    user_id: int,
    goods_id: int,
    media_id: int,
    artist_id: int,
    title: str,
    release_date_value: date | None,
    memo: str | None,
    is_owned: bool,
    code_number: str | None,
) -> dict[str, object]:
    write("INF", f"商品更新要求 user_id={user_id} goods_id={goods_id}")
    existing = get_goods(user_id, goods_id)
    if existing is None:
        write("WRN", f"商品更新失敗 user_id={user_id} goods_id={goods_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_title(title)
    _ensure_media_and_artist(user_id, media_id, artist_id)
    update_goods(
        goods_id, user_id, media_id, artist_id, trimmed, release_date_value, memo, is_owned, code_number
    )
    updated = get_goods(user_id, goods_id)
    assert updated is not None
    write("INF", f"商品更新成功 user_id={user_id} goods_id={goods_id}")
    return _goods_detail_body(updated)


def remove_goods(user_id: int, goods_id: int) -> None:
    write("INF", f"商品削除要求 user_id={user_id} goods_id={goods_id}")
    existing = get_goods(user_id, goods_id)
    if existing is None:
        write("WRN", f"商品削除失敗 user_id={user_id} goods_id={goods_id} 理由=対象なし")
        raise NotFoundError
    logical_delete_goods(goods_id, user_id)
    write("INF", f"商品削除成功 user_id={user_id} goods_id={goods_id}")


# ---- goods 画像 -----------------------------------------------------------------


def add_image(user_id: int, goods_id: int, image_type: str, image_data: str) -> dict[str, object]:
    write("INF", f"商品画像追加要求 user_id={user_id} goods_id={goods_id}")
    if get_goods(user_id, goods_id) is None:
        write("WRN", f"商品画像追加失敗 user_id={user_id} goods_id={goods_id} 理由=対象なし")
        raise NotFoundError
    if image_type not in ALLOWED_IMAGE_TYPES:
        write("WRN", f"商品画像追加失敗 user_id={user_id} goods_id={goods_id} 理由=image_type不正")
        raise InvalidInputError("image_typeが不正")
    try:
        decoded = base64.b64decode(image_data, validate=True)
    except (ValueError, binascii.Error):
        write("WRN", f"商品画像追加失敗 user_id={user_id} goods_id={goods_id} 理由=image_data不正")
        raise InvalidInputError("image_dataが不正") from None
    if not decoded:
        write("WRN", f"商品画像追加失敗 user_id={user_id} goods_id={goods_id} 理由=image_data不正")
        raise InvalidInputError("image_dataが不正")
    row = insert_goods_image(user_id, goods_id, decoded, image_type)
    write("INF", f"商品画像追加成功 user_id={user_id} goods_id={goods_id} image_id={row.id}")
    return _image_body(row)


def remove_image(user_id: int, goods_id: int, image_id: int) -> None:
    write("INF", f"商品画像削除要求 user_id={user_id} goods_id={goods_id} image_id={image_id}")
    if get_goods(user_id, goods_id) is None:
        write("WRN", f"商品画像削除失敗 user_id={user_id} goods_id={goods_id} 理由=対象なし")
        raise NotFoundError
    if get_goods_image(user_id, goods_id, image_id) is None:
        write(
            "WRN",
            f"商品画像削除失敗 user_id={user_id} goods_id={goods_id} image_id={image_id} 理由=対象なし",
        )
        raise NotFoundError
    delete_goods_image(image_id)
    write("INF", f"商品画像削除成功 user_id={user_id} goods_id={goods_id} image_id={image_id}")
