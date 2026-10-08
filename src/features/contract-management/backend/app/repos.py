from __future__ import annotations

from dataclasses import dataclass

from psycopg2.extensions import connection as PgConnection

DEFAULT_CATEGORY_NAME = "その他"


# ---- categories ----


@dataclass(frozen=True)
class CategoryRow:
    id: int
    user_id: int
    name: str
    is_default: bool
    is_financial: bool
    is_deleted: bool


def _category(row: dict[str, object]) -> CategoryRow:
    return CategoryRow(
        id=int(row["id"]),  # type: ignore[arg-type]
        user_id=int(row["user_id"]),  # type: ignore[arg-type]
        name=str(row["name"]),
        is_default=bool(row["is_default"]),
        is_financial=bool(row["is_financial"]),
        is_deleted=bool(row["is_deleted"]),
    )


_CATEGORY_COLUMNS = "id, user_id, name, is_default, is_financial, is_deleted"


def ensure_default_category(conn: PgConnection, user_id: int) -> None:
    """利用者の「その他」がなければ作る。同時に作られても、1 つだけになる（部分一意）。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO contract_management.categories (user_id, name, is_default)
            VALUES (%s, %s, true)
            ON CONFLICT DO NOTHING
            """,
            (user_id, DEFAULT_CATEGORY_NAME),
        )


def list_categories(conn: PgConnection, user_id: int) -> list[CategoryRow]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CATEGORY_COLUMNS}
            FROM contract_management.categories
            WHERE user_id = %s AND is_deleted = false
            ORDER BY is_default DESC, id
            """,
            (user_id,),
        )
        return [_category(r) for r in cur.fetchall()]


def get_category(
    conn: PgConnection, user_id: int, category_id: int, for_update: bool = False
) -> CategoryRow | None:
    """本人の削除されていない区分を返す。他人・削除済み・存在しないときは None。"""
    lock = " FOR UPDATE" if for_update else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CATEGORY_COLUMNS}
            FROM contract_management.categories
            WHERE id = %s AND user_id = %s AND is_deleted = false{lock}
            """,
            (category_id, user_id),
        )
        row = cur.fetchone()
        return None if row is None else _category(row)


def category_name_exists(
    conn: PgConnection, user_id: int, name: str, exclude_id: int | None = None
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM contract_management.categories
            WHERE user_id = %s AND name = %s AND is_deleted = false
              AND (%s::integer IS NULL OR id <> %s::integer)
            """,
            (user_id, name, exclude_id, exclude_id),
        )
        return cur.fetchone() is not None


def insert_category(conn: PgConnection, user_id: int, name: str, is_financial: bool) -> CategoryRow:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO contract_management.categories (user_id, name, is_financial)
            VALUES (%s, %s, %s)
            RETURNING {_CATEGORY_COLUMNS}
            """,
            (user_id, name, is_financial),
        )
        return _category(cur.fetchone())


def update_category(
    conn: PgConnection, category_id: int, name: str, is_financial: bool
) -> CategoryRow:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE contract_management.categories
            SET name = %s, is_financial = %s
            WHERE id = %s
            RETURNING {_CATEGORY_COLUMNS}
            """,
            (name, is_financial, category_id),
        )
        return _category(cur.fetchone())


def soft_delete_category(conn: PgConnection, category_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE contract_management.categories SET is_deleted = true WHERE id = %s",
            (category_id,),
        )


def category_in_use(conn: PgConnection, category_id: int) -> bool:
    """その区分を使っている、削除されていない契約があるか。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM contract_management.contracts
            WHERE category_id = %s AND is_deleted = false
            LIMIT 1
            """,
            (category_id,),
        )
        return cur.fetchone() is not None


def category_used_as_payment(conn: PgConnection, category_id: int) -> bool:
    """その区分の契約を、支払方法にしている契約（削除されていないもの）があるか。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM contract_management.contracts pay
            JOIN contract_management.contracts ref ON ref.payment_contract_id = pay.id
            WHERE pay.category_id = %s AND pay.is_deleted = false AND ref.is_deleted = false
            LIMIT 1
            """,
            (category_id,),
        )
        return cur.fetchone() is not None


# ---- contracts（参照） ----


def _like(keyword: str) -> str:
    """部分一致の検索語。LIKE の特殊文字（% _ バックスラッシュ）は、文字そのものとして扱う。"""
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_contract_rows(
    conn: PgConnection,
    user_id: int,
    keyword: str | None,
    category_id: int | None,
    status: str | None,
    has_contract: bool | None,
    password_unset: bool,
) -> list[dict[str, object]]:
    """本人の削除されていない契約を、名称の昇順（同名は ID 昇順）で返す。条件はすべて満たすものだけ。

    返す列は contract_view.CONTRACT_COLUMNS（パスワードの値は含まない）。
    """
    from app.contract_view import CONTRACT_COLUMNS

    where = ["user_id = %s", "is_deleted = false"]
    params: list[object] = [user_id]
    if keyword is not None:
        pattern = _like(keyword)
        where.append(
            "(name ILIKE %s OR homepage ILIKE %s OR registered_email ILIKE %s "
            "OR username ILIKE %s OR memo ILIKE %s)"
        )
        params.extend([pattern] * 5)
    if category_id is not None:
        where.append("category_id = %s")
        params.append(category_id)
    if status is not None:
        where.append("status = %s")
        params.append(status)
    if has_contract is not None:
        where.append("has_contract = %s")
        params.append(has_contract)
    if password_unset:
        where.append("login_password = true AND password IS NULL")
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {CONTRACT_COLUMNS} FROM contract_management.contracts "
            f"WHERE {' AND '.join(where)} ORDER BY name, id",
            tuple(params),
        )
        return [dict(r) for r in cur.fetchall()]


def get_contract_password(conn: PgConnection, user_id: int, contract_id: int) -> tuple[bool, str | None]:
    """(本人の削除されていない契約か, パスワードの値)。契約が無ければ (False, None)。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT password
            FROM contract_management.contracts
            WHERE id = %s AND user_id = %s AND is_deleted = false
            """,
            (contract_id, user_id),
        )
        row = cur.fetchone()
        if row is None:
            return False, None
        return True, row["password"]


def list_account_rows(conn: PgConnection, user_id: int, keyword: str | None) -> list[dict[str, object]]:
    """ユーザ名またはパスワードを持つ、本人の削除されていない契約を、名称の昇順（同名は ID 昇順）で返す。パスワードの値は含まない。"""
    where = [
        "user_id = %s",
        "is_deleted = false",
        "(username IS NOT NULL OR password IS NOT NULL)",
    ]
    params: list[object] = [user_id]
    if keyword is not None:
        pattern = _like(keyword)
        where.append("(name ILIKE %s OR username ILIKE %s OR homepage ILIKE %s OR memo ILIKE %s)")
        params.extend([pattern] * 4)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, username, homepage,
                   (password IS NOT NULL) AS has_password,
                   (login_password AND password IS NULL) AS password_unset
            FROM contract_management.contracts
            WHERE {' AND '.join(where)}
            ORDER BY name, id
            """,
            tuple(params),
        )
        return [dict(r) for r in cur.fetchall()]
