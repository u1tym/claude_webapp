from __future__ import annotations

from conftest import TestUser

SYSTEM_GENRES = ["洋画", "邦画", "アニメ", "ライブ", "ドラマ", "ドキュメンタリー", "その他"]


def test_genres_start_with_system_genres(user: TestUser) -> None:
    items = user.client.get("/genres").json()["items"]
    system = [g for g in items if g["is_system"]]
    assert [g["name"] for g in system] == SYSTEM_GENRES
    assert [g["sort_order"] for g in system] == [1, 2, 3, 4, 5, 6, 99]


def test_add_user_genre_and_order(user: TestUser) -> None:
    res = user.client.post("/genres", json={"name": "  邦画名作  ", "sort_order": 10})
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == "邦画名作"
    assert created["is_system"] is False
    items = user.client.get("/genres").json()["items"]
    orders = [g["sort_order"] for g in items]
    assert orders == sorted(orders)
    assert created["id"] in [g["id"] for g in items]


def test_genre_default_sort_order_is_zero(user: TestUser) -> None:
    assert user.client.post("/genres", json={"name": "先頭"}).json()["sort_order"] == 0


def test_duplicate_user_genre_is_409(user: TestUser) -> None:
    assert user.client.post("/genres", json={"name": "重複"}).status_code == 201
    res = user.client.post("/genres", json={"name": "重複"})
    assert res.status_code == 409
    assert res.json() == {"detail": "同じ名前のジャンルがあります"}


def test_user_genre_may_share_name_with_system_genre(user: TestUser) -> None:
    assert user.client.post("/genres", json={"name": "洋画"}).status_code == 201


def test_user_genres_are_private(user: TestUser, other_user: TestUser) -> None:
    user.client.post("/genres", json={"name": "自分だけ"})
    names = [g["name"] for g in other_user.client.get("/genres").json()["items"]]
    assert "自分だけ" not in names
    # 他ユーザは同じ名前を登録できる
    assert other_user.client.post("/genres", json={"name": "自分だけ"}).status_code == 201


def test_genre_validation(user: TestUser) -> None:
    for body in ({"name": ""}, {"name": "   "}, {"name": "x" * 101}, {"name": "a", "sort_order": -1}, {}):
        assert user.client.post("/genres", json=body).status_code == 400, body


def test_create_and_list_series(user: TestUser) -> None:
    first = user.client.post("/series", json={"title": "作品A", "description": "説明"})
    assert first.status_code == 201
    assert first.json()["description"] == "説明"
    second = user.client.post("/series", json={"title": "作品B"})
    assert second.json()["description"] is None
    body = user.client.get("/series").json()
    assert [s["title"] for s in body["items"]] == ["作品B", "作品A"]  # 登録日時の降順
    assert body["pagination"] == {"page": 1, "per_page": 20, "total_count": 2, "total_pages": 1}


def test_series_search_is_case_insensitive_partial(user: TestUser) -> None:
    user.client.post("/series", json={"title": "Space Story"})
    user.client.post("/series", json={"title": "別の作品"})
    items = user.client.get("/series", params={"q": "space"}).json()["items"]
    assert [s["title"] for s in items] == ["Space Story"]
    # % はワイルドカードではなく文字として扱う
    assert user.client.get("/series", params={"q": "%"}).json()["items"] == []


def test_series_pagination(user: TestUser) -> None:
    for i in range(3):
        user.client.post("/series", json={"title": f"作品{i}"})
    body = user.client.get("/series", params={"page": 2, "per_page": 2}).json()
    assert len(body["items"]) == 1
    assert body["pagination"]["total_pages"] == 2
    empty = user.client.get("/series", params={"q": "存在しない"}).json()
    assert empty["pagination"]["total_pages"] == 0


def test_series_paging_out_of_range_is_400(user: TestUser) -> None:
    for params in ({"page": 0}, {"per_page": 0}, {"per_page": 101}):
        assert user.client.get("/series", params=params).status_code == 400, params


def test_series_validation(user: TestUser) -> None:
    for body in ({"title": ""}, {"title": "  "}, {"title": "x" * 501}, {}):
        assert user.client.post("/series", json=body).status_code == 400, body


def test_series_detail_lists_videos_in_order(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    for title, order, episode in (("第2話", 2, 2), ("第1話", 1, 1), ("特典", 3, None)):
        res = user.client.post(
            "/videos",
            json={
                "title": title,
                "series_id": series_id,
                "sort_order": order,
                "episode_number": episode,
                "duration_ms": 1000,
            },
        )
        assert res.status_code == 201
    detail = user.client.get(f"/series/{series_id}").json()
    assert [v["title"] for v in detail["videos"]] == ["第1話", "第2話", "特典"]
    assert detail["videos"][0]["status"] == "uploading"  # 全状態を含む


def test_other_users_series_is_404(user: TestUser, other_user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    assert other_user.client.get(f"/series/{series_id}").status_code == 404
    assert other_user.client.get("/series").json()["items"] == []
    assert user.client.get("/series/99999999").status_code == 404
