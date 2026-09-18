from __future__ import annotations

import argparse
import sys
from pathlib import Path

from psycopg2 import errors

from app.repos import (
    assignment_exists,
    delete_assignment,
    get_feature,
    get_user_by_username,
    insert_assignment,
    insert_feature,
    insert_user,
    list_active_users,
    logical_delete_feature,
    logical_delete_user,
    update_feature,
)
from app.security import hash_password


class CliError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _media_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    raise CliError(f"未対応の画像形式です: {path.suffix}")


def _read_icon(path_str: str) -> tuple[bytes, str]:
    path = Path(path_str)
    if not path.is_file():
        raise CliError(f"ファイルがありません: {path}")
    return path.read_bytes(), _media_type_for(path)


def _require_active_user(username: str):
    user = get_user_by_username(username)
    if user is None:
        raise CliError("ユーザが存在しません")
    if user.is_deleted:
        raise CliError("既に削除されています")
    return user


def _require_active_feature(feature_id: str):
    feature = get_feature(feature_id)
    if feature is None:
        raise CliError("機能が存在しません")
    if feature.is_deleted:
        raise CliError("既に削除されています")
    return feature


def cmd_user_list(_args: argparse.Namespace) -> int:
    for user in list_active_users():
        print(user.username)
    return 0


def cmd_user_add(args: argparse.Namespace) -> int:
    if get_user_by_username(args.username) is not None:
        raise CliError("同じユーザ名は登録できません")
    insert_user(args.username, hash_password(args.password))
    print("追加しました")
    return 0


def cmd_user_delete(args: argparse.Namespace) -> int:
    user = get_user_by_username(args.username)
    if user is None:
        raise CliError("ユーザが存在しません")
    if user.is_deleted:
        raise CliError("既に削除されています")
    logical_delete_user(user.id)
    print("削除しました")
    return 0


def cmd_feature_add(args: argparse.Namespace) -> int:
    if get_feature(args.id) is not None:
        raise CliError("同じ機能IDは登録できません")
    if args.icon:
        icon, media_type = _read_icon(args.icon)
    else:
        icon, media_type = b"", ""
    insert_feature(args.id, args.title, args.url, icon, media_type)
    print("追加しました")
    return 0


def cmd_feature_update(args: argparse.Namespace) -> int:
    feature = _require_active_feature(args.id)
    title = args.title
    url = args.url
    icon: bytes | None = None
    media_type: str | None = None
    if args.icon:
        icon, media_type = _read_icon(args.icon)
    if title is None and url is None and icon is None:
        raise CliError("更新する項目を指定してください")
    try:
        update_feature(feature.id, title, url, icon, media_type)
    except errors.CheckViolation as exc:
        raise CliError("更新に失敗しました") from exc
    print("更新しました")
    return 0


def cmd_feature_delete(args: argparse.Namespace) -> int:
    feature = get_feature(args.id)
    if feature is None:
        raise CliError("機能が存在しません")
    if feature.is_deleted:
        raise CliError("既に削除されています")
    logical_delete_feature(feature.id)
    print("削除しました")
    return 0


def cmd_menu_assign(args: argparse.Namespace) -> int:
    user = _require_active_user(args.username)
    feature = _require_active_feature(args.feature_id)
    if assignment_exists(user.id, feature.id):
        raise CliError("既に割り当てられています")
    insert_assignment(user.id, feature.id, args.order)
    print("割り当てました")
    return 0


def cmd_menu_unassign(args: argparse.Namespace) -> int:
    user = _require_active_user(args.username)
    feature = get_feature(args.feature_id)
    if feature is None:
        raise CliError("機能が存在しません")
    if not assignment_exists(user.id, feature.id):
        raise CliError("割り当てられていません")
    delete_assignment(user.id, feature.id)
    print("解除しました")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    root = parser.add_subparsers(dest="group", required=True)

    user = root.add_parser("user")
    user_sub = user.add_subparsers(dest="action", required=True)
    user_sub.add_parser("list").set_defaults(func=cmd_user_list)

    add_user = user_sub.add_parser("add")
    add_user.add_argument("username")
    add_user.add_argument("password")
    add_user.set_defaults(func=cmd_user_add)

    del_user = user_sub.add_parser("delete")
    del_user.add_argument("username")
    del_user.set_defaults(func=cmd_user_delete)

    feature = root.add_parser("feature")
    feature_sub = feature.add_subparsers(dest="action", required=True)

    add_feat = feature_sub.add_parser("add")
    add_feat.add_argument("id")
    add_feat.add_argument("title")
    add_feat.add_argument("url")
    add_feat.add_argument("icon", nargs="?", default=None)
    add_feat.set_defaults(func=cmd_feature_add)

    upd_feat = feature_sub.add_parser("update")
    upd_feat.add_argument("id")
    upd_feat.add_argument("--title")
    upd_feat.add_argument("--url")
    upd_feat.add_argument("--icon")
    upd_feat.set_defaults(func=cmd_feature_update)

    del_feat = feature_sub.add_parser("delete")
    del_feat.add_argument("id")
    del_feat.set_defaults(func=cmd_feature_delete)

    menu = root.add_parser("menu")
    menu_sub = menu.add_subparsers(dest="action", required=True)

    assign = menu_sub.add_parser("assign")
    assign.add_argument("username")
    assign.add_argument("feature_id")
    assign.add_argument("order", type=int)
    assign.set_defaults(func=cmd_menu_assign)

    unassign = menu_sub.add_parser("unassign")
    unassign.add_argument("username")
    unassign.add_argument("feature_id")
    unassign.set_defaults(func=cmd_menu_unassign)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(exc.message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
