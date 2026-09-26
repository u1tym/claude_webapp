# api-key-management（APIキー管理）API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

本書は次の 2 つの契約を定める。

1. 本機能の FastAPI が公開する HTTP API（API キーの発行・一覧・失効）。
2. 対象機能（`goods-management`、`expense-management`、`knowhow-management`、`schedule`）の API に共通で追加する、API キーによる認証の契約（「対象機能の API キー認証」の節）。対象機能のエンドポイント自体（パス・要求・応答）は変えない。

ログイン・ログアウトの API は持たない。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント: `requirements.md` / `design.md` / `ui-design.md` / `db-design.md`

## 共通事項

### ベース URL

`VITE_API_API_KEY_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）。開発時は `http://localhost:8010`。

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `api-key-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。
- **API キーによる認証は受け付けない。** `Authorization` ヘッダは無視し、Cookie（または `DEBUG_USER`）だけで判定する。したがって、API キーだけを添えた要求は未ログイン（401）になる。

GET `/settings` だけ認証不要。それ以外は認証要かつ本機能の割当要。他ユーザの API キーは対象なし（404）とする。存在しないことと区別しない。

### 日時の形式

- 日時: ISO 8601 のタイムゾーン付き（例: `2026-12-31T23:59:00+09:00`）。応答は UTC（`Z`）で返す。
- 要求の日時にタイムゾーンが無いときは、入力不正（400）とする。

### API キーの表し方

| 項目 | 形式 |
|------|------|
| `key` | キー全体。`wak_` + 43 文字（32 バイトの乱数を URL 安全な Base64 にし、末尾の `=` を除いたもの）。発行の応答にだけ含める |
| `key_prefix` | 識別用の先頭部分。`key` の先頭 12 文字 |
| `status` | `active`（有効）、`expired`（期限切れ）、`revoked`（失効済み）。判定の条件は `db-design.md` |

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の API キー、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 失効済みの API キーの失効 | 409、本文 `{ "detail": "既に失効しています" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

FastAPI の要求検証の失敗（型違い・必須欠落）も 400 で返す。失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 概要 | 対応 REQ |
|----------|------|------|------|----------|
| GET | `/settings` | 不要 | システム設定（ログイン URL、メニュー URL、共通アイコン） | REQ-001 |
| GET | `/api-keys` | 要 | 本人の API キーの一覧 | REQ-001、REQ-002、REQ-004、REQ-008 |
| POST | `/api-keys` | 要 | API キーの発行 | REQ-001、REQ-003、REQ-008 |
| POST | `/api-keys/{api_key_id}/revoke` | 要 | API キーの失効 | REQ-001、REQ-002、REQ-005、REQ-008 |

REQ-006・REQ-007 は、対象機能の API キー認証（後述）で満たす。本機能のエンドポイントは無い。

## エンドポイント詳細

### GET `/settings`

- **認証**: 不要
- **要求**: なし
- **応答（200）**

```json
{
  "login_url": "http://localhost:5173/portal/login",
  "menu_url": "http://localhost:5173/portal/menu",
  "icon_system": "data:image/png;base64,....",
  "icon_back": "data:image/png;base64,...."
}
```

`icon_*` は `data:{media_type};base64,{payload}` の data URL。未ログイン時の誘導と、ヘッダの戻るに使う。

- **エラー**

| HTTP ステータス | 条件 |
|------|------|
| 500 | システム設定に必須キー（`login_url`、`menu_url`、`icon_system`、`icon_back`）が欠けている |

### GET `/api-keys`

- **認証**: 要
- **要求**: なし
- **応答（200）**

発行日時（`created_at`）の新しい順。失効済みを含む全件。キー全体（`key`）とハッシュは含めない。

```json
{
  "items": [
    {
      "id": 12,
      "name": "家計簿連携",
      "key_prefix": "wak_Ab3dEf7h",
      "status": "active",
      "created_at": "2026-09-26T00:00:00Z",
      "expires_at": "2027-03-31T14:59:00Z",
      "last_used_at": null,
      "revoked_at": null
    }
  ]
}
```

| 項目 | 型 | 説明 |
|------|----|------|
| `id` | integer | API キーの識別子 |
| `name` | string | 名前 |
| `key_prefix` | string | 識別用の先頭部分 |
| `status` | string | `active` / `expired` / `revoked` |
| `created_at` | string | 発行日時 |
| `expires_at` | string \| null | 有効期限。null は無期限 |
| `last_used_at` | string \| null | 最終利用日時。null は未使用 |
| `revoked_at` | string \| null | 失効日時。null は未失効 |

- **エラー**: 共通（401、403、500）

### POST `/api-keys`

- **認証**: 要
- **要求**（JSON）

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | 名前。前後の空白を除いて 1〜100 文字 |
| `expires_at` | string \| null | 任意 | 有効期限（タイムゾーン付き ISO 8601）。省略または null で無期限。現在より後であること |

```json
{
  "name": "家計簿連携",
  "expires_at": "2027-03-31T23:59:00+09:00"
}
```

- **応答（201）**

キー全体（`key`）は、この応答にだけ含める。

```json
{
  "id": 12,
  "name": "家計簿連携",
  "key": "wak_Ab3dEf7hIjKlMnOpQrStUvWxYz0123456789-_AbCdEfG",
  "key_prefix": "wak_Ab3dEf7h",
  "status": "active",
  "created_at": "2026-09-26T00:00:00Z",
  "expires_at": "2027-03-31T14:59:00Z",
  "last_used_at": null,
  "revoked_at": null
}
```

- **エラー**

| HTTP ステータス | 条件 |
|------|------|
| 400 | `name` が無い・文字列でない・前後の空白を除いて空・100 文字を超える |
| 400 | `expires_at` の形式が不正、タイムゾーンが無い、現在以前 |
| 401 / 403 / 500 | 共通 |

キーのハッシュが既存と重複したときは、サーバ内で生成し直す（応答には現れない）。

### POST `/api-keys/{api_key_id}/revoke`

- **認証**: 要
- **要求**

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `api_key_id`（パス） | integer | 必須 | 失効する API キーの識別子 |

本文なし。

- **応答（200）**

失効後の API キー（一覧の 1 件と同じ形。`key` は含めない）。

```json
{
  "id": 12,
  "name": "家計簿連携",
  "key_prefix": "wak_Ab3dEf7h",
  "status": "revoked",
  "created_at": "2026-09-26T00:00:00Z",
  "expires_at": "2027-03-31T14:59:00Z",
  "last_used_at": "2026-09-27T01:23:45Z",
  "revoked_at": "2026-09-28T09:00:00Z"
}
```

- **エラー**

| HTTP ステータス | 条件 |
|------|------|
| 400 | `api_key_id` が整数でない |
| 404 | 存在しない、または他人の API キー |
| 409 | 既に失効済み |
| 401 / 403 / 500 | 共通 |

期限切れ（未失効）の API キーは失効できる（200）。

## 対象機能の API キー認証

対象機能（`goods-management`、`expense-management`、`knowhow-management`、`schedule`）の、認証を要する全エンドポイントに共通で適用する。各対象機能の `api-design.md` の「認証」節に、本節と同じ内容を追記する（改訂時）。

### 要求

| ヘッダ | 値 | 説明 |
|--------|----|------|
| `Authorization` | `Bearer <キー全体>` | API キー。スキーム名 `Bearer` は大文字小文字を区別しない。キーの前後の空白は除く |

- API キーは URL（クエリ・パス）では受け取らない。
- 他システムは Cookie を送らなくてよい。

例:

```
GET /goods HTTP/1.1
Host: api.example.com
Authorization: Bearer wak_Ab3dEf7hIjKlMnOpQrStUvWxYz0123456789-_AbCdEfG
```

### 判定

| 条件 | 結果 |
|------|------|
| `Authorization` ヘッダが無い | 従来どおり `DEBUG_USER`・Cookie で判定する |
| `Authorization` ヘッダがあるが、`Bearer` 方式でない、またはキーが空 | 401 |
| キーのハッシュに一致する API キーが無い | 401 |
| 失効済み | 401 |
| 有効期限切れ | 401 |
| 持ち主が論理削除済み | 401 |
| 持ち主に当該機能が割り当てられていない、または当該機能が論理削除済み | 403 |
| 上記以外 | 許可。持ち主をログイン中ユーザとして処理し、`last_used_at` を更新する |

- `Authorization` ヘッダがあるときは、判定に失敗しても Cookie・`DEBUG_USER` での判定に戻らない。
- API キーで許可した要求では、セッションの有効期限の延長をしない。
- 認証不要の GET `/settings` は、`Authorization` ヘッダがあっても判定せずに応答する（従来どおり）。

### 応答

- 許可したときの応答は、Cookie で利用したときと同じ（各対象機能の `api-design.md` のとおり）。
- 401・403 の本文は、各対象機能の共通エラーと同じ（`{ "detail": "未ログイン" }`、`{ "detail": "権限がありません" }`）。401 の理由（該当なし・失効済み・期限切れ・ユーザ削除済み）は本文で区別しない。内部理由はログにだけ残す。
- API キーによる判定で 401 を返すときは、ヘッダ `WWW-Authenticate: Bearer` を付ける。

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-26 00:41 | 未承認 | 初版 |
| 2026-09-26 00:42 | 承認済み | 初版を承認 |
