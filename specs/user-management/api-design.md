# API設計: user-management（ユーザ管理）

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。テーブル定義は `db-design.md` を参照する。ログイン・ログアウトの API は持たない。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `user-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外は認証要かつ本機能の割当要。

### アイコンの載せ方

DB のバイナリとメディアタイプから、JSON では data URL 文字列にする。形式は `data:{media_type};base64,{payload}`。要求でアイコンを送るときも同じ形式とする。配信用の画像ファイルは置かない。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし | 404、本文 `{ "detail": "対象がありません" }` |
| 保存の失敗（重複など） | 409、本文 `{ "detail": "保存できませんでした" }` |
| 削除・解除の失敗（禁止を含む） | 409、本文 `{ "detail": "削除できませんでした" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | REQ-001 |
| GET | `/users` | 要 | REQ-002 |
| POST | `/users` | 要 | REQ-003 |
| PATCH | `/users/{user_id}` | 要 | REQ-004 |
| DELETE | `/users/{user_id}` | 要 | REQ-005 |
| GET | `/features` | 要 | REQ-006 |
| POST | `/features` | 要 | REQ-007 |
| PATCH | `/features/{feature_id}` | 要 | REQ-008 |
| DELETE | `/features/{feature_id}` | 要 | REQ-009 |
| GET | `/assignments` | 要 | REQ-010 |
| POST | `/assignments` | 要 | REQ-011 |
| DELETE | `/assignments/{user_id}/{feature_id}` | 要 | REQ-012 |

REQ-013 は各操作 API のログ出力であり、専用エンドポイントは無い。

## エンドポイント

### GET `/settings`

- 認証: 不要
- 対応 REQ: REQ-001

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

`icon_*` は data URL。未ログイン時の誘導と、ヘッダの戻るに使う。

処理概要: システム設定からログイン URL、メニュー URL、システムアイコン、戻るアイコンを返す。

エラー:

| 状況 | 応答 |
|------|------|
| 必須キーが欠けている | 500 |

### GET `/users`

- 認証: 要
- 対応 REQ: REQ-002

要求: なし

応答: 200

```json
{
  "items": [
    {
      "id": 1,
      "username": "string",
      "email": "string",
      "is_self": true
    }
  ]
}
```

`items` はユーザ名順。パスワードは含めない。`email` はメールアドレス。`is_self` は操作中ユーザなら true。0 件なら空配列。

処理概要: 未削除ユーザを返す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/users`

- 認証: 要
- 対応 REQ: REQ-003

要求:

```json
{
  "username": "string",
  "password": "string",
  "email": "string"
}
```

応答: 201

```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "is_self": false
}
```

処理概要: ユーザを追加する。パスワードはハッシュして保存する。メールアドレスはログインに使わない。

エラー:

| 状況 | 応答 |
|------|------|
| `username`、`password`、または `email` が無い／空 | 400 |
| `email` に `@` が無い、または `@` の前後に文字が無い | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 同じユーザ名が既にある | 409、保存できませんでした |

### PATCH `/users/{user_id}`

- 認証: 要
- 対応 REQ: REQ-004

要求:

```json
{
  "username": "string",
  "password": "string",
  "email": "string"
}
```

`password` は省略可。空または省略ならパスワードは変えない。`email` は必須。空にしない。

応答: 200

```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "is_self": true
}
```

処理概要: 未削除ユーザのユーザ名とメールアドレスを更新する。パスワードが空でなければハッシュして更新する。メールアドレスはログインに使わない。

エラー:

| 状況 | 応答 |
|------|------|
| `username` または `email` が無い／空 | 400 |
| `email` に `@` が無い、または `@` の前後に文字が無い | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、または論理削除済み | 404 |
| 変更後のユーザ名が既にある | 409、保存できませんでした |

### DELETE `/users/{user_id}`

- 認証: 要
- 対応 REQ: REQ-005

要求: なし

応答: 204。本文なし。

処理概要: ユーザを論理削除する。そのユーザのセッション行を削除する。自分自身は削除しない。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、または既に論理削除済み | 404 |
| 自分自身 | 409、削除できませんでした |

### GET `/features`

- 認証: 要
- 対応 REQ: REQ-006

要求: なし

応答: 200

```json
{
  "items": [
    {
      "id": "string",
      "title": "string",
      "url": "string",
      "icon": "string",
      "is_protected": true
    }
  ]
}
```

`icon` は data URL。`is_protected` は識別子が `user-management` なら true。0 件なら空配列。

処理概要: 未削除機能を返す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/features`

- 認証: 要
- 対応 REQ: REQ-007

要求:

```json
{
  "id": "string",
  "title": "string",
  "url": "string",
  "icon": "string"
}
```

`icon` は data URL。

応答: 201

```json
{
  "id": "string",
  "title": "string",
  "url": "string",
  "icon": "string",
  "is_protected": false
}
```

処理概要: 機能を追加する。アイコンはバイト列として保存する。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い／空、または `icon` が data URL でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 同じ識別子が既にある | 409、保存できませんでした |

### PATCH `/features/{feature_id}`

- 認証: 要
- 対応 REQ: REQ-008

要求:

```json
{
  "title": "string",
  "url": "string",
  "icon": "string"
}
```

`icon` は省略可。省略または空なら既存のアイコンを維持する。識別子はパスで指定し、本文では変えない。

応答: 200

```json
{
  "id": "string",
  "title": "string",
  "url": "string",
  "icon": "string",
  "is_protected": true
}
```

処理概要: 未削除機能のタイトル、遷移先、任意でアイコンを更新する。

エラー:

| 状況 | 応答 |
|------|------|
| `title` または `url` が無い／空、または `icon` を送ったが data URL でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、または論理削除済み | 404 |

### DELETE `/features/{feature_id}`

- 認証: 要
- 対応 REQ: REQ-009

要求: なし

応答: 204。本文なし。

処理概要: 機能を論理削除する。識別子 `user-management` は削除しない。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、または既に論理削除済み | 404 |
| 本機能自身 | 409、削除できませんでした |

### GET `/assignments`

- 認証: 要
- 対応 REQ: REQ-010

要求: なし

応答: 200

```json
{
  "items": [
    {
      "user_id": 1,
      "username": "string",
      "feature_id": "string",
      "feature_title": "string",
      "display_order": 1,
      "can_unassign": true
    }
  ]
}
```

未削除ユーザかつ未削除機能の割当だけ。`can_unassign` は、操作中ユーザかつ `feature_id` が `user-management` のとき false。0 件なら空配列。

処理概要: 有効な割当を返す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/assignments`

- 認証: 要
- 対応 REQ: REQ-011

要求:

```json
{
  "user_id": 1,
  "feature_id": "string",
  "display_order": 1
}
```

応答: 201

```json
{
  "user_id": 1,
  "username": "string",
  "feature_id": "string",
  "feature_title": "string",
  "display_order": 1,
  "can_unassign": true
}
```

処理概要: 未削除のユーザへ、未削除の機能を表示順付きで割り当てる。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、または `display_order` が整数でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| ユーザまたは機能が無い／論理削除済み | 404 |
| 既に割り当て済み | 409、保存できませんでした |

### DELETE `/assignments/{user_id}/{feature_id}`

- 認証: 要
- 対応 REQ: REQ-012

要求: なし

応答: 204。本文なし。

処理概要: 割当行を削除する。操作中ユーザから本機能を外すことはしない。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 割り当てていない | 404 |
| 自分自身から本機能を外そうとした | 409、削除できませんでした |

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通の認証。GET `/settings`。各操作 API の 401 / 403 |
| REQ-002 | GET `/users`（`email` を含む。パスワードは含めない） |
| REQ-003 | POST `/users`（`email` 必須。空・形式不正は 400） |
| REQ-004 | PATCH `/users/{user_id}`（`email` 必須。空・形式不正は 400） |
| REQ-005 | DELETE `/users/{user_id}` |
| REQ-006 | GET `/features` |
| REQ-007 | POST `/features` |
| REQ-008 | PATCH `/features/{feature_id}` |
| REQ-009 | DELETE `/features/{feature_id}` |
| REQ-010 | GET `/assignments` |
| REQ-011 | POST `/assignments` |
| REQ-012 | DELETE `/assignments/{user_id}/{feature_id}` |
| REQ-013 | 各操作 API のログ（専用パスなし） |

## 未決事項

- なし

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-26 23:00 | 未承認 | 初版 |
| 2026-08-26 23:03 | 承認済み | 初版を承認 |
| 2026-08-30 08:25 | 未承認 | ユーザの要求・応答に `email` を追加。空・形式不正は 400。一意は要求しない |
| 2026-08-30 08:26 | 承認済み | ユーザの `email` を承認 |
