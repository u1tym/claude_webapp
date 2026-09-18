from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.cli import main
from app.repos import assignment_exists, get_feature, get_user_by_username
from png_bytes import PNG_1X1


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def test_cli_user_add_list_delete(tmp_path: Path, capsys) -> None:
    username = _unique("cliuser")
    assert main(["user", "add", username, "pw"]) == 0
    assert main(["user", "list"]) == 0
    listed = capsys.readouterr().out
    assert username in listed
    assert main(["user", "delete", username]) == 0
    user = get_user_by_username(username)
    assert user is not None
    assert user.is_deleted is True
    assert main(["user", "delete", username]) == 1
    assert main(["user", "delete", _unique("missing")]) == 1


def test_cli_feature_add_without_icon() -> None:
    feature_id = _unique("noicon")
    assert main(["feature", "add", feature_id, "アイコンなし", "http://localhost/n"]) == 0
    feat = get_feature(feature_id)
    assert feat is not None
    assert feat.title == "アイコンなし"
    assert feat.icon == b""
    assert feat.icon_media_type == ""


def test_cli_feature_and_menu(tmp_path: Path) -> None:
    icon = tmp_path / "icon.png"
    icon.write_bytes(PNG_1X1)
    username = _unique("cliowner")
    feature_id = _unique("clifeat")
    assert main(["user", "add", username, "pw"]) == 0
    assert main(["feature", "add", feature_id, "タイトル", "http://localhost/x", str(icon)]) == 0
    feat = get_feature(feature_id)
    assert feat is not None
    assert feat.title == "タイトル"
    assert main(["feature", "update", feature_id, "--title", "変更"]) == 0
    assert get_feature(feature_id).title == "変更"
    assert main(["menu", "assign", username, feature_id, "10"]) == 0
    user = get_user_by_username(username)
    assert user is not None
    assert assignment_exists(user.id, feature_id)
    assert main(["menu", "assign", username, feature_id, "11"]) == 1
    assert main(["menu", "unassign", username, feature_id]) == 0
    assert assignment_exists(user.id, feature_id) is False
    assert main(["menu", "unassign", username, feature_id]) == 1
    assert main(["feature", "delete", feature_id]) == 0
    assert get_feature(feature_id).is_deleted is True
    assert main(["feature", "delete", feature_id]) == 1
    assert main(["feature", "update", feature_id, "--title", "x"]) == 1
