"""export_from_goods.py が出力した JSON を読み込み、本プロジェクトの
goods_management スキーマへ取り込むスクリプト。

旧アプリにはユーザ・アカウントの区別が無いため、取り込み先のユーザを
このスクリプトの引数で1人指定し、全データをそのユーザの所有として取り込む。

このスクリプトは本プロジェクトの DB に到達できる環境（このバックエンドの venv）で実行する。
接続情報は `backend/.env` を使う（`app.db` 経由）。

人物→アーティスト→アーティストと人物の関連→媒体→商品→商品画像の順に、
旧IDと新IDの対応を保ちながら挿入する。商品画像の表示順は移行元の値をそのまま使う。

使い方（このディレクトリの venv を有効化してから）:
    python scripts/import_to_goods_management.py --input goods_export.json --username <取り込み先のユーザ名>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_conn  # noqa: E402
from app.repos import get_user_by_username  # noqa: E402


def _parse_args() -> tuple[str, str]:
    parser = argparse.ArgumentParser(description="goods のエクスポート JSON を取り込む")
    parser.add_argument("--input", required=True, help="export_from_goods.py が出力した JSON ファイルパス")
    parser.add_argument("--username", required=True, help="取り込み先の本プロジェクトのユーザ名")
    args = parser.parse_args()
    return args.input, args.username


def _insert_person(user_id: int, name: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.persons (user_id, name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (user_id, name),
            )
            return int(cur.fetchone()["id"])


def _insert_artist(user_id: int, name: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.artists (user_id, name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (user_id, name),
            )
            return int(cur.fetchone()["id"])


def _insert_artist_person(user_id: int, artist_id: int, person_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.artist_persons (user_id, artist_id, person_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, artist_id, person_id),
            )


def _insert_media(user_id: int, name: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.media (user_id, name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (user_id, name),
            )
            return int(cur.fetchone()["id"])


def _insert_goods(
    user_id: int,
    media_id: int,
    artist_id: int,
    title: str,
    release_date: str,
    memo: str | None,
    is_owned: bool,
    code_number: str | None,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.goods
                    (user_id, media_id, artist_id, title, release_date, memo, is_owned, code_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, media_id, artist_id, title, release_date, memo, is_owned, code_number),
            )
            return int(cur.fetchone()["id"])


def _insert_goods_image(
    user_id: int, goods_id: int, image_data_b64: str, image_type: str, display_order: int
) -> None:
    import base64

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.goods_images
                    (user_id, goods_id, image_data, image_type, display_order)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, goods_id, base64.b64decode(image_data_b64), image_type, display_order),
            )


def main() -> None:
    input_path, username = _parse_args()
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    user = get_user_by_username(username)
    if user is None or user.is_deleted:
        print(f"エラー: ユーザ '{username}' が見つからないか、削除済みです", file=sys.stderr)
        sys.exit(1)
    user_id = user.id

    person_id_map: dict[int, int] = {}
    for p in data["persons"]:
        person_id_map[int(p["id"])] = _insert_person(user_id, str(p["name"]))
    print(f"人物: {len(person_id_map)}件", file=sys.stderr)

    artist_id_map: dict[int, int] = {}
    for a in data["artists"]:
        artist_id_map[int(a["id"])] = _insert_artist(user_id, str(a["name"]))
    print(f"アーティスト: {len(artist_id_map)}件", file=sys.stderr)

    artist_person_count = 0
    for ap in data["artist_persons"]:
        old_artist_id = int(ap["artist_id"])
        old_person_id = int(ap["person_id"])
        new_artist_id = artist_id_map.get(old_artist_id)
        new_person_id = person_id_map.get(old_person_id)
        if new_artist_id is None or new_person_id is None:
            continue
        _insert_artist_person(user_id, new_artist_id, new_person_id)
        artist_person_count += 1
    print(f"アーティストと人物の関連: {artist_person_count}件", file=sys.stderr)

    media_id_map: dict[int, int] = {}
    for m in data["media"]:
        media_id_map[int(m["id"])] = _insert_media(user_id, str(m["name"]))
    print(f"媒体: {len(media_id_map)}件", file=sys.stderr)

    goods_id_map: dict[int, int] = {}
    goods_skipped = 0
    for g in data["goods"]:
        old_media_id = int(g["media_id"])
        old_artist_id = int(g["artist_id"])
        new_media_id = media_id_map.get(old_media_id)
        new_artist_id = artist_id_map.get(old_artist_id)
        if new_media_id is None or new_artist_id is None:
            goods_skipped += 1
            continue
        new_id = _insert_goods(
            user_id,
            new_media_id,
            new_artist_id,
            str(g["title"]),
            str(g["release_date"]),
            g["memo"],
            bool(g["is_owned"]),
            g["code_number"],
        )
        goods_id_map[int(g["id"])] = new_id
    print(f"商品: {len(goods_id_map)}件（対象外: {goods_skipped}件）", file=sys.stderr)

    image_count = 0
    image_skipped = 0
    for img in data["goods_images"]:
        old_goods_id = int(img["goods_id"])
        new_goods_id = goods_id_map.get(old_goods_id)
        if new_goods_id is None:
            image_skipped += 1
            continue
        _insert_goods_image(
            user_id,
            new_goods_id,
            str(img["image_data"]),
            str(img["image_type"]),
            int(img["display_order"]),
        )
        image_count += 1
    print(f"商品画像: {image_count}件（対象外: {image_skipped}件）", file=sys.stderr)


if __name__ == "__main__":
    main()
