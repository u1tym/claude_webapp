"""移行プログラム（scripts/migrate_from_recipe.py）のテスト。

移行元は、サンプルの構造を再現した一時的な DB（管理者で作成し、テスト後に削除）、
移行先は開発用 DB（backend/.env）を使う。管理者で接続できないときは、このファイルのテストを飛ばす。
"""

from __future__ import annotations

import io
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
import migrate_from_recipe as mig  # noqa: E402

ADMIN = {
    "user": os.environ.get("PG_ADMIN_USER", "postgres"),
    "password": os.environ.get("PG_ADMIN_PASSWORD", "postgres"),
}
FIXTURE_SQL = Path(__file__).resolve().parent / "fixtures" / "source_recipe.sql"


def _admin_connect(dbname: str, dict_rows: bool = False) -> psycopg2.extensions.connection:
    cfg = load_config()
    return psycopg2.connect(
        host=cfg.db_server, port=cfg.db_port, dbname=dbname,
        cursor_factory=RealDictCursor if dict_rows else None, **ADMIN,
    )


@pytest.fixture(scope="module")
def source_db_name() -> Iterator[str]:
    name = f"rm_src_{uuid.uuid4().hex[:10]}"
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

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def ingredient(self, name: str, kana: str = "かな") -> int:
        return self._one("INSERT INTO recipe.ingredient (name, kana) VALUES (%s, %s) RETURNING id", (name, kana))

    def measurement(self, bef: str, aft: str, ness: bool) -> int:
        return self._one(
            "INSERT INTO recipe.measurements (name_bef, name_aft, ness_amount) VALUES (%s, %s, %s) RETURNING id",
            (bef, aft, ness),
        )

    def menu(
        self, name: str, steps: list[tuple[str, list[tuple[int, int, str]]]], *, kana: str = "かな", deleted: bool = False,
        step_numbers: list[int] | None = None,
    ) -> int:
        """steps = [(説明, [(材料ID, 分量名称ID, 数量)])]。"""
        menu_id = self._one(
            "INSERT INTO recipe.menu (name, kana, is_deleted) VALUES (%s, %s, %s) RETURNING id", (name, kana, deleted)
        )
        for index, (description, items) in enumerate(steps):
            number = step_numbers[index] if step_numbers else index + 1
            step_id = self._one(
                "INSERT INTO recipe.menu_step (menu_id, step, description) VALUES (%s, %s, %s) RETURNING id",
                (menu_id, number, description),
            )
            for ingredient_id, measurement_id, amount in items:
                self._exec(
                    "INSERT INTO recipe.menu_step_ingredient (menu_step_id, ingredient_id, measurement_id, amount)"
                    " VALUES (%s, %s, %s, %s)",
                    (step_id, ingredient_id, measurement_id, amount),
                )
        return menu_id


@pytest.fixture()
def src(source_db_name: str) -> Iterator[Source]:
    conn = _admin_connect(source_db_name)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE recipe.menu_step_ingredient, recipe.menu_step, recipe.menu, recipe.measurements, recipe.ingredient "
            "RESTART IDENTITY CASCADE"
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


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _common_ids(user: TestUser) -> tuple[int, int, int]:
    """共通の砂糖・大さじ・cc の、移行先の識別子（移行元の識別子とは別に採番されている）。"""
    ing = _rows("SELECT id FROM recipe_management.ingredients WHERE user_id IS NULL AND name = '砂糖'")[0]["id"]
    tbsp = _rows("SELECT id FROM recipe_management.measurements WHERE user_id IS NULL AND name_bef = '大さじ'")[0]["id"]
    cc = _rows("SELECT id FROM recipe_management.measurements WHERE user_id IS NULL AND name_aft = 'cc'")[0]["id"]
    return ing, tbsp, cc


def _seed_basic(src: Source) -> dict[str, int]:
    ids = {
        "sugar": src.ingredient("砂糖", "さとう"),
        "daikon": src.ingredient("大根", "だいこん"),
        "tbsp": src.measurement("大さじ", "", True),
        "gram": src.measurement("", "g", True),
        "pinch": src.measurement("ひとつまみ", "", False),
    }
    ids["menu"] = src.menu(
        "大根の煮物",
        [
            ("切る", [(ids["daikon"], ids["gram"], "200"), (ids["sugar"], ids["tbsp"], "1")]),
            ("煮る", []),
            ("味をととのえる", [(ids["sugar"], ids["pinch"], "")]),
        ],
        kana="だいこんのにもの",
    )
    return ids


def _target_recipe(user: TestUser, name: str) -> dict[str, Any]:
    items = user.client.get("/recipes").json()["items"]
    recipe_id = next(i["id"] for i in items if i["name"] == name)
    return user.client.get(f"/recipes/{recipe_id}").json()


# ---- 利用者の指定 -----------------------------------------------------------


def test_missing_or_deleted_user_aborts_without_writing(
    src: Source, migrate: Runner, make_user: Callable[..., TestUser]
) -> None:
    _seed_basic(src)
    deleted = make_user(deleted=True)
    before = _rows("SELECT count(*) AS n FROM recipe_management.ingredients")[0]["n"]
    for name in ("rm_no_such_user", deleted.username):
        with pytest.raises(mig.MigrationAbort):
            migrate.run(name)
    assert _rows("SELECT count(*) AS n FROM recipe_management.ingredients")[0]["n"] == before
    assert _rows("SELECT count(*) AS n FROM recipe_management.recipes WHERE user_id = %s", (deleted.id,))[0]["n"] == 0


def test_username_is_required() -> None:
    with pytest.raises(SystemExit):
        mig._parse_args(["--host", "x"])


# ---- 移行の内容 ---------------------------------------------------------------


def test_recipe_is_migrated_with_values_and_order(src: Source, migrate: Runner, user: TestUser) -> None:
    ids = _seed_basic(src)
    report, out = migrate.run(user.username)
    assert report.failures == 0
    assert (report.count("recipe", "migrated"), report.count("step", "migrated"), report.count("item", "migrated")) == (1, 3, 3)
    recipe = _target_recipe(user, "大根の煮物")
    assert recipe["kana"] == "だいこんのにもの"
    assert [s["step_no"] for s in recipe["steps"]] == [1, 2, 3]
    assert [s["description"] for s in recipe["steps"]] == ["切る", "煮る", "味をととのえる"]
    first, second, third = recipe["steps"]
    assert second["items"] == []
    assert [i["item_no"] for i in first["items"]] == [1, 2]  # 移行元の識別子の順
    assert [(i["ingredient"]["name"], i["amount"]) for i in first["items"]] == [("大根", "200"), ("砂糖", "1")]
    assert third["items"][0]["measurement"]["ness_amount"] is False and third["items"][0]["amount"] == ""
    assert "[1/1] 大根の煮物" in out


def test_masters_are_mapped_to_common_or_added_as_own(src: Source, migrate: Runner, user: TestUser) -> None:
    _seed_basic(src)
    report, _ = migrate.run(user.username)
    sugar, tbsp, _ = _common_ids(user)
    recipe = _target_recipe(user, "大根の煮物")
    used = {i["ingredient"]["name"]: i["ingredient"] for s in recipe["steps"] for i in s["items"]}
    assert used["砂糖"]["id"] == sugar and used["砂糖"]["is_system"] is True  # 共通に対応付け
    assert used["大根"]["is_system"] is False  # 共通に無いため、独自として追加
    measurements = {(i["measurement"]["name_bef"], i["measurement"]["name_aft"]): i["measurement"] for s in recipe["steps"] for i in s["items"]}
    assert measurements[("大さじ", "")]["id"] == tbsp and measurements[("大さじ", "")]["is_system"] is True
    assert measurements[("", "g")]["is_system"] is False
    assert measurements[("ひとつまみ", "")]["is_system"] is True
    assert (report.count("ingredient", "migrated"), report.count("ingredient", "skipped")) == (1, 1)
    assert (report.count("measurement", "migrated"), report.count("measurement", "skipped")) == (1, 2)
    own = _rows("SELECT name FROM recipe_management.ingredients WHERE user_id = %s", (user.id,))
    assert [r["name"] for r in own] == ["大根"]


def test_existing_own_master_is_reused_and_flag_difference_is_reported(src: Source, migrate: Runner, user: TestUser) -> None:
    daikon = src.ingredient("大根", "だいこん")
    gram = src.measurement("", "g", False)  # 移行元では数量なし
    src.menu("煮物", [("煮る", [(daikon, gram, "")])])
    own_ing = user.client.post("/ingredients", json={"name": "大根", "kana": "だいこん"}).json()["id"]
    own_meas = user.client.post("/measurements", json={"name_bef": "", "name_aft": "g", "ness_amount": True}).json()["id"]
    report, _ = migrate.run(user.username)
    # 数量ありで登録済みの独自を使うため、移行元が「数量なし」でも、数量は移行先の要否に従う
    recipe = _target_recipe(user, "煮物")
    item = recipe["steps"][0]["items"][0]
    assert (item["ingredient"]["id"], item["measurement"]["id"]) == (own_ing, own_meas)
    assert item["measurement"]["ness_amount"] is True  # 既存のものは変更しない
    assert any("数量の要否が違います" in d for d in report.details[("measurement", "skipped")])
    assert len(_rows("SELECT id FROM recipe_management.ingredients WHERE user_id = %s", (user.id,))) == 1
    assert len(_rows("SELECT id FROM recipe_management.measurements WHERE user_id = %s", (user.id,))) == 1


def test_deleted_menu_is_excluded(src: Source, migrate: Runner, user: TestUser) -> None:
    sugar = src.ingredient("砂糖")
    tbsp = src.measurement("大さじ", "", True)
    src.menu("生きている", [("作る", [(sugar, tbsp, "1")])])
    src.menu("消えた", [("作る", [(sugar, tbsp, "1")])], deleted=True)
    report, _ = migrate.run(user.username)
    assert (report.count("recipe", "migrated"), report.count("recipe", "excluded")) == (1, 1)
    assert any("消えた" in d and "削除済み" in d for d in report.details[("recipe", "excluded")])
    assert [i["name"] for i in user.client.get("/recipes").json()["items"]] == ["生きている"]


def test_step_numbers_are_kept_from_source(src: Source, migrate: Runner, user: TestUser) -> None:
    src.menu("飛び番", [("一つ目", []), ("二つ目", [])], step_numbers=[2, 5])
    migrate.run(user.username)
    assert [s["step_no"] for s in _target_recipe(user, "飛び番")["steps"]] == [2, 5]


def test_items_pointing_to_missing_masters_are_dropped_and_listed(src: Source, migrate: Runner, user: TestUser) -> None:
    sugar = src.ingredient("砂糖")
    tbsp = src.measurement("大さじ", "", True)
    src.menu("一部欠け", [("作る", [(sugar, tbsp, "1"), (9999, tbsp, "2"), (sugar, 9999, "3"), (sugar, tbsp, "4")])])
    report, _ = migrate.run(user.username)
    assert report.failures == 0
    assert (report.count("item", "migrated"), report.count("item", "excluded")) == (2, 2)
    items = _target_recipe(user, "一部欠け")["steps"][0]["items"]
    assert [(i["item_no"], i["amount"]) for i in items] == [(1, "1"), (2, "4")]  # 並びは詰め直す
    assert all("一部欠け" in d for d in report.details[("item", "excluded")])


# ---- 失敗・再実行・ドライラン ---------------------------------------------------


def test_failed_recipe_leaves_nothing_and_next_one_continues(src: Source, migrate: Runner, user: TestUser) -> None:
    sugar = src.ingredient("砂糖")
    tbsp = src.measurement("大さじ", "", True)
    src.menu("壊れている", [("正常な手順", [(sugar, tbsp, "1")]), ("   ", [(sugar, tbsp, "2")])])  # 説明が空白だけ（移行先で拒否される）
    src.menu("正常", [("作る", [(sugar, tbsp, "1")])])
    report, _ = migrate.run(user.username)
    assert (report.count("recipe", "migrated"), report.count("recipe", "failed")) == (1, 1)
    assert report.failures == 1
    assert any("壊れている" in d for d in report.details[("recipe", "failed")])
    assert [i["name"] for i in user.client.get("/recipes").json()["items"]] == ["正常"]
    # 途中まで書いた工程・材料の行も残らない
    assert _rows(
        "SELECT count(*) AS n FROM recipe_management.recipe_steps s JOIN recipe_management.recipes r ON r.id = s.recipe_id"
        " WHERE r.user_id = %s AND r.name = '壊れている'", (user.id,)
    )[0]["n"] == 0


def test_rerun_skips_migrated_recipes_and_masters(src: Source, migrate: Runner, user: TestUser) -> None:
    _seed_basic(src)
    first, _ = migrate.run(user.username)
    assert first.count("recipe", "migrated") == 1
    again, _ = migrate.run(user.username)
    assert (again.count("recipe", "migrated"), again.count("recipe", "skipped"), again.failures) == (0, 1, 0)
    assert again.count("ingredient", "migrated") == 0 and again.count("measurement", "migrated") == 0
    assert len(user.client.get("/recipes").json()["items"]) == 1
    assert len(_rows("SELECT id FROM recipe_management.ingredients WHERE user_id = %s", (user.id,))) == 1


def test_existing_recipe_with_same_name_is_skipped_and_not_overwritten(src: Source, migrate: Runner, user: TestUser) -> None:
    _seed_basic(src)
    sugar, tbsp, _ = _common_ids(user)
    mine = user.client.post("/recipes", json={
        "name": "大根の煮物", "kana": "じぶんの", "steps": [{"description": "自分の手順", "items": [
            {"ingredient_id": sugar, "measurement_id": tbsp, "amount": "9"}]}],
    }).json()
    report, _ = migrate.run(user.username)
    assert (report.count("recipe", "skipped"), report.count("recipe", "migrated")) == (1, 0)
    assert user.client.get(f"/recipes/{mine['id']}").json() == mine


def test_resume_after_partial_failure(src: Source, migrate: Runner, user: TestUser) -> None:
    sugar = src.ingredient("砂糖")
    tbsp = src.measurement("大さじ", "", True)
    src.menu("先", [("作る", [(sugar, tbsp, "1")])])
    bad = src.menu("途中で壊れる", [("  ", [(sugar, tbsp, "1")])])
    report, _ = migrate.run(user.username)
    assert (report.count("recipe", "migrated"), report.count("recipe", "failed")) == (1, 1)
    src._exec("UPDATE recipe.menu_step SET description = '直した手順' WHERE menu_id = %s", (bad,))
    again, _ = migrate.run(user.username)
    assert (again.count("recipe", "migrated"), again.count("recipe", "skipped"), again.failures) == (1, 1, 0)
    assert sorted(i["name"] for i in user.client.get("/recipes").json()["items"]) == ["先", "途中で壊れる"]


def test_dry_run_writes_nothing(src: Source, migrate: Runner, user: TestUser) -> None:
    _seed_basic(src)
    report, out = migrate.run(user.username, dry_run=True)
    assert report.dry_run
    assert (report.count("recipe", "migrated"), report.count("step", "migrated"), report.count("item", "migrated")) == (1, 3, 3)
    assert (report.count("ingredient", "migrated"), report.count("measurement", "migrated")) == (1, 1)  # 移行予定
    assert user.client.get("/recipes").json()["items"] == []
    assert _rows("SELECT id FROM recipe_management.ingredients WHERE user_id = %s", (user.id,)) == []
    assert _rows("SELECT id FROM recipe_management.measurements WHERE user_id = %s", (user.id,)) == []
    text = io.StringIO()
    report.print(text)
    assert "ドライラン" in text.getvalue() and "移行予定" in text.getvalue()
    assert "[1/1]" in out


def test_source_is_never_modified_and_connection_is_read_only(src: Source, migrate: Runner, user: TestUser, source_db_name: str) -> None:
    _seed_basic(src)

    def snapshot() -> list[int]:
        return [src._one(f"SELECT count(*) FROM recipe.{t}") for t in ("ingredient", "measurements", "menu", "menu_step", "menu_step_ingredient")]

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
                cur.execute("INSERT INTO recipe.ingredient (name, kana) VALUES ('x', 'x')")
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
    _seed_basic(src)
    code = mig.main(_argv(source_db_name, "rm_no_such_user"))
    err = capsys.readouterr().err
    assert code == 2
    assert "rm_no_such_user" in err and "何も移行せずに終了" in err


def test_main_exit_code_and_report(
    capsys: pytest.CaptureFixture[str], src: Source, source_db_name: str, user: TestUser, log_dir: Path
) -> None:
    _seed_basic(src)
    assert mig.main(_argv(source_db_name, user.username)) == 0
    err = capsys.readouterr().err
    assert "レシピ: 移行 1 / スキップ 0 / 対象外 0 / 失敗 0" in err
    assert "[1/1]" in err and ADMIN["password"] not in err
    text = log_text(log_dir)
    assert "移行開始" in text and "移行終了" in text and ADMIN["password"] not in text
    sugar = src.ingredient("塩")  # 壊れたレシピを加える
    src.menu("壊れた", [("  ", [(sugar, 1, "1")])])
    assert mig.main(_argv(source_db_name, user.username)) == 1  # 失敗があれば 0 以外
    err = capsys.readouterr().err
    assert "レシピ: 移行 0 / スキップ 1 / 対象外 0 / 失敗 1" in err and "壊れた" in err
