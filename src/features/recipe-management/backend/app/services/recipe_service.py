from __future__ import annotations

from typing import Any

from psycopg2 import errors
from psycopg2.extensions import cursor as PgCursor

from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import ingredient as ingredient_repo
from app.repos import measurement as measurement_repo
from app.repos import recipe as recipe_repo

DUPLICATE = "同じメニュー名のレシピがあります"

Step = tuple[str, list[tuple[int, int, str]]]  # (説明, [(材料, 分量名称, 数量)])


def _prepare_steps(cur: PgCursor, user_id: int, steps: list[dict[str, Any]]) -> list[Step]:
    """材料・分量名称の利用可否と、数量の規則を確認し、保存する形にそろえる。"""
    ingredient_ids = sorted({item["ingredient_id"] for step in steps for item in step["items"]})
    measurement_ids = sorted({item["measurement_id"] for step in steps for item in step["items"]})
    if ingredient_repo.count_accessible(cur, user_id, ingredient_ids) != len(ingredient_ids):
        raise NotFoundError(reason=f"材料なし user_id={user_id} ingredient_ids={ingredient_ids}")
    ness = measurement_repo.ness_amount_by_id(cur, user_id, measurement_ids)
    if len(ness) != len(measurement_ids):
        raise NotFoundError(reason=f"分量名称なし user_id={user_id} measurement_ids={measurement_ids}")
    prepared: list[Step] = []
    for step_index, step in enumerate(steps, start=1):
        rows: list[tuple[int, int, str]] = []
        for item_index, item in enumerate(step["items"], start=1):
            amount = item["amount"]
            if ness[item["measurement_id"]]:
                if not amount:
                    raise InvalidInputError(reason=f"数量が空 手順{step_index} 材料{item_index}")
            else:
                amount = ""  # 数量なしの分量名称は、数量を保存しない
            rows.append((item["ingredient_id"], item["measurement_id"], amount))
        prepared.append((step["description"], rows))
    return prepared


def _write_steps(cur: PgCursor, recipe_id: int, prepared: list[Step]) -> None:
    for step_no, (description, rows) in enumerate(prepared, start=1):
        step_id = recipe_repo.insert_step(cur, recipe_id, step_no, description)
        recipe_repo.insert_items(cur, step_id, rows)


def _detail(cur: PgCursor, recipe: dict[str, Any]) -> dict[str, Any]:
    return {**recipe, "steps": recipe_repo.fetch_steps(cur, recipe["id"])}


def _summary(body: dict[str, Any]) -> str:
    """ログ用の要約。工程の説明の本文は出さない。"""
    rows = sum(len(step["items"]) for step in body["steps"])
    return f"name={body['name']} kana={body['kana']} 工程数={len(body['steps'])} 材料の行={rows}"


def list_recipes(user_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        items = recipe_repo.list_recipes(cur, user_id)
    write("INF", f"レシピ一覧 user_id={user_id} 件数={len(items)}")
    return {"items": items}


def get_recipe(user_id: int, recipe_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        recipe = recipe_repo.get_recipe(cur, user_id, recipe_id)
        if recipe is None:
            raise NotFoundError(reason=f"レシピなし user_id={user_id} recipe_id={recipe_id}")
        detail = _detail(cur, recipe)
    write("INF", f"レシピ詳細 user_id={user_id} recipe_id={recipe_id}")
    return detail


def create_recipe(user_id: int, body: dict[str, Any]) -> dict[str, Any]:
    write("INF", f"レシピ登録要求 user_id={user_id} {_summary(body)}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            prepared = _prepare_steps(cur, user_id, body["steps"])
            recipe_id = recipe_repo.insert_recipe(cur, user_id, body["name"], body["kana"])
            _write_steps(cur, recipe_id, prepared)
            recipe = recipe_repo.get_recipe(cur, user_id, recipe_id)
            assert recipe is not None
            detail = _detail(cur, recipe)
    except errors.UniqueViolation:
        raise ConflictError(DUPLICATE, reason=f"メニュー名重複 name={body['name']}") from None
    write("INF", f"レシピ登録成功 user_id={user_id} recipe_id={detail['id']}")
    return detail


def update_recipe(user_id: int, recipe_id: int, body: dict[str, Any]) -> dict[str, Any]:
    write("INF", f"レシピ更新要求 user_id={user_id} recipe_id={recipe_id} {_summary(body)}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if recipe_repo.get_recipe(cur, user_id, recipe_id, lock=True) is None:
                raise NotFoundError(reason=f"レシピなし user_id={user_id} recipe_id={recipe_id}")
            prepared = _prepare_steps(cur, user_id, body["steps"])
            recipe_repo.update_recipe(cur, recipe_id, body["name"], body["kana"])
            recipe_repo.delete_steps(cur, recipe_id)
            _write_steps(cur, recipe_id, prepared)
            recipe = recipe_repo.get_recipe(cur, user_id, recipe_id)
            assert recipe is not None
            detail = _detail(cur, recipe)
    except errors.UniqueViolation:
        raise ConflictError(DUPLICATE, reason=f"メニュー名重複 name={body['name']}") from None
    write("INF", f"レシピ更新成功 user_id={user_id} recipe_id={recipe_id}")
    return detail


def delete_recipe(user_id: int, recipe_id: int) -> None:
    write("INF", f"レシピ削除要求 user_id={user_id} recipe_id={recipe_id}")
    with get_conn() as conn, conn.cursor() as cur:
        if not recipe_repo.soft_delete(cur, user_id, recipe_id):
            raise NotFoundError(reason=f"レシピなし user_id={user_id} recipe_id={recipe_id}")
    write("INF", f"レシピ削除成功 user_id={user_id} recipe_id={recipe_id}")
