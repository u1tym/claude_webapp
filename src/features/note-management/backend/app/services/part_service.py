"""パーツの業務ロジック（design.md「パーツ」）。ファイルの取得（パーツ付き）もここに置く。"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from app.action_plan import normalize_action_plan
from app.config import load_config
from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError, PayloadTooLargeError
from app.image_markers import validate_markers, validate_scale
from app.logger import write
from app.repos import folder as folder_repo
from app.repos import part as repo
from app.services.file_service import file_effective_deleted, require_file
from app.services.folder_service import DELETED_MESSAGE

TEXT_TYPES = ("text", "md", "tex", "url")
IMAGE_TYPES = ("jpeg", "png")
BINARY_TYPES = repo.BINARY_TYPES
ALL_TYPES = TEXT_TYPES + ("action", "checklist") + BINARY_TYPES

CONTENT_MESSAGE = "ファイルの内容が正しくありません"
FILENAME_MESSAGE = "ファイル名を入力してください"
FORMAT_MESSAGE = "画像の形式が正しくありません"
CHECKLIST_MESSAGE = "チェックリストの種別は変更できません"

_SIGNATURES = {
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
}


def _group(ptype: str) -> str:
    if ptype in TEXT_TYPES:
        return "text"
    if ptype in BINARY_TYPES:
        return "binary"
    return ptype  # action / checklist


# ---- 入力の検証 -------------------------------------------------------------


def _check_type(ptype: Any) -> str:
    if not isinstance(ptype, str) or ptype not in ALL_TYPES:
        raise InvalidInputError(reason=f"種別が不正 type={ptype!r}")
    return ptype


def _too_large_message(limit: int) -> str:
    megabytes = limit / 1048576
    if megabytes >= 1:
        return f"ファイルは {megabytes:g} MB までです"
    return f"ファイルは {limit / 1024:g} KB までです"


def _decode_binary(data: Any, ptype: str) -> int:
    """Base64 の中身を検証し、展開後の大きさを返す。"""
    if not isinstance(data, str) or data == "":
        raise InvalidInputError(CONTENT_MESSAGE, reason="中身が空・文字列でない")
    limit = load_config().part_max_bytes
    if len(data) * 3 // 4 > limit + 3:
        raise PayloadTooLargeError(_too_large_message(limit), reason=f"大きさ超過（概算） base64={len(data)}")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidInputError(CONTENT_MESSAGE, reason="Base64 として読めない") from exc
    if len(raw) > limit:
        raise PayloadTooLargeError(_too_large_message(limit), reason=f"大きさ超過 bytes={len(raw)}")
    if len(raw) == 0:
        raise InvalidInputError(CONTENT_MESSAGE, reason="中身が空")
    _check_signature(raw[:16], ptype)
    return len(raw)


def _check_signature(head: bytes, ptype: str) -> None:
    signature = _SIGNATURES.get(ptype)
    if signature is not None and not head.startswith(signature):
        raise InvalidInputError(FORMAT_MESSAGE, reason=f"形式の不一致 type={ptype}")


def _signature_of_prefix(prefix: str, ptype: str) -> None:
    """保存済みの中身の先頭（Base64）から、形式を確認する。"""
    prefix = prefix[: len(prefix) - len(prefix) % 4]
    try:
        head = base64.b64decode(prefix)
    except (binascii.Error, ValueError):
        head = b""
    _check_signature(head, ptype)


def _clean_filename(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise InvalidInputError(FILENAME_MESSAGE, reason="ファイル名が空")
    return value.strip()


def _text_value(value: Any, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidInputError(reason=f"{name} が文字列でない")
    return value


# ---- 応答の組み立て ---------------------------------------------------------


def _iso(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _part_out(row: dict[str, Any], revisions: list[dict[str, Any]], checklist_id: int | None) -> dict[str, Any]:
    ptype = row["ptype"]
    is_image = ptype in IMAGE_TYPES
    return {
        "id": row["id"],
        "sort_order": row["sort_order"],
        "type": ptype,
        "is_deleted": row["is_deleted"],
        "data": row["data"],
        "byte_size": row["byte_size"],
        "filename": row["filename"],
        "title": row["title"] if is_image else "",
        "markers": row["markers"] if is_image else [],
        "image_scale": float(row["image_scale"]) if is_image else 1.0,
        "checklist_id": checklist_id if ptype == "checklist" else None,
        "revisions": [
            {
                "id": r["id"],
                "revision_number": r["revision_number"],
                "type": r["ptype"],
                "filename": r["filename"],
                "byte_size": r["byte_size"],
                "created_at": _iso(r["created_at"]),
            }
            for r in revisions
        ]
        if ptype in BINARY_TYPES
        else [],
    }


def _load_out(cur, user_id: int, part_id: int) -> dict[str, Any]:
    row = repo.get_part(cur, user_id, part_id)
    assert row is not None
    revisions = repo.list_revisions(cur, [part_id]).get(part_id, [])
    return _part_out(row, revisions, repo.checklist_ids(cur, [part_id]).get(part_id))


def get_file_detail(user_id: int, file_id: int, include_deleted_parts: bool) -> dict[str, Any]:
    write("INF", f"ファイル取得要求 user_id={user_id} file_id={file_id} include_deleted_parts={include_deleted_parts}")
    with get_conn() as conn, conn.cursor() as cur:
        file_row = require_file(cur, user_id, file_id)
        folder = folder_repo.get_folder(cur, user_id, file_row["folder_id"])
        assert folder is not None
        ancestor_deleted = folder_repo.chain_deleted(cur, file_row["folder_id"])
        rows = repo.list_parts(cur, user_id, file_id, include_deleted_parts)
        ids = [r["id"] for r in rows]
        revisions = repo.list_revisions(cur, ids)
        checklists = repo.checklist_ids(cur, ids)
        parts = [_part_out(r, revisions.get(r["id"], []), checklists.get(r["id"])) for r in rows]
    write("INF", f"ファイル取得成功 user_id={user_id} file_id={file_id} パーツ={len(parts)}")
    return {
        "id": file_row["id"],
        "folder": {"id": folder["id"], "name": folder["name"]},
        "title": file_row["title"],
        "is_deleted": file_row["is_deleted"],
        "ancestor_deleted": ancestor_deleted,
        "parts": parts,
    }


# ---- 追加 -------------------------------------------------------------------


def create_part(user_id: int, file_id: int, body: dict[str, Any]) -> dict[str, Any]:
    ptype = _check_type(body.get("type"))
    data = body.get("data")
    write("INF", f"パーツ追加要求 user_id={user_id} file_id={file_id} type={ptype} data長={len(data) if isinstance(data, str) else 0}")

    filename = ""
    title = ""
    markers: list[dict[str, Any]] = []
    scale = 1.0
    byte_size = 0
    if ptype in TEXT_TYPES:
        data = _text_value(data, "data")
    elif ptype == "action":
        data = normalize_action_plan(data if isinstance(data, str) else "")
    elif ptype == "checklist":
        data = ""
    else:
        filename = _clean_filename(body.get("filename"))
        byte_size = _decode_binary(data, ptype)
        if ptype in IMAGE_TYPES:
            title = _text_value(body.get("title"), "title")
            markers = validate_markers(body["markers"]) if body.get("markers") is not None else []
            scale = validate_scale(body["image_scale"]) if body.get("image_scale") is not None else 1.0

    with get_conn() as conn, conn.cursor() as cur:
        file_row = require_file(cur, user_id, file_id)
        if file_effective_deleted(cur, file_row):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済みのファイル file_id={file_id}")
        repo.lock_parts(cur, file_id)
        part_id = repo.insert_part(
            cur, user_id, file_id, repo.next_sort_order(cur, user_id, file_id),
            ptype=ptype, data=data, byte_size=byte_size, filename=filename, title=title,
            markers=markers, image_scale=scale,
        )
        if ptype == "checklist":
            repo.insert_checklist(cur, user_id, part_id)
        out = _load_out(cur, user_id, part_id)
    write("INF", f"パーツ追加成功 user_id={user_id} file_id={file_id} part_id={part_id} type={ptype} byte_size={byte_size}")
    return out


# ---- 更新 -------------------------------------------------------------------


def _require_part(cur, user_id: int, part_id: int) -> dict[str, Any]:
    row = repo.get_part(cur, user_id, part_id)
    if row is None:
        raise NotFoundError(reason=f"パーツなし user_id={user_id} part_id={part_id}")
    return row


def _require_editable(cur, user_id: int, part: dict[str, Any]) -> dict[str, Any]:
    """所属ファイルが削除済み（上位を含む）でないことを確認する。ファイルの行を返す。"""
    file_row = require_file(cur, user_id, part["file_id"])
    if file_effective_deleted(cur, file_row):
        raise ConflictError(DELETED_MESSAGE, reason=f"削除済みのファイル part_id={part['id']}")
    return file_row


def update_part(user_id: int, part_id: int, body: dict[str, Any], provided: set[str]) -> dict[str, Any]:
    """provided は、要求で指定された項目の名前（省略した項目は現在の値を保つ）。"""
    cfg = load_config()
    write("INF", f"パーツ更新要求 user_id={user_id} part_id={part_id} 項目={sorted(provided)}")
    new_type_in = _check_type(body["type"]) if "type" in provided and body.get("type") is not None else None
    with get_conn() as conn, conn.cursor() as cur:
        cur_row = _require_part(cur, user_id, part_id)
        _require_editable(cur, user_id, cur_row)
        if cur_row["is_deleted"]:
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済みのパーツ part_id={part_id}")
        old_type = cur_row["ptype"]
        new_type = new_type_in or old_type
        if new_type != old_type and "checklist" in (old_type, new_type):
            raise ConflictError(CHECKLIST_MESSAGE, reason=f"チェックリストの種別変更 {old_type}->{new_type}")
        if old_type == "checklist":
            return _load_out(cur, user_id, part_id)  # 本文を持たないため、変更するものはない

        old_group, new_group = _group(old_type), _group(new_type)
        has_data = "data" in provided and body.get("data") is not None
        if old_group != new_group and not has_data:
            raise InvalidInputError("内容を指定してください", reason=f"組をまたぐ種別変更で data がない {old_type}->{new_type}")

        new_data: str | None = None  # None は変更しない
        new_size: int | None = None
        filename, title, markers, scale = "", "", [], 1.0
        content_changed = False

        if new_group == "text":
            if has_data:
                new_data = _text_value(body["data"], "data")
        elif new_group == "action":
            if has_data:
                new_data = normalize_action_plan(body["data"] if isinstance(body["data"], str) else "")
        else:  # binary（画像・バイナリ）
            was_binary = old_group == "binary"
            if has_data:
                new_size = _decode_binary(body["data"], new_type)
                new_data = body["data"]
                content_changed = not (was_binary and repo.data_equals(cur, part_id, new_data))
            elif new_type in IMAGE_TYPES and new_type != old_type:
                _signature_of_prefix(repo.data_prefix(cur, part_id), new_type)
            filename = _clean_filename(body["filename"]) if "filename" in provided and body.get("filename") is not None else cur_row["filename"]
            if filename.strip() == "":
                raise InvalidInputError(FILENAME_MESSAGE, reason="ファイル名が空")
            if new_type in IMAGE_TYPES:
                was_image = old_type in IMAGE_TYPES
                title = _text_value(body["title"], "title") if "title" in provided and body.get("title") is not None else (cur_row["title"] if was_image else "")
                if "markers" in provided and body.get("markers") is not None:
                    markers = validate_markers(body["markers"])
                elif content_changed or not was_image:
                    markers = []
                else:
                    markers = cur_row["markers"]
                if "image_scale" in provided and body.get("image_scale") is not None:
                    scale = validate_scale(body["image_scale"])
                else:
                    scale = float(cur_row["image_scale"]) if was_image else 1.0

        # 画像・バイナリは、中身・種別・ファイル名のいずれかが変わるとき、更新前の内容を過去世代として保管する
        if old_group == "binary":
            changed = content_changed or new_type != old_type or filename != cur_row["filename"] or new_group != "binary"
            if changed:
                repo.snapshot_revision(cur, user_id, part_id)
                repo.prune_revisions(cur, part_id, cfg.parts_max_revisions)

        # 大きさ: 画像・バイナリは、中身を差し替えたときだけ更新する。それ以外の種別は 0
        byte_size = new_size if new_group == "binary" else 0
        repo.update_part(
            cur, part_id,
            ptype=new_type, data=new_data, byte_size=byte_size,
            filename=filename, title=title, markers=markers, image_scale=scale,
        )
        out = _load_out(cur, user_id, part_id)
    write("INF", f"パーツ更新成功 user_id={user_id} part_id={part_id} type={new_type}")
    return out


# ---- 削除・削除解除・入れ替え ---------------------------------------------------


def delete_part(user_id: int, part_id: int) -> None:
    write("INF", f"パーツ削除要求 user_id={user_id} part_id={part_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = _require_part(cur, user_id, part_id)
        _require_editable(cur, user_id, row)
        if row["is_deleted"]:
            raise ConflictError("既に削除されています", reason=f"削除済み part_id={part_id}")
        repo.set_deleted(cur, part_id, True)
    write("INF", f"パーツ削除成功 user_id={user_id} part_id={part_id}")


def undelete_part(user_id: int, part_id: int) -> dict[str, Any]:
    write("INF", f"パーツ削除解除要求 user_id={user_id} part_id={part_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = _require_part(cur, user_id, part_id)
        _require_editable(cur, user_id, row)
        if not row["is_deleted"]:
            raise ConflictError("削除されていません", reason=f"削除済みでない part_id={part_id}")
        # 並び順は、削除済みを含めて一意のため、元の位置のまま戻せる
        repo.set_deleted(cur, part_id, False)
        out = _load_out(cur, user_id, part_id)
    write("INF", f"パーツ削除解除成功 user_id={user_id} part_id={part_id}")
    return out


def swap_order(user_id: int, part_id_1: int, part_id_2: int) -> None:
    write("INF", f"パーツ並び替え要求 user_id={user_id} part_id_1={part_id_1} part_id_2={part_id_2}")
    if part_id_1 == part_id_2:
        raise InvalidInputError(reason="同じパーツの入れ替え")
    with get_conn() as conn, conn.cursor() as cur:
        a = _require_part(cur, user_id, part_id_1)
        b = _require_part(cur, user_id, part_id_2)
        if a["file_id"] != b["file_id"]:
            raise InvalidInputError("同じ場所の項目ではありません", reason="所属ファイルが違う")
        _require_editable(cur, user_id, a)
        if a["is_deleted"] or b["is_deleted"]:
            raise ConflictError(DELETED_MESSAGE, reason="削除済みのパーツの入れ替え")
        repo.lock_parts(cur, a["file_id"])
        repo.set_sort_order(cur, part_id_1, -1)
        repo.set_sort_order(cur, part_id_2, a["sort_order"])
        repo.set_sort_order(cur, part_id_1, b["sort_order"])
    write("INF", f"パーツ並び替え成功 user_id={user_id}")


# ---- 中身の取得 -------------------------------------------------------------


_MEDIA_TYPES = {"jpeg": "image/jpeg", "png": "image/png", "binary": "application/octet-stream"}


def get_content(user_id: int, part_id: int) -> dict[str, Any]:
    write("INF", f"パーツの中身の取得要求 user_id={user_id} part_id={part_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = repo.get_content(cur, user_id, part_id)
    if row is None:
        raise NotFoundError(reason=f"中身なし user_id={user_id} part_id={part_id}")
    return _content_out(row)


def get_revision_content(user_id: int, revision_id: int) -> dict[str, Any]:
    write("INF", f"過去世代の取得要求 user_id={user_id} revision_id={revision_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = repo.get_revision_content(cur, user_id, revision_id)
    if row is None:
        raise NotFoundError(reason=f"過去世代なし user_id={user_id} revision_id={revision_id}")
    return _content_out(row)


def _content_out(row: dict[str, Any]) -> dict[str, Any]:
    raw = base64.b64decode(row["data"])
    return {
        "content": raw,
        "media_type": _MEDIA_TYPES[row["ptype"]],
        "filename": row["filename"],
        "inline": row["ptype"] in IMAGE_TYPES,
    }
