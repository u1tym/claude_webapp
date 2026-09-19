# password-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_PASSWORD_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `password-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

### 一覧・検索応答からのパスワード除外について

一覧・検索（GET `/passwords`）の応答にはパスワード（`psword`）を含めない。パスワードは、単件取得（GET `/passwords/{id}`）・登録（POST）・更新（PATCH）の応答にだけ含める。一覧はタイトルとユーザ名だけを表示するため（`ui-design.md`）、不要な経路でパスワードの値を送信しないようにする。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、削除済み、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| タイトルが重複 | 409、本文 `{ "detail": "保存できませんでした" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/passwords` | 要 | REQ-006 |
| GET | `/passwords/{id}` | 要 | REQ-007 |
| POST | `/passwords` | 要 | REQ-003 |
| PATCH | `/passwords/{id}` | 要 | REQ-004 |
| DELETE | `/passwords/{id}` | 要 | REQ-005 |

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

### GET `/passwords`

対応 REQ: REQ-006

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `keyword` | 任意 | 検索キーワード。タイトル・ユーザ名・サイトURL・メモのいずれかに大文字小文字を区別しない部分一致で絞り込む。無い、または空・空白のみのときは全件を返す |

応答: 200

```json
{
  "total": 2,
  "items": [
    {
      "id": 10,
      "title": "Googleアカウント",
      "userword": "user@example.com",
      "site": "https://accounts.google.com",
      "memo": "メインアカウント"
    }
  ]
}
```

`items` は削除フラグが立っていない、本人のパスワードエントリを登録順（ID昇順）で返す。`site` / `memo` が無いときは `null`。`psword` は含めない。

処理概要: ログイン中ユーザ本人の、削除されていないパスワードエントリを一覧・検索する。

エラー: 共通エラーのみ。

### GET `/passwords/{id}`

対応 REQ: REQ-007

要求: なし

応答: 200

```json
{
  "id": 10,
  "title": "Googleアカウント",
  "userword": "user@example.com",
  "psword": "MyP@ssword123",
  "site": "https://accounts.google.com",
  "memo": "メインアカウント"
}
```

処理概要: ログイン中ユーザ本人の、指定 ID のパスワードエントリを取得する（詳細表示に使う。パスワードを含む）。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていないパスワードエントリでない | 404 |

### POST `/passwords`

対応 REQ: REQ-003

要求:

```json
{
  "title": "Googleアカウント",
  "userword": "user@example.com",
  "psword": "MyP@ssword123",
  "site": "https://accounts.google.com",
  "memo": "メインアカウント"
}
```

| フィールド | 型 | 必須 | 説明 |
|------------|----|----|------|
| `title` | string | 要 | 空・空白のみ不可 |
| `userword` | string | 要 | 空・空白のみ不可 |
| `psword` | string | 要 | 空文字不可。空白のみ・複数行は可 |
| `site` | string \| null | 否 | 省略時は `null` |
| `memo` | string \| null | 否 | 省略時は `null` |

応答: 201（登録内容。形式は GET `/passwords/{id}` の応答と同じ。`id` はシステムが採番）

エラー:

| 状況 | 応答 |
|------|------|
| `title` / `userword` が空・空白のみ、`psword` が空、必須項目が無い | 400 |
| `title` が、本人の削除されていないパスワードエントリと重複する | 409 |

処理概要: パスワードエントリを登録する。`title` / `userword` はトリムして保存する。

### PATCH `/passwords/{id}`

対応 REQ: REQ-004

要求: POST `/passwords` と同じ形式（全項目を送る）

応答: 200（更新後の内容。形式は GET `/passwords/{id}` の応答と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の削除されていないパスワードエントリでない | 404 |
| 更新後の `title` が、自エントリ以外の本人の削除されていないパスワードエントリと重複する | 409 |

処理概要: パスワードエントリを更新する（タイトルの変更を含む）。

### DELETE `/passwords/{id}`

対応 REQ: REQ-005

要求: なし

応答: 204。本文なし。

処理概要: パスワードエントリを論理削除する。削除後、一覧・検索・単件取得の対象外になる。同じタイトルで新たに登録できる。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていないパスワードエントリでない | 404 |

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通の認証・権限エラー |
| REQ-002 | 全エンドポイントの本人絞り込み（404 で他人の行を隠す） |
| REQ-003 | POST `/passwords` |
| REQ-004 | PATCH `/passwords/{id}` |
| REQ-005 | DELETE `/passwords/{id}` |
| REQ-006 | GET `/passwords` |
| REQ-007 | GET `/passwords/{id}` |
| REQ-008 | エンドポイント対象外（ログ） |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 01:15 | 未承認 | 初版 |
| 2026-09-20 01:16 | 承認済み | 初版を承認 |
