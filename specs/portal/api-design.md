# API設計: portal（ログインとメニュー）

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。テーブル定義は `db-design.md` を参照する。運用コマンドは HTTP API ではない。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通

### 認証

Cookie ベースのセッション認証を用いる。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。
- 本機能の画面向け API では、ログイン中ユーザの自分のメニューだけを返す。割当が無いことは 403 にせず、空一覧とする。403 は使わない。

### アイコンの載せ方

DB のバイナリとメディアタイプから、JSON では data URL 文字列にする。形式は `data:{media_type};base64,{payload}`。アイコンが無いときは空文字列。配信用の画像ファイルは置かない。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403 は使わない |
| 対象なし | 404、本文 `{ "detail": "対象がありません" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

ログイン失敗は「対象なし」にせず、後述の 401（ログイン失敗）とする。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| POST | `/auth/login` | 不要 | REQ-001, REQ-006, REQ-007 |
| POST | `/auth/logout` | 要 | REQ-008 |
| GET | `/auth/session` | 要 | REQ-003, REQ-009 |
| GET | `/settings` | 不要 | REQ-004, REQ-005 |
| GET | `/menu` | 要 | REQ-005, REQ-012, REQ-013 |

## エンドポイント

### POST `/auth/login`

- 認証: 不要
- 対応 REQ: REQ-001, REQ-006, REQ-007

要求:

```json
{
  "username": "string",
  "password": "string"
}
```

応答: 204。本文なし。`Set-Cookie` で `session_id` を付ける。

処理概要: 未削除ユーザのユーザ名で引き、パスワードハッシュを照合する。成功なら、そのユーザの既存セッションを削除して新しいセッションを作り、Cookie に載せる。失敗（ユーザなし、論理削除、パスワード不一致）は同じ応答にする。

エラー:

| 状況 | 応答 |
|------|------|
| `username` または `password` が無い／空 | 400 |
| 認証に失敗 | 401、本文 `{ "detail": "ログインできませんでした" }` |

### POST `/auth/logout`

- 認証: 要
- 対応 REQ: REQ-008

要求: なし

応答: 204。本文なし。`Set-Cookie` で `session_id` を削除する。

処理概要: 当該セッション行を削除する。Cookie を無効にする。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |

### GET `/auth/session`

- 認証: 要
- 対応 REQ: REQ-003, REQ-009

要求: なし

応答: 200

```json
{
  "username": "string"
}
```

処理概要: ログイン中ならユーザ名を返す。フロントは `/` の誘導と、メニュー要求前の確認に使う。セッション ID は返さない。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |

### GET `/settings`

- 認証: 不要
- 対応 REQ: REQ-004, REQ-005

要求: なし

応答: 200

```json
{
  "login_url": "string",
  "menu_url": "string",
  "icon_system": "string",
  "icon_settings": "string",
  "icon_back": "string"
}
```

`icon_*` は data URL。ログイン画面のヘッダが `icon_system` を使うため、未ログインでも取得できる。

処理概要: システム設定の必須キー 5 件を返す。

エラー:

| 状況 | 応答 |
|------|------|
| 必須キーが欠けている | 500 |

### GET `/menu`

- 認証: 要
- 対応 REQ: REQ-005, REQ-012, REQ-013

要求: なし

応答: 200

```json
{
  "items": [
    {
      "id": "string",
      "title": "string",
      "url": "string",
      "icon": "string"
    }
  ]
}
```

`items` は表示順。`icon` は data URL。アイコンが無いときは空文字列。割当が無ければ `items` は空配列。他ユーザの割当は含まない。論理削除済みの機能は含まない。

処理概要: ログイン中ユーザの有効な割当だけを、表示順（同順なら機能 ID）で返す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | POST `/auth/login` |
| REQ-002 | POST `/auth/login`（論理削除ユーザは失敗）。運用コマンドは API 対象外 |
| REQ-003 | GET `/auth/session`、Cookie |
| REQ-004 | GET `/settings` |
| REQ-005 | GET `/settings`、GET `/menu` の data URL |
| REQ-006 | POST `/auth/login` |
| REQ-007 | POST `/auth/login` の 401 |
| REQ-008 | POST `/auth/logout` |
| REQ-009 | GET `/auth/session`、GET `/menu` の 401 |
| REQ-010 | API 対象外（運用コマンド） |
| REQ-011 | API 対象外（運用コマンド） |
| REQ-012 | GET `/menu` |
| REQ-013 | GET `/menu` の `url` |
| REQ-014 | API 対象外（各機能が DB を参照） |
| REQ-015 | API 対象外（運用コマンド） |
| REQ-016 | API 対象外（運用コマンド） |
| REQ-017 | API 対象外（運用コマンド） |
| REQ-018 | API 対象外（運用コマンド） |
| REQ-019 | API 対象外（運用コマンド） |

## 未決事項

-

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-26 08:48 | 未承認 | 初版 |
| 2026-08-26 08:53 | 承認済み | 初版を承認 |
| 2026-08-26 23:40 | 未承認 | アイコンなしは空文字列 |
| 2026-08-26 23:45 | 承認済み | アイコンなしは空文字列とする改訂を承認 |
