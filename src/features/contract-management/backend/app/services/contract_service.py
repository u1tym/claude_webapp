from __future__ import annotations

from psycopg2.extensions import connection as PgConnection

from app import repos, repos_write
from app.contract_model import STATUSES, ContractData, ContractIn, validate_contract
from app.contract_view import build_views, fetch_views
from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write


def _keyword(value: str | None) -> str | None:
    """前後の空白を除く。空・空白のみは「絞り込まない」。"""
    if value is None:
        return None
    text = value.strip()
    return text or None


def list_contracts(
    user_id: int,
    keyword: str | None,
    category_id: int | None,
    status: str | None,
    has_contract: bool | None,
    password_unset: bool | None,
) -> dict[str, object]:
    write(
        "INF",
        f"契約一覧要求 user_id={user_id} keyword={keyword!r} category_id={category_id} "
        f"status={status} has_contract={has_contract} password_unset={password_unset}",
    )
    if status is not None and status not in STATUSES:
        raise InvalidInputError(f"ステータスの絞り込みが不正 status={status!r}")
    with get_conn() as conn:
        rows = repos.list_contract_rows(
            conn, user_id, _keyword(keyword), category_id, status, has_contract, bool(password_unset)
        )
        items = build_views(conn, rows)
    write("INF", f"契約一覧成功 user_id={user_id} 件数={len(items)}")
    return {"total": len(items), "items": items}


def get_contract(user_id: int, contract_id: int) -> dict[str, object]:
    write("INF", f"契約詳細要求 user_id={user_id} id={contract_id}")
    with get_conn() as conn:
        views = fetch_views(conn, user_id, [contract_id])
    if not views:
        raise NotFoundError(f"契約が本人の削除されていないものでない id={contract_id}")
    write("INF", f"契約詳細成功 user_id={user_id} id={contract_id}")
    return views[0]


def get_password(user_id: int, contract_id: int) -> dict[str, object]:
    """パスワードの値を 1 件返す。ログには契約の ID だけを残し、値は残さない。"""
    write("INF", f"パスワード取得要求 user_id={user_id} id={contract_id}")
    with get_conn() as conn:
        found, password = repos.get_contract_password(conn, user_id, contract_id)
    if not found:
        raise NotFoundError(f"契約が本人の削除されていないものでない id={contract_id}")
    write("INF", f"パスワード取得成功 user_id={user_id} id={contract_id} 設定済み={password is not None}")
    return {"password": password}


def list_accounts(user_id: int, keyword: str | None) -> dict[str, object]:
    write("INF", f"アカウント一覧要求 user_id={user_id} keyword={keyword!r}")
    with get_conn() as conn:
        rows = repos.list_account_rows(conn, user_id, _keyword(keyword))
    items = [
        {
            "id": int(r["id"]),  # type: ignore[arg-type]
            "name": str(r["name"]),
            "username": r["username"],
            "homepage": r["homepage"],
            "has_password": bool(r["has_password"]),
            "password_unset": bool(r["password_unset"]),
        }
        for r in rows
    ]
    write("INF", f"アカウント一覧成功 user_id={user_id} 件数={len(items)}")
    return {"total": len(items), "items": items}


# ---- 登録・更新・削除 ----


def _input_log(data: ContractData) -> str:
    """ログに出す入力。パスワード・ユーザ名・登録メールアドレス・2段階認証の送付先の値は出さない。"""
    return (
        f"name={data.name!r} has_contract={data.has_contract} category_id={data.category_id} "
        f"status={data.status} depends_on_ids={list(data.depends_on_ids)} "
        f"payment_contract_id={data.payment_contract_id} password_given={data.password_given}"
    )


def _resolve_category(conn: PgConnection, user_id: int, category_id: int | None) -> int:
    """区分を決める。指定がなければ「その他」。本人の削除されていない区分でなければ入力不正。"""
    repos.ensure_default_category(conn, user_id)
    if category_id is None:
        default = next(c for c in repos.list_categories(conn, user_id) if c.is_default)
        return default.id
    category = repos.get_category(conn, user_id, category_id)
    if category is None:
        raise InvalidInputError(f"区分が本人の削除されていないものでない category_id={category_id}")
    return category.id


def _check_references(conn: PgConnection, user_id: int, data: ContractData, own_id: int | None) -> None:
    """依存契約・支払方法の対象を検査する。自分自身・他ユーザ・削除済み・金融機関でない区分は入力不正。"""
    refs = list(data.depends_on_ids)
    if data.payment_contract_id is not None:
        refs.append(data.payment_contract_id)
    if own_id is not None and own_id in refs:
        raise InvalidInputError(f"自分自身は選べない id={own_id}")
    found = repos_write.find_own_contracts(conn, user_id, refs)
    for dep in data.depends_on_ids:
        if dep not in found:
            raise InvalidInputError(f"依存契約が本人の削除されていない契約でない id={dep}")
    if data.payment_contract_id is not None:
        pay = data.payment_contract_id
        if pay not in found:
            raise InvalidInputError(f"支払方法が本人の削除されていない契約でない id={pay}")
        if not found[pay]:
            raise InvalidInputError(f"支払方法が金融機関の区分の契約でない id={pay}")


def create_contract(user_id: int, body: ContractIn, via_api_key: bool) -> dict[str, object]:
    write("INF", f"契約登録要求 user_id={user_id} via_api_key={via_api_key}")
    data = validate_contract(body, allow_password=not via_api_key)
    write("INF", f"契約登録入力 user_id={user_id} {_input_log(data)}")
    with get_conn() as conn:
        repos_write.lock_user_contracts(conn, user_id)
        category_id = _resolve_category(conn, user_id, data.category_id)
        _check_references(conn, user_id, data, own_id=None)
        contract_id = repos_write.insert_contract(conn, user_id, category_id, data)
        repos_write.replace_dependencies(conn, contract_id, data.depends_on_ids)
        view = fetch_views(conn, user_id, [contract_id])[0]
    write("INF", f"契約登録成功 user_id={user_id} id={contract_id}")
    return view


def update_contract(user_id: int, contract_id: int, body: ContractIn, via_api_key: bool) -> dict[str, object]:
    write("INF", f"契約更新要求 user_id={user_id} id={contract_id} via_api_key={via_api_key}")
    data = validate_contract(body, allow_password=not via_api_key)
    write("INF", f"契約更新入力 user_id={user_id} id={contract_id} {_input_log(data)}")
    with get_conn() as conn:
        repos_write.lock_user_contracts(conn, user_id)
        current = repos_write.get_current(conn, user_id, contract_id)
        if current is None:
            raise NotFoundError(f"契約が本人の削除されていないものでない id={contract_id}")
        category_id = _resolve_category(conn, user_id, data.category_id)
        _check_references(conn, user_id, data, own_id=contract_id)

        # 金融機関の区分から、金融機関でない区分へ変えるとき、他の契約の支払方法になっていてはいけない
        if current.category_is_financial and category_id != current.category_id:
            new_category = repos.get_category(conn, user_id, category_id)
            if new_category is not None and not new_category.is_financial and repos_write.is_payment_target(
                conn, contract_id
            ):
                raise ConflictError(f"支払方法として使われているため金融機関でない区分へ変えられない id={contract_id}")

        if repos_write.dependency_reaches(conn, list(data.depends_on_ids), contract_id, skip_source_id=contract_id):
            raise ConflictError(f"依存の関係が循環する id={contract_id}")

        repos_write.update_contract(conn, contract_id, category_id, data)
        repos_write.replace_dependencies(conn, contract_id, data.depends_on_ids)
        # 契約を伴わない、またはステータスが解約になった契約は、解約順の対象でなくなる
        if not data.has_contract or data.status == "cancelled":
            if repos_write.remove_from_plan(conn, user_id, contract_id):
                write("INF", f"解約順から外した user_id={user_id} id={contract_id}")
        view = fetch_views(conn, user_id, [contract_id])[0]
    write("INF", f"契約更新成功 user_id={user_id} id={contract_id}")
    return view


def delete_contract(user_id: int, contract_id: int) -> None:
    write("INF", f"契約削除要求 user_id={user_id} id={contract_id}")
    with get_conn() as conn:
        repos_write.lock_user_contracts(conn, user_id)
        current = repos_write.get_current(conn, user_id, contract_id)
        if current is None:
            raise NotFoundError(f"契約が本人の削除されていないものでない id={contract_id}")
        repos_write.soft_delete_contract(conn, contract_id)
        if repos_write.remove_from_plan(conn, user_id, contract_id):
            write("INF", f"解約順から外した user_id={user_id} id={contract_id}")
    write("INF", f"契約削除成功 user_id={user_id} id={contract_id}")
