"""別サーバで稼働する goods（旧グッズ管理サービス）から、未削除の商品と、
関連する人物・アーティスト・媒体・アーティストと人物の関連・商品画像を JSON へ
エクスポートするスクリプト。

旧アプリにはユーザ・アカウントの区別が無いため、アカウント一覧は出力しない。
全データを、インポート時に指定する1人の利用者へ取り込む前提。

このスクリプトは旧サーバ側（または旧サーバの DB に到達できる環境）で実行する。

使い方:
    python export_from_goods.py \
        --host localhost --port 5432 --dbname <旧DB名> \
        --user <旧DBユーザ> --password <旧DBパスワード> \
        --output goods_export.json

接続情報は環境変数でも指定できる（引数が優先）:
    GOODS_DB_HOST, GOODS_DB_PORT, GOODS_DB_NAME, GOODS_DB_USER, GOODS_DB_PASSWORD
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionArgs:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _parse_args() -> tuple[ConnectionArgs, str]:
    parser = argparse.ArgumentParser(description="goods から未削除データを JSON へエクスポートする")
    parser.add_argument("--host", default=os.environ.get("GOODS_DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GOODS_DB_PORT", "5432")))
    parser.add_argument("--dbname", default=os.environ.get("GOODS_DB_NAME", ""))
    parser.add_argument("--user", default=os.environ.get("GOODS_DB_USER", ""))
    parser.add_argument("--password", default=os.environ.get("GOODS_DB_PASSWORD", ""))
    parser.add_argument("--output", required=True, help="出力先の JSON ファイルパス")
    args = parser.parse_args()
    return (
        ConnectionArgs(
            host=args.host,
            port=args.port,
            dbname=args.dbname,
            user=args.user,
            password=args.password,
        ),
        args.output,
    )


def main() -> None:
    conn_args, output_path = _parse_args()

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(
        host=conn_args.host,
        port=conn_args.port,
        dbname=conn_args.dbname,
        user=conn_args.user,
        password=conn_args.password,
        cursor_factory=RealDictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM public.persons ORDER BY id ASC")
            persons = [{"id": int(r["id"]), "name": str(r["name"])} for r in cur.fetchall()]

            cur.execute("SELECT id, name FROM public.artists ORDER BY id ASC")
            artists = [{"id": int(r["id"]), "name": str(r["name"])} for r in cur.fetchall()]

            cur.execute(
                "SELECT id, artist_id, person_id FROM public.artist_persons ORDER BY id ASC"
            )
            artist_persons = [
                {
                    "id": int(r["id"]),
                    "artist_id": int(r["artist_id"]),
                    "person_id": int(r["person_id"]),
                }
                for r in cur.fetchall()
            ]

            cur.execute("SELECT id, name FROM public.media ORDER BY id ASC")
            media = [{"id": int(r["id"]), "name": str(r["name"])} for r in cur.fetchall()]

            cur.execute(
                """
                SELECT id, media_id, artist_id, title, release_date, memo,
                       is_owned, code_number
                FROM public.goods
                WHERE is_deleted = false
                ORDER BY id ASC
                """
            )
            goods_rows = cur.fetchall()
            goods = [
                {
                    "id": int(r["id"]),
                    "media_id": int(r["media_id"]),
                    "artist_id": int(r["artist_id"]),
                    "title": str(r["title"]),
                    "release_date": r["release_date"].isoformat(),
                    "memo": (None if r["memo"] is None else str(r["memo"])),
                    "is_owned": bool(r["is_owned"]),
                    "code_number": (None if r["code_number"] is None else str(r["code_number"])),
                }
                for r in goods_rows
            ]
            goods_ids = [g["id"] for g in goods]

            goods_images: list[dict[str, object]] = []
            if goods_ids:
                cur.execute(
                    """
                    SELECT id, goods_id, image_data, image_type, display_order
                    FROM public.goods_images
                    WHERE goods_id = ANY(%s)
                    ORDER BY goods_id ASC, display_order ASC
                    """,
                    (goods_ids,),
                )
                for r in cur.fetchall():
                    goods_images.append(
                        {
                            "id": int(r["id"]),
                            "goods_id": int(r["goods_id"]),
                            "image_data": base64.b64encode(bytes(r["image_data"])).decode("ascii"),
                            "image_type": str(r["image_type"]),
                            "display_order": int(r["display_order"]),
                        }
                    )
    finally:
        conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "persons": persons,
                "artists": artists,
                "artist_persons": artist_persons,
                "media": media,
                "goods": goods,
                "goods_images": goods_images,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"人物: {len(persons)}件、アーティスト: {len(artists)}件、"
        f"アーティストと人物の関連: {len(artist_persons)}件、媒体: {len(media)}件、"
        f"商品: {len(goods)}件、商品画像: {len(goods_images)}件を {output_path} へ出力しました",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
