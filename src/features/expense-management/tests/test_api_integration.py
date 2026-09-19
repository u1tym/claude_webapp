from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.db import get_conn  # noqa: E402


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


@pytest.fixture(scope="module")
def allowed_username() -> str:
    return f"integration_test_{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
def unassigned_username() -> str:
    return f"integration_test_noaccess_{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
def allowed_user_id(allowed_username: str) -> int:
    user_id = _ensure_user(allowed_username)
    _ensure_feature_assignment(user_id, "expense-management")
    return user_id


@pytest.fixture(scope="module")
def unassigned_user_id(unassigned_username: str) -> int:
    return _ensure_user(unassigned_username)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, allowed_username: str, allowed_user_id: int):
    from app.main import app

    cfg = load_config()
    patched_allowed = cfg.__class__(
        db_server=cfg.db_server,
        db_name=cfg.db_name,
        db_port=cfg.db_port,
        db_username=cfg.db_username,
        db_password=cfg.db_password,
        cors_origins=cfg.cors_origins,
        session_timeout_minutes=cfg.session_timeout_minutes,
        debug_user=allowed_username,
        log_max_bytes=cfg.log_max_bytes,
        log_backup_count=cfg.log_backup_count,
    )
    monkeypatch.setattr("app.deps.load_config", lambda: patched_allowed)

    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture()
def unauthenticated_client(monkeypatch: pytest.MonkeyPatch):
    from app.main import app

    cfg = load_config()
    patched = cfg.__class__(
        db_server=cfg.db_server,
        db_name=cfg.db_name,
        db_port=cfg.db_port,
        db_username=cfg.db_username,
        db_password=cfg.db_password,
        cors_origins=cfg.cors_origins,
        session_timeout_minutes=cfg.session_timeout_minutes,
        debug_user=None,
        log_max_bytes=cfg.log_max_bytes,
        log_backup_count=cfg.log_backup_count,
    )
    monkeypatch.setattr("app.deps.load_config", lambda: patched)

    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture()
def unassigned_client(monkeypatch: pytest.MonkeyPatch, unassigned_username: str, unassigned_user_id: int):
    from app.main import app

    cfg = load_config()
    patched = cfg.__class__(
        db_server=cfg.db_server,
        db_name=cfg.db_name,
        db_port=cfg.db_port,
        db_username=cfg.db_username,
        db_password=cfg.db_password,
        cors_origins=cfg.cors_origins,
        session_timeout_minutes=cfg.session_timeout_minutes,
        debug_user=unassigned_username,
        log_max_bytes=cfg.log_max_bytes,
        log_backup_count=cfg.log_backup_count,
    )
    monkeypatch.setattr("app.deps.load_config", lambda: patched)

    from fastapi.testclient import TestClient

    return TestClient(app)


def test_unauthenticated_request_is_rejected(unauthenticated_client) -> None:
    r = unauthenticated_client.get("/budget-periods")
    assert r.status_code == 401


def test_unassigned_user_is_forbidden(unassigned_client) -> None:
    r = unassigned_client.get("/budget-periods")
    assert r.status_code == 403


def test_budget_period_and_item_flow(client) -> None:
    r = client.post(
        "/budget-periods",
        json={"title": "2030年1月分", "start_date": "2030-01-01", "end_date": "2030-01-31"},
    )
    assert r.status_code == 201
    period = r.json()
    assert period["title"] == "2030年1月分"

    # Overlapping periods are now allowed.
    r = client.post(
        "/budget-periods",
        json={"title": "2030年1月分(重複)", "start_date": "2030-01-15", "end_date": "2030-02-15"},
    )
    assert r.status_code == 201

    r = client.post(
        "/budget-periods",
        json={"title": "", "start_date": "2030-01-01", "end_date": "2030-01-31"},
    )
    assert r.status_code == 400

    r = client.patch(
        f"/budget-periods/{period['id']}",
        json={"title": "2030年1月分(改題)", "start_date": "2030-01-05", "end_date": "2030-01-25"},
    )
    assert r.status_code == 200
    updated_period = r.json()
    assert updated_period["title"] == "2030年1月分(改題)"
    assert updated_period["start_date"] == "2030-01-05"
    assert updated_period["end_date"] == "2030-01-25"

    r = client.patch(
        f"/budget-periods/{period['id']}",
        json={"title": "", "start_date": "2030-01-05", "end_date": "2030-01-25"},
    )
    assert r.status_code == 400

    r = client.patch(
        f"/budget-periods/{period['id']}",
        json={"title": "無効な期間", "start_date": "2030-01-25", "end_date": "2030-01-05"},
    )
    assert r.status_code == 400

    r = client.patch(
        "/budget-periods/0",
        json={"title": "存在しない", "start_date": "2030-01-01", "end_date": "2030-01-31"},
    )
    assert r.status_code == 404

    period = updated_period

    r = client.post(
        "/budget-items",
        json={"budget_period_id": period["id"], "name": "食費", "amount": "20000.00", "display_order": 1},
    )
    assert r.status_code == 201
    item = r.json()

    r = client.get("/budget-items", params={"budget_period_id": period["id"]})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1

    r = client.post(
        f"/budget-periods/{period['id']}/duplicate",
        json={"title": "2030年2月分", "start_date": "2030-02-01", "end_date": "2030-02-28"},
    )
    assert r.status_code == 201
    duplicated = r.json()
    assert duplicated["title"] == "2030年2月分"
    assert len(duplicated["budget_items"]) == 1
    assert duplicated["budget_items"][0]["name"] == "食費"

    r = client.delete(f"/budget-items/{item['id']}")
    assert r.status_code == 204
    r = client.get("/budget-items", params={"budget_period_id": period["id"]})
    assert r.json()["items"] == []

    r = client.delete(f"/budget-items/{item['id']}")
    assert r.status_code == 404


def test_payment_method_and_expense_and_report_flow(client) -> None:
    r = client.post(
        "/payment-methods",
        json={
            "name": "テストカード",
            "closing_day": 20,
            "closing_day_shift_direction": "earlier",
            "payment_month_offset": 1,
            "payment_day": 27,
            "payment_day_shift_direction": "later",
            "display_order": 1,
        },
    )
    assert r.status_code == 201
    method = r.json()

    r = client.post(
        "/budget-periods",
        json={"title": "2031年1月分", "start_date": "2031-01-01", "end_date": "2031-01-31"},
    )
    assert r.status_code == 201
    period = r.json()

    r = client.post(
        "/budget-items",
        json={"budget_period_id": period["id"], "name": "娯楽費", "amount": "10000.00", "display_order": 1},
    )
    item = r.json()

    r = client.get(
        f"/payment-methods/{method['id']}/estimated-payment-date", params={"usage_date": "2031-01-05"}
    )
    assert r.status_code == 200
    estimated = r.json()["payment_date"]

    r = client.post(
        "/expenses",
        json={
            "usage_date": "2031-01-05",
            "budget_period_id": period["id"],
            "budget_item_id": item["id"],
            "purpose": "映画",
            "amount": "1800.00",
            "payment_method_id": method["id"],
            "payment_date": estimated,
        },
    )
    assert r.status_code == 201
    expense = r.json()
    assert expense["budget_period_id"] == period["id"]

    # budget_item_id without budget_period_id is rejected
    r = client.post(
        "/expenses",
        json={
            "usage_date": "2031-01-05",
            "budget_item_id": item["id"],
            "purpose": "不正",
            "amount": "100.00",
            "payment_method_id": method["id"],
            "payment_date": estimated,
        },
    )
    assert r.status_code == 400

    # a budget item from another period is rejected
    r = client.post(
        "/budget-periods",
        json={"title": "別期間", "start_date": "2031-02-01", "end_date": "2031-02-28"},
    )
    other_period = r.json()
    r = client.post(
        "/expenses",
        json={
            "usage_date": "2031-01-05",
            "budget_period_id": other_period["id"],
            "budget_item_id": item["id"],
            "purpose": "不正",
            "amount": "100.00",
            "payment_method_id": method["id"],
            "payment_date": estimated,
        },
    )
    assert r.status_code == 400

    # "no budget" is allowed
    r = client.post(
        "/expenses",
        json={
            "usage_date": "2031-01-06",
            "purpose": "予算なし",
            "amount": "500.00",
            "payment_method_id": method["id"],
            "payment_date": estimated,
        },
    )
    assert r.status_code == 201
    unassigned_expense = r.json()
    assert unassigned_expense["budget_period_id"] is None
    assert unassigned_expense["budget_item_id"] is None

    r = client.get("/expenses", params={"budget_period_id": period["id"]})
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == [expense["id"]]

    r = client.get("/expenses", params={"unassigned": "true"})
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == [unassigned_expense["id"]]

    r = client.get("/reports/usage-date", params={"budget_period_id": period["id"]})
    assert r.status_code == 200
    report_items = r.json()["items"]
    matching = next(i for i in report_items if i["budget_item_id"] == item["id"])
    assert matching["actual_amount"] == "1800.00"
    assert matching["difference"] == "8200.00"

    year_month = estimated[:7]
    r = client.get("/reports/payment-month", params={"year_month": year_month})
    assert r.status_code == 200
    assert any(i["budget_item_id"] == item["id"] and i["actual_amount"] == "1800.00" for i in r.json()["items"])

    r = client.delete(f"/expenses/{expense['id']}")
    assert r.status_code == 204
    r = client.delete(f"/expenses/{unassigned_expense['id']}")
    assert r.status_code == 204
    r = client.get("/expenses", params={"start_date": "2031-01-01", "end_date": "2031-01-31"})
    assert r.json()["items"] == []


def test_payment_method_exclusion_holiday(client) -> None:
    r = client.post(
        "/payment-methods",
        json={
            "name": "祝日除外カード",
            "closing_day": 10,
            "closing_day_shift_direction": "later",
            "closing_day_exclusions": [{"exclusion_kind": "holiday"}],
            "payment_month_offset": 1,
            "payment_day": 20,
            "payment_day_shift_direction": "earlier",
            "payment_day_exclusions": [{"exclusion_kind": "holiday"}, {"exclusion_kind": "sunday"}],
            "display_order": 1,
        },
    )
    assert r.status_code == 201
    method = r.json()
    assert {"exclusion_kind": "holiday"} in method["closing_day_exclusions"]
    assert {"exclusion_kind": "holiday"} in method["payment_day_exclusions"]

    r = client.patch(
        f"/payment-methods/{method['id']}",
        json={
            "name": "祝日除外カード",
            "closing_day": 10,
            "closing_day_shift_direction": "later",
            "closing_day_exclusions": [],
            "payment_month_offset": 1,
            "payment_day": 20,
            "payment_day_shift_direction": "earlier",
            "payment_day_exclusions": [{"exclusion_kind": "holiday"}],
            "display_order": 1,
        },
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["closing_day_exclusions"] == []
    assert updated["payment_day_exclusions"] == [{"exclusion_kind": "holiday"}]

    invalid = client.post(
        "/payment-methods",
        json={
            "name": "不正な条件",
            "closing_day": 10,
            "closing_day_shift_direction": "later",
            "closing_day_exclusions": [{"exclusion_kind": "holidays"}],
            "payment_month_offset": 0,
            "payment_day": 10,
            "payment_day_shift_direction": "later",
            "display_order": 1,
        },
    )
    assert invalid.status_code == 400
