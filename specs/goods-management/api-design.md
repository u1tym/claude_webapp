# goods-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_GOODS_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `goods-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、削除済み、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 参照されているため削除できない | 409、本文 `{ "detail": "他のデータから参照されているため削除できません" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/persons` | 要 | REQ-004 |
| POST | `/persons` | 要 | REQ-003 |
| PATCH | `/persons/{person_id}` | 要 | REQ-005 |
| DELETE | `/persons/{person_id}` | 要 | REQ-006 |
| GET | `/artists` | 要 | REQ-008 |
| GET | `/artists/{artist_id}` | 要 | REQ-009 |
| POST | `/artists` | 要 | REQ-007 |
| PATCH | `/artists/{artist_id}` | 要 | REQ-010 |
| DELETE | `/artists/{artist_id}` | 要 | REQ-011 |
| GET | `/media` | 要 | REQ-013 |
| POST | `/media` | 要 | REQ-012 |
| PATCH | `/media/{media_id}` | 要 | REQ-014 |
| DELETE | `/media/{media_id}` | 要 | REQ-015 |
| GET | `/persons/{person_id}/related-artists` | 要 | REQ-016 |
| GET | `/persons/{person_id}/related-media` | 要 | REQ-016 |
| GET | `/goods` | 要 | REQ-017 |
| GET | `/goods/{goods_id}` | 要 | REQ-019 |
| POST | `/goods` | 要 | REQ-020 |
| PATCH | `/goods/{goods_id}` | 要 | REQ-021 |
| DELETE | `/goods/{goods_id}` | 要 | REQ-023 |
| POST | `/goods/{goods_id}/images` | 要 | REQ-022 |
| DELETE | `/goods/{goods_id}/images/{image_id}` | 要 | REQ-022 |

`GET /persons/{person_id}/related-artists` ／ `related-media` は `GET /persons/{person_id}` という単件取得エンドポイントを持たないため、パスの衝突は無い。

## エンドポイント詳細

### GET `/settings`

- 認証: 不要

要求: なし

応答: 200

```json
{
  "login_url": "string",
  "menu_url": "string",
  "icon_system": "string",
  "icon_back": "string"
}
```

`icon_*` は data URL。未ログイン時の誘導先（`login_url`）と、ヘッダの「戻る」（`menu_url`）に使う。`public.system_settings` から取得する（`portal` が管理するデータを読むだけで、本機能は変更しない）。

エラー:

| 状況 | 応答 |
|------|------|
| 必須キーが欠けている | 500 |

### GET `/persons`

対応 REQ: REQ-004

要求: なし

応答: 200

```json
{ "items": [ { "id": 1, "name": "山田花子" } ] }
```

処理概要: ログイン中ユーザ本人の、削除されていない人物を `id` 昇順で返す。

エラー: 共通エラーのみ。

### POST `/persons`

対応 REQ: REQ-003

要求:

```json
{ "name": "山田花子" }
```

`name` は必須、空・空白のみ不可。

応答: 201（登録内容。形式は GET `/persons` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ、必須項目が無い | 400 |

処理概要: 人物を登録する。`name` はトリムして保存する。

### PATCH `/persons/{person_id}`

対応 REQ: REQ-005

要求: POST `/persons` と同じ形式

応答: 200（更新後の内容）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ | 400 |
| 本人の削除されていない人物でない | 404 |

処理概要: 人物の名称を変更する。

### DELETE `/persons/{person_id}`

対応 REQ: REQ-006

要求: なし

応答: 204。本文なし。

処理概要: 人物を論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない人物でない | 404 |
| いずれかの未削除のアーティストに紐付いている | 409 |

### GET `/artists`

対応 REQ: REQ-008

要求: なし

応答: 200

```json
{ "items": [ { "id": 1, "name": "サンプルズ" } ] }
```

処理概要: ログイン中ユーザ本人の、削除されていないアーティストを `id` 昇順で返す。

エラー: 共通エラーのみ。

### GET `/artists/{artist_id}`

対応 REQ: REQ-009

要求: なし

応答: 200

```json
{
  "id": 1,
  "name": "サンプルズ",
  "persons": [ { "id": 1, "name": "山田花子" } ]
}
```

処理概要: 本人の削除されていないアーティスト1件の名称と、紐付く削除されていない人物の一覧を返す。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていないアーティストでない | 404 |

### POST `/artists`

対応 REQ: REQ-007

要求:

```json
{ "name": "サンプルズ", "person_ids": [1, 2] }
```

`name` は必須、空・空白のみ不可。`person_ids` は省略可（省略時は空配列扱い）。

応答: 201（登録内容。形式は GET `/artists/{artist_id}` の応答と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ、必須項目が無い | 400 |
| `person_ids` に、本人の削除されていない人物でない ID が含まれる | 404 |

処理概要: アーティストを登録し、指定した人物と関連付ける。

### PATCH `/artists/{artist_id}`

対応 REQ: REQ-010

要求: POST `/artists` と同じ形式（`person_ids` は変更後の全件を送る）

応答: 200（更新後の内容）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の削除されていないアーティストでない | 404 |
| `person_ids` に、本人の削除されていない人物でない ID が含まれる | 404 |

処理概要: アーティストの名称を変更し、`person_ids` と現在の関連との差分を追加・削除する。

### DELETE `/artists/{artist_id}`

対応 REQ: REQ-011

要求: なし

応答: 204。本文なし。

処理概要: アーティストを論理削除する。人物との関連（`artist_persons`）は削除しない。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていないアーティストでない | 404 |
| いずれかの未削除の商品から参照されている | 409 |

### GET `/media`

対応 REQ: REQ-013

要求: なし

応答: 200

```json
{ "items": [ { "id": 1, "name": "1stシングル" } ] }
```

処理概要: ログイン中ユーザ本人の、削除されていない媒体を `id` 昇順で返す。

エラー: 共通エラーのみ。

### POST `/media`

対応 REQ: REQ-012

要求:

```json
{ "name": "1stシングル" }
```

応答: 201（登録内容。形式は GET `/media` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ、必須項目が無い | 400 |

処理概要: 媒体を登録する。

### PATCH `/media/{media_id}`

対応 REQ: REQ-014

要求: POST `/media` と同じ形式

応答: 200（更新後の内容）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ | 400 |
| 本人の削除されていない媒体でない | 404 |

処理概要: 媒体の名称を変更する。

### DELETE `/media/{media_id}`

対応 REQ: REQ-015

要求: なし

応答: 204。本文なし。

処理概要: 媒体を論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない媒体でない | 404 |
| いずれかの未削除の商品から参照されている | 409 |

### GET `/persons/{person_id}/related-artists`

対応 REQ: REQ-016

要求: なし

応答: 200

```json
{ "items": [ { "id": 1, "name": "サンプルズ" } ] }
```

処理概要: 指定した人物が本人の削除されていない人物のとき、その人物に `artist_persons` で紐づく、削除されていないアーティストを返す。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない人物でない | 404 |

### GET `/persons/{person_id}/related-media`

対応 REQ: REQ-016

要求: なし

応答: 200

```json
{ "items": [ { "id": 1, "name": "1stシングル" } ] }
```

処理概要: 指定した人物に紐づくアーティストが登録した、削除されていない商品が属する媒体を、重複を除いて返す。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない人物でない | 404 |

### GET `/goods`

対応 REQ: REQ-017

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `person_id` | 要 | 絞り込みの起点となる人物 |
| `artist_id` | 否 | 省略時は、`person_id` に紐づく全アーティストが対象（「すべて」） |
| `media_id` | 否 | 省略時は、対象アーティストの商品が属する全媒体が対象（「すべて」） |

応答: 200

```json
{
  "items": [
    {
      "goods_id": 100,
      "media_id": 1,
      "media_name": "1stシングル",
      "artist_id": 1,
      "artist_name": "サンプルズ",
      "title": "サンプルグッズ",
      "release_date": "2026-01-01",
      "is_owned": true,
      "code_number": "ABC-123",
      "thumbnail_image_type": "image/jpeg",
      "thumbnail_image_data": "base64string"
    }
  ]
}
```

`thumbnail_image_type` / `thumbnail_image_data` は、その商品に登録されている画像のうち表示順が最も先のもの。画像が無い商品は両方 `null`。`items` は `release_date` 降順、同日は `id` 降順で返す。

処理概要: `person_id` に紐づくアーティストのうち、`artist_id` を指定していればそれに絞り込み、削除されていない商品を対象に、`media_id` を指定していればそれにも絞り込んで返す。

エラー:

| 状況 | 応答 |
|------|------|
| `person_id` が無い | 400 |
| `person_id` が本人の削除されていない人物でない | 404 |
| `artist_id` を指定していて、本人の削除されていないアーティストでない、または `person_id` に紐づかない | 404 |
| `media_id` を指定していて、本人の削除されていない媒体でない | 404 |

### GET `/goods/{goods_id}`

対応 REQ: REQ-019

要求: なし

応答: 200

```json
{
  "id": 100,
  "media_id": 1,
  "artist_id": 1,
  "title": "サンプルグッズ",
  "release_date": "2026-01-01",
  "memo": "メモ",
  "is_owned": true,
  "code_number": "ABC-123",
  "images": [
    { "id": 1, "image_type": "image/jpeg", "image_data": "base64string", "display_order": 1 }
  ]
}
```

処理概要: 本人の削除されていない商品1件を、登録済みの全画像とともに返す。`images` は `display_order` 昇順。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない商品でない | 404 |

### POST `/goods`

対応 REQ: REQ-020

要求:

```json
{
  "media_id": 1,
  "artist_id": 1,
  "title": "サンプルグッズ",
  "release_date": "2026-01-01",
  "memo": "メモ",
  "is_owned": false,
  "code_number": "ABC-123"
}
```

| フィールド | 型 | 必須 | 説明 |
|------------|----|----|------|
| `media_id` | integer | 要 | 本人の削除されていない媒体 |
| `artist_id` | integer | 要 | 本人の削除されていないアーティスト |
| `title` | string | 要 | 空・空白のみ不可 |
| `release_date` | string(date) \| null | 否 | 省略・`null` なら登録日を設定する |
| `memo` | string \| null | 否 | 省略時は `null` |
| `is_owned` | boolean | 否 | 省略時は `false` |
| `code_number` | string \| null | 否 | 省略時は `null` |

応答: 201（登録内容。形式は GET `/goods/{goods_id}` の応答と同じ。`images` は空配列）

エラー:

| 状況 | 応答 |
|------|------|
| `title` が空・空白のみ、必須項目が無い | 400 |
| `media_id` / `artist_id` が本人の削除されていない行でない | 404 |

処理概要: 商品を登録する。画像はこの API では扱わない（登録後に `POST /goods/{goods_id}/images` で追加する）。

### PATCH `/goods/{goods_id}`

対応 REQ: REQ-021

要求: POST `/goods` と同じ形式

応答: 200（更新後の内容。`images` は現在登録済みの画像）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の削除されていない商品でない | 404 |
| `media_id` / `artist_id` が本人の削除されていない行でない | 404 |

処理概要: 商品の内容を更新する。画像は更新しない。`release_date` を省略・`null` にした場合は既存の値を保持する。

### DELETE `/goods/{goods_id}`

対応 REQ: REQ-023

要求: なし

応答: 204。本文なし。

処理概要: 商品を論理削除する。登録済みの画像は削除しない。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない商品でない | 404 |

### POST `/goods/{goods_id}/images`

対応 REQ: REQ-022

要求:

```json
{ "image_type": "image/jpeg", "image_data": "base64string" }
```

`image_type` は `image/png` または `image/jpeg`。`image_data` は Base64 文字列（必須）。

応答: 201

```json
{ "id": 2, "image_type": "image/jpeg", "image_data": "base64string", "display_order": 2 }
```

エラー:

| 状況 | 応答 |
|------|------|
| `image_type` が許可値でない、`image_data` が無い・Base64として不正 | 400 |
| 本人の削除されていない商品でない | 404 |

処理概要: 指定した商品に画像を1枚追加する。`display_order` はその商品の登録済み画像のうち最大値+1を採番する。上限枚数は設けない。

### DELETE `/goods/{goods_id}/images/{image_id}`

対応 REQ: REQ-022

要求: なし

応答: 204。本文なし。

エラー:

| 状況 | 応答 |
|------|------|
| 商品が本人の削除されていない商品でない | 404 |
| 画像がその商品に属さない、または存在しない | 404 |

処理概要: 指定した商品の指定した画像を削除する。

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通の認証・権限エラー |
| REQ-002 | 全エンドポイントの本人絞り込み（404 で他人の行を隠す） |
| REQ-003 | POST `/persons` |
| REQ-004 | GET `/persons` |
| REQ-005 | PATCH `/persons/{person_id}` |
| REQ-006 | DELETE `/persons/{person_id}` |
| REQ-007 | POST `/artists` |
| REQ-008 | GET `/artists` |
| REQ-009 | GET `/artists/{artist_id}` |
| REQ-010 | PATCH `/artists/{artist_id}` |
| REQ-011 | DELETE `/artists/{artist_id}` |
| REQ-012 | POST `/media` |
| REQ-013 | GET `/media` |
| REQ-014 | PATCH `/media/{media_id}` |
| REQ-015 | DELETE `/media/{media_id}` |
| REQ-016 | GET `/persons/{person_id}/related-artists`、GET `/persons/{person_id}/related-media` |
| REQ-017 | GET `/goods` |
| REQ-018 | エンドポイント対象外（フロントエンド内の絞り込み） |
| REQ-019 | GET `/goods/{goods_id}` |
| REQ-020 | POST `/goods` |
| REQ-021 | PATCH `/goods/{goods_id}` |
| REQ-022 | POST `/goods/{goods_id}/images`、DELETE `/goods/{goods_id}/images/{image_id}` |
| REQ-023 | DELETE `/goods/{goods_id}` |
| REQ-024 | エンドポイント対象外（ログ） |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 | 未承認 | 初版 |
| 2026-09-20 | 承認済み | 初版を承認 |
