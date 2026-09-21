"""移行プログラム（scripts/migrate_from_note.py）のテスト。

移行元は、サンプルの構造を再現した一時的な DB（管理者で作成し、テスト後に削除）、
移行先は開発用 DB（backend/.env）を使う。管理者で接続できないときは、このファイルのテストを飛ばす。
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor

from app.config import load_config
from app.db import connect, get_conn

from conftest import TestUser, log_text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "scripts"))
import migrate_from_note as mig  # noqa: E402

ADMIN = {
    "user": os.environ.get("PG_ADMIN_USER", "postgres"),
    "password": os.environ.get("PG_ADMIN_PASSWORD", "postgres"),
}
FIXTURE_SQL = Path(__file__).resolve().parent / "fixtures" / "source_note.sql"

PNG = b"\x89PNG\r\n\x1a\n" + b"png-body" * 10
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-body" * 10


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _admin_connect(dbname: str, dict_rows: bool = False) -> psycopg2.extensions.connection:
    cfg = load_config()
    return psycopg2.connect(
        host=cfg.db_server, port=cfg.db_port, dbname=dbname,
        cursor_factory=RealDictCursor if dict_rows else None, **ADMIN,
    )


@pytest.fixture(scope="module")
def source_db_name() -> Iterator[str]:
    name = f"nm_src_{uuid.uuid4().hex[:10]}"
    try:
        admin = _admin_connect("postgres")
    except psycopg2.Error:
        pytest.skip("管理者で DB に接続できないため、移行のテストを飛ばします")
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    conn = _admin_connect(name)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(FIXTURE_SQL.read_text(encoding="utf-8"))
    conn.close()
    yield name
    with admin.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,))
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
    admin.close()


class Source:
    """移行元 DB へテストデータを入れる。"""

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def exec(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def account(self, username: str) -> int:
        return self.one("INSERT INTO public.accounts (username) VALUES (%s) RETURNING id", (username,))

    def folder(self, aid: int, name: str, parent: int | None = None, dorder: int = 1, deleted: int = 0) -> int:
        return self.one(
            "INSERT INTO note.folder (aid, parent, name, dorder, deleted_number) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (aid, parent, name, dorder, deleted),
        )

    def file(self, aid: int, belong: int, title: str, dorder: int = 1, deleted: int = 0) -> int:
        return self.one(
            "INSERT INTO note.file (aid, belong, title, dorder, deleted_number) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (aid, belong, title, dorder, deleted),
        )

    def part(
        self, aid: int, file_id: int, dorder: int, ptype: str, data: str = "", *, deleted: bool = False,
        filename: str = "", title: str = "", markers: str = "[]", scale: float = 1.0,
    ) -> int:
        return self.one(
            "INSERT INTO note.parts (aid, file, dorder, is_deleted, ptype, data, filename, title, markers, image_scale)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (aid, file_id, dorder, deleted, ptype, data, filename, title, markers, scale),
        )

    def revision(self, aid: int, part_id: int, number: int, ptype: str, filename: str, data: str, created: str = "2026-01-02 03:04:05") -> None:
        self.exec(
            "INSERT INTO note.parts_revision (aid, parts_id, revision_number, filename, ptype, data, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (aid, part_id, number, filename, ptype, data, created),
        )

    def table_part(self, aid: int, file_id: int, dorder: int) -> int:
        table_id = self.one("INSERT INTO note.\"table\" (aid, title) VALUES (%s, '表') RETURNING id", (aid,))
        self.exec(
            "INSERT INTO note.table_cell (table_id, x, y, cell_type, input_value, display_format, display_value, text_align)"
            " VALUES (%s, 1, 1, 'number', '=1+2', '整数', '3', '左寄せ')",
            (table_id,),
        )
        self.exec("INSERT INTO note.table_col_width (table_id, x, width_px) VALUES (%s, 1, 120)", (table_id,))
        return self.part(aid, file_id, dorder, "table", str(table_id))

    def checklist(
        self, aid: int, file_id: int, dorder: int, title: str, categories: list[tuple[str, list[tuple[str, bool, bool]], bool]],
    ) -> int:
        """categories = [(名前, [(項目のタイトル, チェック, 削除済み)], カテゴリが削除済みか)]。"""
        checklist_id = self.one("INSERT INTO note.checklist (aid, title) VALUES (%s, %s) RETURNING id", (aid, title))
        for index, (name, items, cat_deleted) in enumerate(categories):
            cat_id = self.one(
                "INSERT INTO note.checklist_category (checklist_id, name, dorder, is_deleted) VALUES (%s, %s, %s, %s) RETURNING id",
                (checklist_id, name, index, cat_deleted),
            )
            for item_index, (item_title, checked, item_deleted) in enumerate(items):
                self.exec(
                    "INSERT INTO note.checklist_item (checklist_id, category_id, title, is_checked, dorder, is_deleted)"
                    " VALUES (%s, %s, %s, %s, %s, %s)",
                    (checklist_id, cat_id, item_title, checked, item_index, item_deleted),
                )
        return self.part(aid, file_id, dorder, "checklist", str(checklist_id))


@pytest.fixture()
def src(source_db_name: str) -> Iterator[Source]:
    conn = _admin_connect(source_db_name)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            'TRUNCATE note.checklist_item, note.checklist_category, note.checklist, note.table_col_width, note.table_cell, note."table",'
            " note.parts_revision, note.parts, note.file, note.folder, public.accounts RESTART IDENTITY CASCADE"
        )
    yield Source(conn)
    conn.close()


@pytest.fixture(autouse=True)
def keep_test_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() がログの出力先を backend/log へ切り替えないようにする（テスト用の出力先を使い続ける）。"""
    monkeypatch.setattr(mig, "setup_logging", lambda: None)


class Runner:
    def __init__(self, db_name: str) -> None:
        self.db_name = db_name

    def run(self, username: str, *, dry_run: bool = False) -> tuple[mig.Report, str]:
        source = _admin_connect(self.db_name, dict_rows=True)
        source.set_session(readonly=True)
        target = connect()
        out = io.StringIO()
        try:
            report = mig.run(source, target, mig.Options(username=username, dry_run=dry_run), out)
        finally:
            source.close()
            target.close()
        return report, out.getvalue()


@pytest.fixture()
def migrate(source_db_name: str) -> Runner:
    return Runner(source_db_name)


@pytest.fixture()
def account(src: Source, user: TestUser) -> int:
    """移行元に、移行先の利用者と同じ名前のアカウントを作る。"""
    return src.account(user.username)


def rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def target_folders(user: TestUser) -> dict[str, dict[str, Any]]:
    result = rows(
        "SELECT f.id, f.name, f.sort_order, f.is_deleted, p.name AS parent FROM note_management.folders f"
        " LEFT JOIN note_management.folders p ON p.id = f.parent_id WHERE f.user_id = %s ORDER BY f.id",
        (user.id,),
    )
    return {r["name"]: r for r in result}


def target_file(user: TestUser, title: str) -> dict[str, Any]:
    return rows("SELECT * FROM note_management.files WHERE user_id = %s AND title = %s", (user.id, title))[0]


def target_parts(file_id: int) -> list[dict[str, Any]]:
    return rows("SELECT * FROM note_management.parts WHERE file_id = %s ORDER BY sort_order", (file_id,))


def count(user: TestUser, table: str) -> int:
    return rows(f"SELECT count(*) AS n FROM note_management.{table} WHERE user_id = %s", (user.id,))[0]["n"]


def seed_basic(src: Source, aid: int) -> dict[str, int]:
    root = src.folder(aid, "旅行", None, 1)
    child = src.folder(aid, "国内", root, 1)
    trash = src.folder(aid, "ごみ箱", None, 2, deleted=1)
    f1 = src.file(aid, child, "持ち物", 1)
    return {"root": root, "child": child, "trash": trash, "file": f1}


# ---- 利用者の指定 -----------------------------------------------------------


def test_missing_accounts_abort_without_writing(src: Source, migrate: Runner, user: TestUser, make_user: Callable[..., TestUser]) -> None:
    aid = src.account(user.username)
    seed_basic(src, aid)
    deleted = make_user(deleted=True)
    src.account(deleted.username)
    src.account("nm_only_in_source")
    for name, message in (
        ("nm_only_in_target_" + uuid.uuid4().hex[:6], "移行元に、アカウント"),
        (deleted.username, "論理削除済み"),
        ("nm_only_in_source", "移行先に、利用者"),
    ):
        with pytest.raises(mig.MigrationAbort) as err:
            migrate.run(name)
        assert message in str(err.value), name
    assert count(user, "folders") == 0 and count(deleted, "folders") == 0


def test_username_is_required() -> None:
    with pytest.raises(SystemExit):
        mig._parse_args(["--host", "x"])


# ---- フォルダ ---------------------------------------------------------------


def test_folders_are_migrated_with_hierarchy_order_and_deleted_state(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    root = src.folder(account, "A", None, 3)
    src.folder(account, "B", None, 7, deleted=1)
    c1 = src.folder(account, "c1", root, 5)
    src.folder(account, "c2", root, 9, deleted=2)
    src.folder(account, "gc", c1, 1)  # 深い階層
    report, out = migrate.run(user.username)
    assert report.failures == 0
    assert (report.count("folder", "migrated"), report.count("folder", "skipped")) == (5, 0)
    folders = target_folders(user)
    assert {n: (f["parent"], f["sort_order"], f["is_deleted"]) for n, f in folders.items()} == {
        "A": (None, 3, False), "B": (None, 7, True), "c1": ("A", 5, False), "c2": ("A", 9, True), "gc": ("c1", 1, False),
    }
    assert "[1/0]" not in out  # ファイルがなければ、進捗は出ない


def test_deleted_folders_with_same_name_are_all_migrated(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    src.folder(account, "dup", None, 1, deleted=1)
    src.folder(account, "dup", None, 2, deleted=2)
    src.folder(account, "dup", None, 3, deleted=0)
    report, _ = migrate.run(user.username)
    assert report.count("folder", "migrated") == 3
    got = rows("SELECT sort_order, is_deleted FROM note_management.folders WHERE user_id = %s AND name = 'dup' ORDER BY sort_order", (user.id,))
    assert [(r["sort_order"], r["is_deleted"]) for r in got] == [(1, True), (2, True), (3, False)]
    again, _ = migrate.run(user.username)  # 再実行しても、増えない
    assert (again.count("folder", "migrated"), again.count("folder", "skipped"), again.failures) == (0, 3, 0)
    assert count(user, "folders") == 3


def test_existing_folder_with_same_name_is_reused_and_sort_order_conflict_is_resolved(
    src: Source, migrate: Runner, user: TestUser, account: int
) -> None:
    mine = user.client.post("/folders", json={"parent_id": None, "name": "既存"}).json()  # 並び順 1
    other = user.client.post("/folders", json={"parent_id": None, "name": "別"}).json()  # 並び順 2
    src.folder(account, "既存", None, 1)
    new_root = src.folder(account, "新規", None, 2)  # 並び順 2 は移行先で使用済み → 末尾に付く
    src.file(account, new_root, "f", 1)
    report, _ = migrate.run(user.username)
    assert (report.count("folder", "skipped"), report.count("folder", "migrated")) == (1, 1)
    folders = target_folders(user)
    assert folders["既存"]["id"] == mine["id"] and folders["別"]["id"] == other["id"]
    assert folders["新規"]["sort_order"] == 3
    assert count(user, "folders") == 3


# ---- ファイル・パーツ ---------------------------------------------------------


def test_files_and_all_part_types_are_migrated(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    fid = ids["file"]
    action = json.dumps({"points": [{"place": "東京駅", "time": "9:00"}], "legs": []}, ensure_ascii=False)
    markers = json.dumps([{"id": "m1", "kind": "house", "x": 0.1, "y": 0.2, "text": "宿"}], ensure_ascii=False)
    src.part(account, fid, 1, "text", "本文\n2 行目")
    src.part(account, fid, 2, "md", "# 見出し")
    src.part(account, fid, 3, "tex", "x^2")
    src.part(account, fid, 4, "url", "https://example.com")
    src.part(account, fid, 5, "action", action)
    src.part(account, fid, 6, "png", b64(PNG), filename="map.png", title="地図", markers=markers, scale=1.5)
    src.part(account, fid, 7, "jpeg", b64(JPEG), filename="a.jpg")
    src.part(account, fid, 8, "binary", b64(bytes(range(256)) * 20), filename="資料.bin")
    src.checklist(account, fid, 9, "買い物", [("", [("牛乳", True, False)], False), ("日用品", [("洗剤", False, False)], False)])
    report, out = migrate.run(user.username)
    assert report.failures == 0
    assert (report.count("file", "migrated"), report.count("part", "migrated"), report.count("checklist", "migrated")) == (1, 9, 1)
    assert "[1/1] 旅行/国内/持ち物" in out

    file_row = target_file(user, "持ち物")
    assert file_row["folder_id"] == target_folders(user)["国内"]["id"]
    detail = user.client.get(f"/files/{file_row['id']}").json()
    parts = detail["parts"]
    assert [p["type"] for p in parts] == ["text", "md", "tex", "url", "action", "png", "jpeg", "binary", "checklist"]
    assert [p["sort_order"] for p in parts] == list(range(1, 10))
    assert (parts[0]["data"], parts[1]["data"], parts[2]["data"], parts[3]["data"]) == ("本文\n2 行目", "# 見出し", "x^2", "https://example.com")
    assert json.loads(parts[4]["data"]) == json.loads(action)
    png = parts[5]
    assert (png["filename"], png["title"], png["image_scale"], png["byte_size"], png["markers"]) == ("map.png", "地図", 1.5, len(PNG), json.loads(markers))
    assert (parts[7]["filename"], parts[7]["byte_size"]) == ("資料.bin", 5120)
    # 画像・バイナリの中身が一致する
    assert user.client.get(f"/parts/{png['id']}/content").content == PNG
    assert user.client.get(f"/parts/{parts[6]['id']}/content").content == JPEG
    assert user.client.get(f"/parts/{parts[7]['id']}/content").content == bytes(range(256)) * 20
    # チェックリスト: パーツの参照が、新しい識別子に付け替えられている
    state = user.client.get(f"/checklists/{parts[8]['checklist_id']}").json()
    assert state["title"] == "買い物"
    assert [(c["name"], [(i["title"], i["is_checked"]) for i in c["items"]]) for c in state["categories"]] == [
        ("", [("牛乳", True)]), ("日用品", [("洗剤", False)]),
    ]
    assert rows("SELECT data FROM note_management.parts WHERE id = %s", (parts[8]["id"],))[0]["data"] == ""


def test_data_is_identical_including_large_binary(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    big = os.urandom(3 * 1024 * 1024)
    part_id = src.part(account, ids["file"], 1, "binary", b64(big), filename="big.bin")
    migrate.run(user.username)
    file_row = target_file(user, "持ち物")
    part = target_parts(file_row["id"])[0]
    assert part["data"] == b64(big) and part["byte_size"] == len(big)
    assert hashlib.md5(user.client.get(f"/parts/{part['id']}/content").content).hexdigest() == hashlib.md5(big).hexdigest()
    assert part_id  # 移行元の識別子とは別に、新しく採番される


def test_table_parts_are_excluded_and_listed(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "text", "前")
    src.table_part(account, ids["file"], 2)
    src.part(account, ids["file"], 3, "text", "後")
    report, _ = migrate.run(user.username)
    assert (report.count("part", "migrated"), report.count("part", "excluded"), report.failures) == (2, 1, 0)
    detail = " ".join(report.details[("part", "excluded")])
    assert "旅行/国内/持ち物" in detail and "並び順2" in detail and "表のパーツ" in detail
    parts = target_parts(target_file(user, "持ち物")["id"])
    assert [(p["ptype"], p["sort_order"]) for p in parts] == [("text", 1), ("text", 3)]  # 並び順は、移行元の値のまま（欠番は残る）
    assert "table" not in {r["ptype"] for r in rows("SELECT ptype FROM note_management.parts WHERE user_id = %s", (user.id,))}


def test_deleted_files_and_parts_keep_deleted_state(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "text", "生きている")
    src.part(account, ids["file"], 2, "text", "削除済み", deleted=True)
    gone = src.file(account, ids["child"], "同名", 2, deleted=1)
    src.file(account, ids["child"], "同名", 3, deleted=2)
    src.part(account, gone, 1, "text", "x")
    in_trash = src.file(account, ids["trash"], "ごみ箱の中", 1)
    src.part(account, in_trash, 1, "text", "y")
    report, _ = migrate.run(user.username)
    assert report.failures == 0 and report.count("file", "migrated") == 4
    assert [(p["data"], p["is_deleted"]) for p in target_parts(target_file(user, "持ち物")["id"])] == [("生きている", False), ("削除済み", True)]
    same = rows("SELECT sort_order, is_deleted FROM note_management.files WHERE user_id = %s AND title = '同名' ORDER BY sort_order", (user.id,))
    assert [(r["sort_order"], r["is_deleted"]) for r in same] == [(2, True), (3, True)]
    trash_file = target_file(user, "ごみ箱の中")
    assert trash_file["is_deleted"] is False  # ファイル自身の行は変わらず、上位が削除済み
    body = user.client.get(f"/files/{trash_file['id']}").json()
    assert (body["is_deleted"], body["ancestor_deleted"]) == (False, True)
    assert target_folders(user)["ごみ箱"]["is_deleted"] is True
    # 移行後、画面（API）から削除解除できる
    trash = target_folders(user)["ごみ箱"]
    assert user.client.post(f"/folders/{trash['id']}/undelete").status_code == 200


def test_revisions_are_migrated(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    part_id = src.part(account, ids["file"], 1, "png", b64(PNG), filename="now.png")
    src.revision(account, part_id, 1, "png", "old1.png", b64(JPEG.replace(JPEG[:3], PNG[:3])), "2026-03-04 05:06:07")
    src.revision(account, part_id, 2, "binary", "old2.bin", b64(b"\x00\x01\x02"), "2026-03-05 05:06:07")
    other = src.part(account, ids["file"], 2, "text", "no revisions")
    report, _ = migrate.run(user.username)
    assert (report.failures, report.count("revision", "migrated")) == (0, 2)
    part = target_parts(target_file(user, "持ち物")["id"])[0]
    revs = rows("SELECT revision_number, ptype, filename, data, byte_size, created_at FROM note_management.part_revisions WHERE part_id = %s ORDER BY revision_number", (part["id"],))
    assert [(r["revision_number"], r["ptype"], r["filename"], r["byte_size"]) for r in revs] == [(1, "png", "old1.png", len(JPEG)), (2, "binary", "old2.bin", 3)]
    assert revs[1]["data"] == b64(b"\x00\x01\x02")
    assert (revs[0]["created_at"].year, revs[0]["created_at"].month, revs[0]["created_at"].day) == (2026, 3, 4)
    detail = user.client.get(f"/files/{target_file(user, '持ち物')['id']}").json()["parts"][0]
    assert [r["revision_number"] for r in detail["revisions"]] == [2, 1]
    assert user.client.get(f"/part-revisions/{detail['revisions'][0]['id']}/content").content == b"\x00\x01\x02"
    assert other


def test_checklist_deleted_entries_are_excluded_and_counted(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    src.checklist(
        account, ids["file"], 1, "T",
        [
            ("", [("生存", False, False), ("削除済み項目", False, True)], False),
            ("消えたカテゴリ", [("中の項目", True, True), ("削除漏れの項目", False, False)], True),  # カテゴリが削除済みなら、中の項目も対象外
            ("残る", [], False),
        ],
    )
    report, _ = migrate.run(user.username)
    assert report.failures == 0
    assert (report.count("category", "migrated"), report.count("category", "excluded")) == (2, 1)
    assert (report.count("item", "migrated"), report.count("item", "excluded")) == (1, 3)
    text = io.StringIO()
    report.print(text)
    assert "削除済みのカテゴリ 1 件" in text.getvalue() and "削除済みの項目 3 件" in text.getvalue()
    file_row = target_file(user, "持ち物")
    part = user.client.get(f"/files/{file_row['id']}").json()["parts"][0]
    state = user.client.get(f"/checklists/{part['checklist_id']}").json()
    assert [(c["name"], len(c["items"])) for c in state["categories"]] == [("", 1), ("残る", 0)]
    assert part["type"] == "checklist"


def test_unparsable_markers_become_empty(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "png", b64(PNG), filename="a.png", markers="not json")
    src.part(account, ids["file"], 2, "png", b64(PNG), filename="b.png", markers='{"a": 1}')
    report, _ = migrate.run(user.username)
    assert report.failures == 0
    assert [p["markers"] for p in target_parts(target_file(user, "持ち物")["id"])] == [[], []]


# ---- 失敗・再実行・ドライラン ---------------------------------------------------


def test_failed_file_leaves_nothing_and_next_one_continues(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    ok = src.file(account, ids["child"], "正常", 2)
    src.part(account, ok, 1, "text", "ok")
    bad = src.file(account, ids["child"], "壊れている", 3)
    src.part(account, bad, 1, "text", "1つ目は正常")
    src.part(account, bad, 2, "png", b64(PNG), filename="")  # ファイル名が空（移行先の制約で拒否される）
    unknown = src.file(account, ids["child"], "種別が想定外", 4)
    src.part(account, unknown, 1, "weird", "x")
    broken64 = src.file(account, ids["child"], "Base64 が壊れている", 5)
    src.part(account, broken64, 1, "binary", "***not base64***", filename="a.bin")
    report, _ = migrate.run(user.username)
    assert (report.count("file", "migrated"), report.count("file", "failed")) == (2, 3)  # 「持ち物」（パーツなし）と「正常」
    assert report.failures == 3
    failed = " ".join(report.details[("file", "failed")])
    for title in ("壊れている", "種別が想定外", "Base64 が壊れている"):
        assert title in failed
    titles = {r["title"] for r in rows("SELECT title FROM note_management.files WHERE user_id = %s", (user.id,))}
    assert titles == {"持ち物", "正常"}  # 失敗したファイルは、ファイルも途中のパーツも残らない
    assert count(user, "parts") == 1
    text = io.StringIO()
    report.print(text)
    assert "失敗が 3 件" in text.getvalue()


def test_resume_after_partial_failure(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    ok = src.file(account, ids["child"], "先", 2)
    src.part(account, ok, 1, "text", "ok")
    bad = src.file(account, ids["child"], "途中で壊れる", 3)
    bad_part = src.part(account, bad, 1, "png", b64(PNG), filename="")
    report, _ = migrate.run(user.username)
    assert (report.count("file", "migrated"), report.count("file", "failed")) == (2, 1)  # 「持ち物」「先」
    src.exec("UPDATE note.parts SET filename = 'fixed.png' WHERE id = %s", (bad_part,))
    again, _ = migrate.run(user.username)
    assert (again.count("file", "migrated"), again.count("file", "skipped"), again.failures) == (1, 2, 0)
    assert again.count("folder", "skipped") == 3
    assert {r["title"] for r in rows("SELECT title FROM note_management.files WHERE user_id = %s", (user.id,))} == {"持ち物", "先", "途中で壊れる"}
    third, _ = migrate.run(user.username)
    assert (third.count("file", "migrated"), third.count("file", "skipped")) == (0, 3)
    assert count(user, "files") == 3 and count(user, "parts") == 2


def test_rerun_does_not_duplicate_anything(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    part = src.part(account, ids["file"], 1, "png", b64(PNG), filename="a.png")
    src.revision(account, part, 1, "png", "o.png", b64(PNG))
    src.checklist(account, ids["file"], 2, "T", [("", [("a", False, False)], False)])
    first, _ = migrate.run(user.username)
    snapshot = {t: count(user, t) for t in ("folders", "files", "parts", "part_revisions", "checklists")}
    again, _ = migrate.run(user.username)
    assert again.failures == 0 and again.count("file", "migrated") == 0
    assert {t: count(user, t) for t in snapshot} == snapshot
    assert first.count("part", "migrated") == 2


def test_existing_file_with_same_title_is_skipped_and_not_overwritten(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "text", "移行元の本文")
    folder = user.client.post("/folders", json={"parent_id": None, "name": "旅行"}).json()
    child = user.client.post("/folders", json={"parent_id": folder["id"], "name": "国内"}).json()
    mine = user.client.post("/files", json={"folder_id": child["id"], "title": "持ち物"}).json()
    user.client.post(f"/files/{mine['id']}/parts", json={"type": "text", "data": "自分の本文"})
    report, _ = migrate.run(user.username)
    assert (report.count("file", "skipped"), report.count("file", "migrated")) == (1, 0)
    assert [p["data"] for p in user.client.get(f"/files/{mine['id']}").json()["parts"]] == ["自分の本文"]


def test_dry_run_writes_nothing(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    part = src.part(account, ids["file"], 1, "png", b64(PNG), filename="a.png")
    src.revision(account, part, 1, "png", "o.png", b64(PNG))
    src.table_part(account, ids["file"], 2)
    src.checklist(account, ids["file"], 3, "T", [("", [("a", False, False), ("d", False, True)], False)])
    report, out = migrate.run(user.username, dry_run=True)
    assert report.dry_run and report.failures == 0
    assert (report.count("folder", "migrated"), report.count("file", "migrated"), report.count("part", "migrated")) == (3, 1, 2)
    assert (report.count("part", "excluded"), report.count("revision", "migrated"), report.count("checklist", "migrated")) == (1, 1, 1)
    assert (report.count("item", "migrated"), report.count("item", "excluded")) == (1, 1)
    assert all(count(user, t) == 0 for t in ("folders", "files", "parts", "part_revisions", "checklists"))
    text = io.StringIO()
    report.print(text)
    assert "ドライラン" in text.getvalue() and "移行予定" in text.getvalue()
    assert "[1/1] 旅行/国内/持ち物" in out
    # 実行後にドライランをすると、移行済みは「スキップ」と見込まれる
    migrate.run(user.username)
    again, _ = migrate.run(user.username, dry_run=True)
    assert (again.count("folder", "skipped"), again.count("file", "skipped"), again.count("file", "migrated")) == (3, 1, 0)


def test_dry_run_reports_failures_without_writing(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "weird", "x")
    report, _ = migrate.run(user.username, dry_run=True)
    assert report.count("file", "failed") == 1


def test_other_accounts_are_not_migrated(src: Source, migrate: Runner, user: TestUser, account: int) -> None:
    other = src.account("someone_else")
    src.folder(other, "他人のフォルダ", None, 1)
    src.folder(account, "自分のフォルダ", None, 1)
    report, _ = migrate.run(user.username)
    assert report.count("folder", "migrated") == 1
    assert set(target_folders(user)) == {"自分のフォルダ"}


def test_source_is_never_modified_and_connection_is_read_only(src: Source, migrate: Runner, user: TestUser, account: int, source_db_name: str) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "text", "x")
    src.checklist(account, ids["file"], 2, "T", [("", [("a", False, False)], False)])

    def snapshot() -> list[int]:
        tables = ("folder", "file", "parts", "parts_revision", "checklist", "checklist_category", "checklist_item")
        return [src.one(f"SELECT count(*) FROM note.{t}") for t in tables]

    before = snapshot()
    migrate.run(user.username)
    migrate.run(user.username, dry_run=True)
    assert snapshot() == before
    args = mig._parse_args(["--username", "x", "--host", "localhost", "--dbname", source_db_name,
                            "--user", ADMIN["user"], "--password", ADMIN["password"]])[0]
    conn = mig.open_source(args)
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
                cur.execute("INSERT INTO note.folder (aid, name, dorder) VALUES (1, 'x', 1)")
    finally:
        conn.close()


# ---- 接続・終了コード・ログ -----------------------------------------------------


def _argv(source_db_name: str, username: str, *extra: str) -> list[str]:
    return ["--username", username, "--host", "localhost", "--dbname", source_db_name,
            "--user", ADMIN["user"], "--password", ADMIN["password"], *extra]


def test_main_reports_source_connection_failure(capsys: pytest.CaptureFixture[str], log_dir: Path) -> None:
    code = mig.main(["--username", "x", "--host", "127.0.0.1", "--port", "1", "--dbname", "nope",
                     "--user", "u", "--password", "secret-pass-xyz"])
    err = capsys.readouterr().err
    assert code == 2
    assert "移行元DB" in err and "移行先DB" not in err
    assert "secret-pass-xyz" not in err and "secret-pass-xyz" not in log_text(log_dir)


def test_main_reports_target_connection_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], source_db_name: str, log_dir: Path
) -> None:
    def broken() -> Any:
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(mig, "connect_target", broken)
    code = mig.main(_argv(source_db_name, "someone"))
    err = capsys.readouterr().err
    assert code == 2 and "移行先DB" in err and ADMIN["password"] not in err


def test_main_aborts_when_user_is_missing(capsys: pytest.CaptureFixture[str], source_db_name: str, src: Source) -> None:
    code = mig.main(_argv(source_db_name, "nm_no_such_user"))
    err = capsys.readouterr().err
    assert code == 2
    assert "nm_no_such_user" in err and "何も移行せずに終了" in err


def test_main_exit_code_and_report(
    capsys: pytest.CaptureFixture[str], src: Source, source_db_name: str, user: TestUser, account: int, log_dir: Path
) -> None:
    ids = seed_basic(src, account)
    src.part(account, ids["file"], 1, "text", "本文の秘密")
    assert mig.main(_argv(source_db_name, user.username)) == 0
    err = capsys.readouterr().err
    assert "フォルダ: 移行 3 / スキップ 0 / 対象外 0 / 失敗 0" in err
    assert "ファイル: 移行 1 / スキップ 0 / 対象外 0 / 失敗 0" in err
    assert "[1/1]" in err and ADMIN["password"] not in err
    text = log_text(log_dir)
    assert "移行開始" in text and "移行終了" in text and "ファイル移行成功" in text
    assert ADMIN["password"] not in text and "本文の秘密" not in text  # パスワードも、パーツの中身も出さない
    bad = src.file(account, ids["child"], "壊れた", 2)
    src.part(account, bad, 1, "weird", "x")
    assert mig.main(_argv(source_db_name, user.username)) == 1  # 失敗があれば 0 以外
    err = capsys.readouterr().err
    assert "ファイル: 移行 0 / スキップ 1 / 対象外 0 / 失敗 1" in err and "壊れた" in err
