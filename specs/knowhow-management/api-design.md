# knowhow-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_KNOWHOW_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `knowhow-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

#### API キーによる認証

他システム連携のため、Cookie に加えて API キーによる認証を受け付ける。API キーの発行・失効は `api-key-management` が担う。契約の詳細は `specs/api-key-management/api-design.md` の「対象機能の API キー認証」。

- 要求ヘッダ `Authorization: Bearer <API キー>` で受け取る（スキーム名は大文字小文字を区別しない）。URL では受け取らない。Cookie は不要。
- `Authorization` ヘッダがあるときは API キーだけで判定し、Cookie・`DEBUG_USER` での判定に戻らない。無いときは従来どおり。
- `Bearer` 方式でない、キーが空、該当なし、失効済み、有効期限切れ、持ち主が論理削除済みは、いずれも未ログイン（401）。このときヘッダ `WWW-Authenticate: Bearer` を付ける。理由は本文で区別しない。
- 持ち主に識別子 `knowhow-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- 許可したときは持ち主をログイン中ユーザとして処理し、API キーの最終利用日時を更新する。セッションの期限は延ばさない。
- GET `/settings` は、`Authorization` ヘッダがあっても判定しない（従来どおり認証不要）。
- 各エンドポイントのパス・要求・応答・エラーは、Cookie で利用したときと同じ。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、削除済み、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 名称が重複 | 409、本文 `{ "detail": "保存できませんでした" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/major-categories` | 要 | REQ-002 |
| POST | `/major-categories` | 要 | REQ-003 |
| PATCH | `/major-categories/{major_category_id}` | 要 | REQ-004 |
| DELETE | `/major-categories/{major_category_id}` | 要 | REQ-005 |
| GET | `/major-categories/{major_category_id}/middle-categories` | 要 | REQ-002 |
| POST | `/major-categories/{major_category_id}/middle-categories` | 要 | REQ-006 |
| PATCH | `/middle-categories/{middle_category_id}` | 要 | REQ-007 |
| DELETE | `/middle-categories/{middle_category_id}` | 要 | REQ-008 |
| GET | `/middle-categories/{middle_category_id}/knowhows` | 要 | REQ-009 |
| GET | `/knowhows/search` | 要 | REQ-015 |
| GET | `/knowhows/{knowhow_id}` | 要 | REQ-010 |
| POST | `/knowhows` | 要 | REQ-011 |
| PATCH | `/knowhows/{knowhow_id}` | 要 | REQ-012 |
| DELETE | `/knowhows/{knowhow_id}` | 要 | REQ-013 |
| POST | `/knowhows/swap-display-order` | 要 | REQ-014 |

`GET /knowhows/search` は `GET /knowhows/{knowhow_id}` より先に定義し、`search` がパス変数として解釈されないようにする（実装上の注意）。

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

処理概要: システム設定からログイン URL、メニュー URL、システムアイコン、戻るアイコンを返す。

エラー:

| 状況 | 応答 |
|------|------|
| 必須キーが欠けている | 500 |

### GET `/major-categories`

対応 REQ: REQ-002

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 1, "name": "サーバ運用", "display_order": 1 }
  ]
}
```

処理概要: ログイン中ユーザ本人の、削除されていない大項目を表示順（`display_order` 昇順、`id` 昇順）で返す。

エラー: 共通エラーのみ。

### POST `/major-categories`

対応 REQ: REQ-003

要求:

```json
{ "name": "サーバ運用" }
```

`name` は必須、空・空白のみ不可。

応答: 201（登録内容。形式は GET `/major-categories` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ、必須項目が無い | 400 |
| `name` が、本人の削除されていない大項目と重複する | 409 |

処理概要: 大項目を登録する。`name` はトリムして保存する。`display_order` は本人の未削除大項目内で自動採番する。

### PATCH `/major-categories/{major_category_id}`

対応 REQ: REQ-004

要求: POST `/major-categories` と同じ形式

応答: 200（更新後の内容。形式は GET `/major-categories` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の削除されていない大項目でない | 404 |
| 変更後の `name` が、自身以外の本人の削除されていない大項目と重複する | 409 |

処理概要: 大項目の名称を変更する。

### DELETE `/major-categories/{major_category_id}`

対応 REQ: REQ-005

要求: なし

応答: 204。本文なし。

処理概要: 大項目を論理削除する。配下の未削除の中項目、およびその配下の未削除のノウハウも、あわせて論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない大項目でない | 404 |

### GET `/major-categories/{major_category_id}/middle-categories`

対応 REQ: REQ-002

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 10, "major_category_id": 1, "name": "バックアップ", "display_order": 1 }
  ]
}
```

処理概要: 指定した大項目が本人の削除されていない大項目のとき、その配下の削除されていない中項目を表示順で返す。

エラー:

| 状況 | 応答 |
|------|------|
| 大項目が本人の削除されていない大項目でない | 404 |

### POST `/major-categories/{major_category_id}/middle-categories`

対応 REQ: REQ-006

要求:

```json
{ "name": "バックアップ" }
```

応答: 201（登録内容。形式は GET の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ | 400 |
| 大項目が本人の削除されていない大項目でない | 404 |
| `name` が、同一大項目内の本人の削除されていない中項目と重複する | 409 |

処理概要: 中項目を登録する。`display_order` は同一大項目内の未削除中項目で自動採番する。

### PATCH `/middle-categories/{middle_category_id}`

対応 REQ: REQ-007

要求: `{ "name": "string" }`

応答: 200（更新後の内容）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ | 400 |
| 本人の削除されていない中項目でない | 404 |
| 変更後の `name` が、同一大項目内で自身以外と重複する | 409 |

処理概要: 中項目の名称を変更する。

### DELETE `/middle-categories/{middle_category_id}`

対応 REQ: REQ-008

要求: なし

応答: 204。本文なし。

処理概要: 中項目を論理削除する。配下の未削除のノウハウも、あわせて論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない中項目でない | 404 |

### GET `/middle-categories/{middle_category_id}/knowhows`

対応 REQ: REQ-009

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 100, "title": "設定手順", "keywords": "初期設定", "middle_category_id": 10, "display_order": 1 }
  ]
}
```

`content`（本文）は含めない。`keywords` が無いときは `null`。

処理概要: 指定した中項目が本人の削除されていない中項目のとき、その `middle_category_id` に一致する削除されていないノウハウを表示順で返す。

エラー:

| 状況 | 応答 |
|------|------|
| 中項目が本人の削除されていない中項目でない | 404 |

### GET `/knowhows/search`

対応 REQ: REQ-015

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `keyword` | 要（1件以上） | 検索キーワード。複数指定できる（例: `?keyword=A&keyword=B`）。指定した全キーワードそれぞれが、タイトル・キーワード・本文のいずれかに大文字小文字を区別せず部分一致する行だけを対象にする（AND） |

応答: 200

```json
{
  "items": [
    {
      "knowhow_id": 100,
      "title": "設定手順",
      "display_order": 1,
      "major_category_id": 1,
      "major_category_name": "サーバ運用",
      "middle_category_id": 10,
      "middle_category_name": "バックアップ"
    }
  ]
}
```

未分類（`middle_category_id` が `null`）のノウハウは、`major_category_id` / `major_category_name` / `middle_category_id` / `middle_category_name` をすべて `null` にする。`items` は `id` 昇順で返す。

処理概要: ログイン中ユーザ本人の、削除されていないノウハウ全体（所属する中項目・大項目を問わない）からキーワード検索する。

エラー:

| 状況 | 応答 |
|------|------|
| `keyword` が1つも無い | 400 |

### GET `/knowhows/{knowhow_id}`

対応 REQ: REQ-010

要求: なし

応答: 200

```json
{
  "id": 100,
  "title": "設定手順",
  "keywords": "初期設定",
  "content": "1. ...\n2. ...",
  "middle_category_id": 10,
  "display_order": 1
}
```

処理概要: 本人の削除されていないノウハウ1件を、本文を含めて返す。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていないノウハウでない | 404 |

### POST `/knowhows`

対応 REQ: REQ-011

要求:

```json
{
  "title": "設定手順",
  "keywords": "初期設定",
  "content": "1. ...\n2. ...",
  "middle_category_id": 10
}
```

| フィールド | 型 | 必須 | 説明 |
|------------|----|----|------|
| `title` | string | 要 | 空・空白のみ不可 |
| `keywords` | string \| null | 否 | 省略時は `null` |
| `content` | string | 要 | 空・空白のみ不可 |
| `middle_category_id` | integer \| null | 否 | 省略時・`null` で未分類 |

応答: 201（登録内容。形式は GET `/knowhows/{knowhow_id}` の応答と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `title` / `content` が空・空白のみ、必須項目が無い | 400 |
| `middle_category_id` を指定していて、本人の削除されていない中項目でない | 404 |

処理概要: ノウハウを登録する。`title` / `content` はトリムして保存する。`display_order` は本人・同一所属先（指定した中項目、または未分類）の未削除ノウハウ内で自動採番する。

### PATCH `/knowhows/{knowhow_id}`

対応 REQ: REQ-012

要求: POST `/knowhows` と同じ形式（全項目を送る）

応答: 200（更新後の内容）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の削除されていないノウハウでない | 404 |
| `middle_category_id` を指定していて、本人の削除されていない中項目でない | 404 |

処理概要: ノウハウを更新する。所属先（`middle_category_id`）が変わる場合、変更後の所属先内で `display_order` を再採番する。

### DELETE `/knowhows/{knowhow_id}`

対応 REQ: REQ-013

要求: なし

応答: 204。本文なし。

処理概要: ノウハウを論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていないノウハウでない | 404 |

### POST `/knowhows/swap-display-order`

対応 REQ: REQ-014

要求:

```json
{ "knowhow_id_a": 100, "knowhow_id_b": 101 }
```

応答: 204。本文なし。

処理概要: 指定した2件のノウハウの `display_order` を交換する。

エラー:

| 状況 | 応答 |
|------|------|
| いずれかが本人の削除されていないノウハウでない | 404 |
| 2件の所属先（`middle_category_id`）が一致しない | 400 |

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通の認証・権限エラー |
| REQ-002 | 全エンドポイントの本人絞り込み（404 で他人の行を隠す） |
| REQ-003 | POST `/major-categories` |
| REQ-004 | PATCH `/major-categories/{major_category_id}` |
| REQ-005 | DELETE `/major-categories/{major_category_id}` |
| REQ-006 | POST `/major-categories/{major_category_id}/middle-categories` |
| REQ-007 | PATCH `/middle-categories/{middle_category_id}` |
| REQ-008 | DELETE `/middle-categories/{middle_category_id}` |
| REQ-009 | GET `/middle-categories/{middle_category_id}/knowhows` |
| REQ-010 | GET `/knowhows/{knowhow_id}` |
| REQ-011 | POST `/knowhows` |
| REQ-012 | PATCH `/knowhows/{knowhow_id}` |
| REQ-013 | DELETE `/knowhows/{knowhow_id}` |
| REQ-014 | POST `/knowhows/swap-display-order` |
| REQ-015 | GET `/knowhows/search` |
| REQ-016 | エンドポイント対象外（ログ） |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 10:44 | 未承認 | 初版 |
| 2026-09-20 10:45 | 承認済み | 初版を承認 |
| 2026-09-26 00:43 | 未承認 | 共通の認証に API キーによる認証（`Authorization: Bearer`）を追加。エンドポイントの変更なし |
| 2026-09-26 00:44 | 承認済み | API キー認証への対応を承認 |
