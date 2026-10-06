from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.db import get_conn
from app.logger import LOG_FILE
from app.main import app as room_app
from helpers import assign_feature, ensure_feature, insert_api_key, insert_session, insert_user, unique

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


@pytest.fixture
def ctx() -> Iterator[tuple[TestClient, int]]:
    """ログイン済みのクライアントとユーザ ID。終了時に、このユーザが作った定期実行を消す。"""
    ensure_feature()
    user_id = insert_user(unique("room_sched"))
    assign_feature(user_id)
    client = TestClient(room_app)
    client.cookies.set(
        "session_id", str(insert_session(user_id, load_config().session_timeout_minutes))
    )
    yield client, user_id
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE created_by_user_id = %s", (user_id,))


def _mine(user_id: int) -> list[int]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM room.room_schedules WHERE created_by_user_id = %s ORDER BY id",
            (user_id,),
        )
        return [int(r["id"]) for r in cur.fetchall()]


def _valid(**override: object) -> dict[str, object]:
    body: dict[str, object] = {
        "condition": "daily",
        "run_time": "07:00",
        "scene": "indoor_speaker",
    }
    body.update(override)
    return body


def _create(client: TestClient, **override: object) -> dict[str, object]:
    res = client.post("/schedules", json=_valid(**override))
    assert res.status_code == 201, res.text
    return res.json()


# ---- 登録 ----


def test_毎日の定期実行を登録できる(ctx: tuple[TestClient, int], log_dir: Path) -> None:
    client, user_id = ctx
    res = client.post("/schedules", json=_valid())

    assert res.status_code == 201
    body = res.json()
    assert isinstance(body["id"], int)
    assert {k: v for k, v in body.items() if k != "id"} == {
        "condition": "daily",
        "weekdays": [],
        "holiday_mode": "none",
        "day_shift": "same",
        "run_time": "07:00",
        "scene": "indoor_speaker",
        "device": None,
        "state": None,
        "pattern": None,
        "is_enabled": True,  # 既定は有効
        "last_run": None,
    }
    assert _mine(user_id) == [body["id"]]
    log = _log_text(log_dir)
    assert "定期実行の登録要求" in log
    assert "定期実行の登録成功" in log


def test_曜日の指定は昇順で保存される(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    body = _create(client, condition="weekdays", weekdays=[5, 1, 3], run_time="22:30", scene="out")
    assert body["weekdays"] == [1, 3, 5]
    assert body["run_time"] == "22:30"


def test_無効での登録(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    body = _create(client, is_enabled=False, run_time="00:00")
    assert body["is_enabled"] is False
    assert body["run_time"] == "00:00"
    assert _create(client, run_time="23:59")["run_time"] == "23:59"


def test_曜日の空配列はdailyで許す(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    assert _create(client, condition="daily", weekdays=[])["weekdays"] == []


@pytest.mark.parametrize(
    "override",
    [
        {"condition": None},
        {"condition": "monthly"},
        {"condition": 1},
        {"condition": "weekdays"},  # 曜日なし
        {"condition": "weekdays", "weekdays": []},
        {"condition": "weekdays", "weekdays": [0]},
        {"condition": "weekdays", "weekdays": [8]},
        {"condition": "weekdays", "weekdays": [1, 1]},
        {"condition": "weekdays", "weekdays": ["1"]},
        {"condition": "weekdays", "weekdays": [True]},
        {"condition": "weekdays", "weekdays": "1"},
        {"condition": "daily", "weekdays": [1]},
        {"condition": "holiday"},  # 祝日だけの条件は無い
        {"condition": "holiday", "weekdays": [1]},
        {"holiday_mode": "all"},
        {"holiday_mode": 1},
        {"day_shift": "tomorrow"},
        {"day_shift": 1},
        {"condition": "daily", "holiday_mode": "include"},  # 毎日には付けられない
        {"condition": "daily", "holiday_mode": "exclude"},
        {"condition": "daily", "day_shift": "before"},
        {"condition": "daily", "day_shift": "after"},
        {"scene": "out", "device": "indirect_light", "state": "on"},  # 両方
        {"scene": "out", "device": "indirect_light"},
        {"scene": "out", "state": "on"},
        {"scene": None, "device": "indirect_light"},  # 状態がない
        {"scene": None, "state": "on"},  # 機器がない
        {"scene": None, "device": "front_door", "state": "on"},  # 玄関ドアは対象外
        {"scene": None, "device": "lock", "state": "on"},
        {"scene": None, "device": "indirect_light", "state": "toggle"},
        {"scene": None, "device": "indirect_light", "state": "locked"},
        {"scene": None, "device": "indirect_light", "state": True},
        {"scene": None, "device": 1, "state": "on"},
        {"run_time": None},
        {"run_time": "7:00"},
        {"run_time": "24:00"},
        {"run_time": "12:60"},
        {"run_time": "07:00:30"},
        {"run_time": "abc"},
        {"run_time": 700},
        {"scene": None},  # 実行内容がない
        {"scene": "front_door"},  # 玄関ドアの施錠・開錠は指定できない
        {"scene": "lock"},
        {"scene": "unlock"},
        {"is_enabled": "true"},
        {"is_enabled": 1},
    ],
)
def test_不正な入力は400で登録されない(ctx: tuple[TestClient, int], override: dict[str, object]) -> None:
    client, user_id = ctx
    res = client.post("/schedules", json=_valid(**override))
    assert res.status_code == 400
    assert res.json() == {"detail": "入力が不正です"}
    assert _mine(user_id) == []


def test_本文なしの登録は400(ctx: tuple[TestClient, int]) -> None:
    client, user_id = ctx
    assert client.post("/schedules").status_code == 400
    assert _mine(user_id) == []


def test_5種の一括切替をすべて登録できる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    for scene in ("indoor_speaker", "bedside_speaker", "ceiling_light", "indirect_light", "out"):
        assert _create(client, scene=scene)["scene"] == scene


def test_従来どおりsceneだけの要求は_祝日の扱いnone_実行日の取り方sameになる(
    ctx: tuple[TestClient, int],
) -> None:
    client, _ = ctx
    res = client.post(
        "/schedules",
        json={"condition": "weekdays", "weekdays": [1], "run_time": "07:00", "scene": "out"},
    )
    assert res.status_code == 201
    assert (res.json()["holiday_mode"], res.json()["day_shift"]) == ("none", "same")


@pytest.mark.parametrize("mode", ["none", "include", "exclude"])
@pytest.mark.parametrize("shift", ["same", "before", "after"])
def test_曜日の指定は祝日の扱いと実行日の取り方の9通りを登録できる(
    ctx: tuple[TestClient, int], mode: str, shift: str
) -> None:
    client, _ = ctx
    body = _create(
        client, condition="weekdays", weekdays=[1, 2, 3, 4, 5], holiday_mode=mode, day_shift=shift
    )
    assert (body["holiday_mode"], body["day_shift"]) == (mode, shift)
    assert body["weekdays"] == [1, 2, 3, 4, 5]
    items = {s["id"]: s for s in client.get("/schedules").json()["schedules"]}
    assert (items[body["id"]]["holiday_mode"], items[body["id"]]["day_shift"]) == (mode, shift)


def test_毎日で既定値を明示しても登録できる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    body = _create(client, condition="daily", holiday_mode="none", day_shift="same")
    assert (body["holiday_mode"], body["day_shift"]) == ("none", "same")


@pytest.mark.parametrize("device", ["ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker"])
@pytest.mark.parametrize("state", ["on", "off"])
def test_機器の個別切替を4機器とON_OFFで登録できる(
    ctx: tuple[TestClient, int], device: str, state: str
) -> None:
    client, _ = ctx
    body = _create(client, scene=None, device=device, state=state)
    assert (body["scene"], body["device"], body["state"]) == (None, device, state)
    item = {s["id"]: s for s in client.get("/schedules").json()["schedules"]}[body["id"]]
    assert (item["scene"], item["device"], item["state"]) == (None, device, state)


def test_sceneを省略した個別切替の要求も登録できる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    res = client.post(
        "/schedules",
        json={"condition": "daily", "run_time": "07:00", "device": "indoor_speaker", "state": "off"},
    )
    assert res.status_code == 201
    assert res.json()["scene"] is None


def test_個別切替の登録がログに残る(ctx: tuple[TestClient, int], log_dir: Path) -> None:
    client, _ = ctx
    _create(
        client,
        scene=None,
        device="indirect_light",
        state="on",
        condition="weekdays",
        weekdays=[2],
        holiday_mode="exclude",
        day_shift="before",
    )
    log = _log_text(log_dir)
    assert "action=device device=indirect_light state=on" in log
    assert "holiday_mode=exclude day_shift=before" in log


# ---- 一覧 ----


def test_一覧は時刻の昇順_同じ時刻なら一括切替の名称順(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    a = _create(client, run_time="23:10", scene="out")["id"]
    b = _create(client, run_time="06:05", scene="out")["id"]
    c = _create(client, run_time="06:05", scene="bedside_speaker")["id"]
    d = _create(client, run_time="12:00", scene="indirect_light")["id"]

    res = client.get("/schedules")

    assert res.status_code == 200
    ids = [s["id"] for s in res.json()["schedules"]]
    mine = [i for i in ids if i in (a, b, c, d)]
    # 06:05 は scene の名称順（bedside_speaker < out）
    assert mine == [c, b, d, a]


def test_一覧は同じ時刻なら一括切替_個別切替_idの順(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    d_on = _create(client, run_time="05:55", scene=None, device="bedside_speaker", state="on")["id"]
    d_off = _create(client, run_time="05:55", scene=None, device="bedside_speaker", state="off")["id"]
    d_ind = _create(client, run_time="05:55", scene=None, device="indirect_light", state="off")["id"]
    s_out = _create(client, run_time="05:55", scene="out")["id"]
    s_bed = _create(client, run_time="05:55", scene="bedside_speaker")["id"]
    s_out2 = _create(client, run_time="05:55", scene="out")["id"]

    ids = [s["id"] for s in client.get("/schedules").json()["schedules"]]
    mine = [i for i in ids if i in (d_on, d_off, d_ind, s_out, s_bed, s_out2)]
    # 一括切替（scene 名順、同じなら id 順）→ 個別切替（機器名順 → 状態名順）
    assert mine == [s_bed, s_out, s_out2, d_off, d_on, d_ind]


def test_一覧に最終実行が含まれる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, condition="weekdays", weekdays=[1, 3, 5])["id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE room.room_schedules
            SET last_run_at = %s, last_run_result = 'partial',
                last_failed_devices = ARRAY['bedside_speaker']
            WHERE id = %s
            """,
            ("2026-10-01T07:00:02+09:00", schedule_id),
        )

    items = {s["id"]: s for s in client.get("/schedules").json()["schedules"]}

    assert items[schedule_id]["last_run"] == {
        "at": "2026-10-01T07:00:02+09:00",
        "result": "partial",
        "failed_devices": ["bedside_speaker"],
    }
    assert items[schedule_id]["weekdays"] == [1, 3, 5]


# ---- 変更 ----


def test_変更で全項目が置き換わり最終実行は変わらない(ctx: tuple[TestClient, int], log_dir: Path) -> None:
    client, user_id = ctx
    schedule_id = _create(client, condition="weekdays", weekdays=[1, 2], run_time="07:00")["id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE room.room_schedules
            SET last_run_at = now(), last_run_result = 'success' WHERE id = %s
            """,
            (schedule_id,),
        )
    before = client.get("/schedules").json()["schedules"]
    last_run_before = next(s for s in before if s["id"] == schedule_id)["last_run"]
    assert last_run_before is not None

    res = client.put(
        f"/schedules/{schedule_id}",
        json=_valid(
            condition="weekdays",
            weekdays=[6, 7],
            holiday_mode="include",
            day_shift="after",
            run_time="21:15",
            scene="out",
            is_enabled=False,
        ),
    )

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == schedule_id
    assert body["condition"] == "weekdays"
    assert body["weekdays"] == [6, 7]  # 曜日は置き換わる
    assert (body["holiday_mode"], body["day_shift"]) == ("include", "after")
    assert body["run_time"] == "21:15"
    assert body["scene"] == "out"
    assert body["is_enabled"] is False
    assert body["last_run"] == last_run_before  # 最終実行は変えない
    # 作成者は変わらない
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT created_by_user_id FROM room.room_schedules WHERE id = %s", (schedule_id,)
        )
        assert cur.fetchone()["created_by_user_id"] == user_id
    assert "定期実行の変更成功" in _log_text(log_dir)


def test_変更で曜日を設定できる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client)["id"]
    body = client.put(
        f"/schedules/{schedule_id}", json=_valid(condition="weekdays", weekdays=[7, 6])
    ).json()
    assert body["weekdays"] == [6, 7]


def test_変更で祝日の扱いと実行日の取り方を省略すると既定に戻る(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(
        client, condition="weekdays", weekdays=[1], holiday_mode="exclude", day_shift="before"
    )["id"]
    body = client.put(
        f"/schedules/{schedule_id}", json=_valid(condition="weekdays", weekdays=[1])
    ).json()
    assert (body["holiday_mode"], body["day_shift"]) == ("none", "same")


def test_変更で一括切替から個別切替へ_逆にも変えられる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, scene="out")["id"]

    to_device = client.put(
        f"/schedules/{schedule_id}", json=_valid(scene=None, device="indoor_speaker", state="off")
    ).json()
    assert (to_device["scene"], to_device["device"], to_device["state"]) == (
        None,
        "indoor_speaker",
        "off",
    )

    back = client.put(f"/schedules/{schedule_id}", json=_valid(scene="ceiling_light")).json()
    assert (back["scene"], back["device"], back["state"]) == ("ceiling_light", None, None)


def test_変更の実行内容の不整合は400で変わらない(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, scene="out")["id"]
    res = client.put(
        f"/schedules/{schedule_id}", json=_valid(scene="out", device="indirect_light", state="on")
    )
    assert res.status_code == 400
    item = next(s for s in client.get("/schedules").json()["schedules"] if s["id"] == schedule_id)
    assert (item["scene"], item["device"], item["state"]) == ("out", None, None)


def test_変更でis_enabledを省略すると現在の値を保つ(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, is_enabled=False)["id"]
    body = client.put(f"/schedules/{schedule_id}", json=_valid(run_time="08:00")).json()
    assert body["is_enabled"] is False
    assert body["run_time"] == "08:00"


def test_変更の不正な入力は400で変わらない(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, run_time="07:00")["id"]
    res = client.put(f"/schedules/{schedule_id}", json=_valid(run_time="99:99"))
    assert res.status_code == 400
    items = {s["id"]: s for s in client.get("/schedules").json()["schedules"]}
    assert items[schedule_id]["run_time"] == "07:00"


def test_存在しない定期実行の変更は404(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    res = client.put("/schedules/999999999", json=_valid())
    assert res.status_code == 404
    assert res.json() == {"detail": "対象がありません"}
    assert client.put(f"/schedules/{2**70}", json=_valid()).status_code == 404
    assert client.put("/schedules/0", json=_valid()).status_code == 404


# ---- 有効／無効 ----


def test_有効無効の切替は他の項目と最終実行を変えない(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    created = _create(client, condition="weekdays", weekdays=[2, 4], run_time="09:30", scene="out")
    schedule_id = created["id"]

    res = client.put(f"/schedules/{schedule_id}/enabled", json={"is_enabled": False})

    assert res.status_code == 200
    body = res.json()
    assert body["is_enabled"] is False
    assert {k: v for k, v in body.items() if k != "is_enabled"} == {
        k: v for k, v in created.items() if k != "is_enabled"
    }
    assert client.put(f"/schedules/{schedule_id}/enabled", json={"is_enabled": True}).json()[
        "is_enabled"
    ] is True


@pytest.mark.parametrize("body", [{}, {"is_enabled": None}, {"is_enabled": "true"}, {"is_enabled": 1}])
def test_有効無効が真偽値でなければ400(ctx: tuple[TestClient, int], body: dict[str, object]) -> None:
    client, _ = ctx
    schedule_id = _create(client)["id"]
    assert client.put(f"/schedules/{schedule_id}/enabled", json=body).status_code == 400
    assert client.put(f"/schedules/{schedule_id}/enabled").status_code == 400


def test_存在しない定期実行の有効無効は404(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    assert client.put("/schedules/999999999/enabled", json={"is_enabled": True}).status_code == 404


# ---- 削除 ----


def test_削除すると曜日と実行記録も消える(ctx: tuple[TestClient, int], log_dir: Path) -> None:
    client, _ = ctx
    schedule_id = _create(client, condition="weekdays", weekdays=[1, 2])["id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO room.schedule_runs (schedule_id, run_date) VALUES (%s, %s)",
            (schedule_id, "2026-10-01"),
        )

    res = client.delete(f"/schedules/{schedule_id}")

    assert res.status_code == 204
    assert res.content == b""
    assert schedule_id not in [s["id"] for s in client.get("/schedules").json()["schedules"]]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM room.schedule_weekdays WHERE schedule_id = %s", (schedule_id,))
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM room.schedule_runs WHERE schedule_id = %s", (schedule_id,))
        assert cur.fetchone()["n"] == 0
    assert "定期実行の削除成功" in _log_text(log_dir)


def test_存在しない定期実行の削除は404(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client)["id"]
    assert client.delete(f"/schedules/{schedule_id}").status_code == 204
    res = client.delete(f"/schedules/{schedule_id}")  # 2 回目
    assert res.status_code == 404
    assert res.json() == {"detail": "対象がありません"}


# ---- 認証 ----


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/schedules", None),
        ("post", "/schedules", _valid()),
        ("put", "/schedules/1", _valid()),
        ("put", "/schedules/1/enabled", {"is_enabled": True}),
        ("delete", "/schedules/1", None),
    ],
)
def test_未ログインは401(method: str, path: str, body: object) -> None:
    client = TestClient(room_app)
    res = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_APIキーでも管理できる(ctx: tuple[TestClient, int]) -> None:
    _, user_id = ctx
    key = "rk_" + unique("k") + "_secretsecretsecret"
    insert_api_key(user_id, key)
    headers = {"Authorization": f"Bearer {key}"}
    client = TestClient(room_app)

    created = client.post("/schedules", json=_valid(), headers=headers)
    assert created.status_code == 201
    schedule_id = created.json()["id"]
    assert client.get("/schedules", headers=headers).status_code == 200
    assert client.put(f"/schedules/{schedule_id}/enabled", json={"is_enabled": False}, headers=headers).status_code == 200
    assert client.delete(f"/schedules/{schedule_id}", headers=headers).status_code == 204


def test_最終実行の日時は秒までの日本標準時で返る(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client)["id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE room.room_schedules SET last_run_at = now(), last_run_result = 'failure', "
            "last_failed_devices = ARRAY['indirect_light','indoor_speaker'] WHERE id = %s",
            (schedule_id,),
        )
    item = next(s for s in client.get("/schedules").json()["schedules"] if s["id"] == schedule_id)
    assert ISO.match(item["last_run"]["at"])
    assert item["last_run"]["result"] == "failure"
    assert item["last_run"]["failed_devices"] == ["indirect_light", "indoor_speaker"]


# ---- 電灯の調光パターン ----


def _ceiling_on(**override: object) -> dict[str, object]:
    body = {"scene": None, "device": "ceiling_light", "state": "on"}
    body.update(override)
    return body


@pytest.mark.parametrize("pattern", ["full", "reading", "relax", "night"])
def test_電灯をONにする個別切替は_調光パターンを登録でき_応答に返る(
    ctx: tuple[TestClient, int], pattern: str
) -> None:
    client, user_id = ctx
    body = _create(client, **_ceiling_on(pattern=pattern))
    assert body["pattern"] == pattern
    assert (body["device"], body["state"], body["scene"]) == ("ceiling_light", "on", None)
    assert client.get("/schedules").json()["schedules"][0]["pattern"] == pattern
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT dimming_pattern FROM room.room_schedules WHERE id = %s", (body["id"],))
        assert cur.fetchone()["dimming_pattern"] == pattern


def test_調光パターンを省略した電灯のONは_全灯として返り_DBはNULL(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    body = _create(client, **_ceiling_on())
    assert body["pattern"] == "full"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT dimming_pattern FROM room.room_schedules WHERE id = %s", (body["id"],))
        assert cur.fetchone()["dimming_pattern"] is None


@pytest.mark.parametrize(
    "override",
    [
        _ceiling_on(pattern="dark"),  # 4 種以外
        _ceiling_on(pattern=""),
        _ceiling_on(pattern="FULL"),
        _ceiling_on(pattern=1),
        _ceiling_on(state="off", pattern="full"),  # 電灯の OFF には付けられない
        {"scene": None, "device": "indirect_light", "state": "on", "pattern": "full"},  # 電灯以外
        {"scene": None, "device": "indoor_speaker", "state": "on", "pattern": "night"},
        {"pattern": "full"},  # 一括切替
        {"scene": "ceiling_light", "pattern": "reading"},  # 電灯選択
    ],
)
def test_不正な調光パターンは400で登録されない(
    ctx: tuple[TestClient, int], override: dict[str, object], log_dir: Path
) -> None:
    client, user_id = ctx
    res = client.post("/schedules", json=_valid(**override))
    assert res.status_code == 400
    assert res.json() == {"detail": "入力が不正です"}
    assert _mine(user_id) == []
    assert "調光パターン" in _log_text(log_dir)


def test_ほかの定期実行の調光パターンはnull(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    assert _create(client)["pattern"] is None  # 一括切替
    assert _create(client, scene=None, device="ceiling_light", state="off")["pattern"] is None
    assert _create(client, scene=None, device="indirect_light", state="on")["pattern"] is None


def test_変更で調光パターンを変えられ_ONでなくすと外れる(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, **_ceiling_on(pattern="reading"))["id"]

    res = client.put(f"/schedules/{schedule_id}", json=_valid(**_ceiling_on(pattern="night")))
    assert res.status_code == 200
    assert res.json()["pattern"] == "night"

    res = client.put(f"/schedules/{schedule_id}", json=_valid(**_ceiling_on(state="off")))
    assert res.status_code == 200
    assert res.json()["pattern"] is None  # OFF には、調光パターンが無い

    # 調光パターンを指定したまま OFF にする変更は、400
    res = client.put(f"/schedules/{schedule_id}", json=_valid(**_ceiling_on(state="off", pattern="night")))
    assert res.status_code == 400


def test_調光パターンの省略で更新すると_全灯に戻る(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, **_ceiling_on(pattern="night"))["id"]
    res = client.put(f"/schedules/{schedule_id}", json=_valid(**_ceiling_on()))
    assert res.json()["pattern"] == "full"  # 省略は、現在の値を維持せず、既定になる


def test_調光パターンの登録がログに残る(ctx: tuple[TestClient, int], log_dir: Path) -> None:
    client, _ = ctx
    _create(client, **_ceiling_on(pattern="relax"))
    assert "device=ceiling_light state=on pattern=relax" in _log_text(log_dir)


def test_有効_無効の切替と最終実行は_調光パターンを変えない(ctx: tuple[TestClient, int]) -> None:
    client, _ = ctx
    schedule_id = _create(client, **_ceiling_on(pattern="relax"))["id"]
    res = client.put(f"/schedules/{schedule_id}/enabled", json={"is_enabled": False})
    assert res.status_code == 200
    assert res.json()["pattern"] == "relax"
