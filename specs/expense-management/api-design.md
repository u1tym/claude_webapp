# expense-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_EXPENSE_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `expense-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

### 日時・数値の形式

- 日付: `YYYY-MM-DD`（日本標準時の年月日）
- 年月: `YYYY-MM`
- 日時: ISO 8601（`created_at` のみ。応答専用、要求では使わない）
- 金額: 小数点以下2桁までの数値を表す文字列（例: `"1500.00"`）。誤差を避けるため数値型ではなく文字列で表す
- `closing_day_shift_direction` / `payment_day_shift_direction`: `earlier`（過去）または `later`（未来）
- `exclusion_kind`: `sunday`、`monday`、`tuesday`、`wednesday`、`thursday`、`friday`、`saturday`、`nonexistent_day`
- 除外条件は `{ "exclusion_kind": "..." }` の配列で表す（締め日用・支払日用を別々の配列で持つ）

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、削除済み、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/budget-periods` | 要 | REQ-004 |
| POST | `/budget-periods` | 要 | REQ-001 |
| POST | `/budget-periods/{budget_period_id}/duplicate` | 要 | REQ-002 |
| GET | `/budget-items` | 要 | REQ-004 |
| POST | `/budget-items` | 要 | REQ-003 |
| PATCH | `/budget-items/{budget_item_id}` | 要 | REQ-003 |
| DELETE | `/budget-items/{budget_item_id}` | 要 | REQ-003 |
| GET | `/payment-methods` | 要 | REQ-007 |
| POST | `/payment-methods` | 要 | REQ-005 |
| PATCH | `/payment-methods/{payment_method_id}` | 要 | REQ-006 |
| DELETE | `/payment-methods/{payment_method_id}` | 要 | REQ-006 |
| GET | `/payment-methods/{payment_method_id}/estimated-payment-date` | 要 | REQ-013 |
| GET | `/expenses` | 要 | REQ-010 |
| POST | `/expenses` | 要 | REQ-008 |
| PATCH | `/expenses/{expense_id}` | 要 | REQ-009 |
| DELETE | `/expenses/{expense_id}` | 要 | REQ-009 |
| GET | `/reports/usage-date` | 要 | REQ-011 |
| GET | `/reports/payment-month` | 要 | REQ-012 |

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

`icon_*` は data URL。未ログイン時の誘導先（`login_url`）と、ヘッダの「戻る」（`menu_url`、システムアイコン・戻るアイコン表示）に使う。`public.system_settings` から取得する（`portal` が管理するデータを読むだけで、本機能は変更しない）。

処理概要: システム設定からログイン URL、メニュー URL、システムアイコン、戻るアイコンを返す。

エラー:

| 状況 | 応答 |
|------|------|
| 必須キーが欠けている | 500 |

### GET `/budget-periods`

対応 REQ: REQ-004

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 1, "title": "2026年9月分", "start_date": "2026-09-01", "end_date": "2026-09-30" }
  ]
}
```

`items` は本人の予算期間を `start_date` の新しい順に返す。0 件なら空配列。同一ユーザ内で期間が重なる予算期間も、それぞれ独立した行として返す。

処理概要: ログイン中ユーザの予算期間を一覧で返す。

### POST `/budget-periods`

対応 REQ: REQ-001

要求:

```json
{ "title": "2026年10月分", "start_date": "2026-10-01", "end_date": "2026-10-31" }
```

応答: 201

```json
{ "id": 2, "title": "2026年10月分", "start_date": "2026-10-01", "end_date": "2026-10-31" }
```

エラー:

| 状況 | 応答 |
|------|------|
| `title` が空、または `end_date` が `start_date` より前 | 400 |

処理概要: 予算期間を新規作成する。予算項目は作らない。同一ユーザの既存の予算期間と期間が重なっていても作成できる。

### POST `/budget-periods/{budget_period_id}/duplicate`

対応 REQ: REQ-002

要求:

```json
{ "title": "2026年10月分", "start_date": "2026-10-01", "end_date": "2026-10-31" }
```

応答: 201

```json
{
  "id": 3,
  "title": "2026年10月分",
  "start_date": "2026-10-01",
  "end_date": "2026-10-31",
  "budget_items": [
    { "id": 10, "name": "食費", "amount": "30000.00", "display_order": 1 }
  ]
}
```

処理概要: `budget_period_id` で指定した予算期間（本人の所有、未削除の予算項目のみ）を複製元として、要求の `title`・`start_date`・`end_date` で新しい予算期間を作成し、複製元の予算項目（項目名・金額・表示順）を新しい `id` でコピーする。

エラー:

| 状況 | 応答 |
|------|------|
| `title` が空、または `end_date` が `start_date` より前 | 400 |
| `budget_period_id` が本人の予算期間でない | 404 |

### GET `/budget-items`

対応 REQ: REQ-004

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `budget_period_id` | 必須 | 対象の予算期間 |

応答: 200

```json
{
  "items": [
    { "id": 10, "budget_period_id": 1, "name": "食費", "amount": "30000.00", "display_order": 1 }
  ]
}
```

`items` は `display_order` の昇順。削除済みは含まない。`budget_period_id` が本人の予算期間でないときは 404。

処理概要: 指定した予算期間に属する、本人の未削除の予算項目を返す。

### POST `/budget-items`

対応 REQ: REQ-003

要求:

```json
{ "budget_period_id": 1, "name": "食費", "amount": "30000.00", "display_order": 1 }
```

応答: 201

```json
{ "id": 10, "budget_period_id": 1, "name": "食費", "amount": "30000.00", "display_order": 1 }
```

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空、`amount` が負、`budget_period_id` が本人の予算期間でない | 400 |

処理概要: 指定した予算期間に予算項目を追加する。

### PATCH `/budget-items/{budget_item_id}`

対応 REQ: REQ-003

要求:

```json
{ "name": "食費", "amount": "32000.00", "display_order": 1 }
```

応答: 200（更新後の予算項目。形式は POST と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空、`amount` が負 | 400 |
| 本人の未削除の予算項目でない | 404 |

処理概要: 予算項目の項目名・金額・表示順を更新する。`budget_period_id` は変更できない。

### DELETE `/budget-items/{budget_item_id}`

対応 REQ: REQ-003

要求: なし

応答: 204

エラー:

| 状況 | 応答 |
|------|------|
| 本人の未削除の予算項目でない | 404 |

処理概要: 予算項目を論理削除する。既存の支出記録の `budget_item_id` は変えない。

### GET `/payment-methods`

対応 REQ: REQ-007

要求: なし

応答: 200

```json
{
  "items": [
    {
      "id": 1,
      "name": "クレジットカードA",
      "closing_day": 15,
      "closing_day_shift_direction": "earlier",
      "closing_day_exclusions": [{ "exclusion_kind": "sunday" }, { "exclusion_kind": "nonexistent_day" }],
      "payment_month_offset": 1,
      "payment_day": 10,
      "payment_day_shift_direction": "later",
      "payment_day_exclusions": [{ "exclusion_kind": "nonexistent_day" }],
      "display_order": 1
    }
  ]
}
```

`items` は本人の未削除の支出方法を `display_order` の昇順で返す。`closing_day = 0`（即時支払）の行は `closing_day_shift_direction`・`payment_day_shift_direction` が `null`、`closing_day_exclusions`・`payment_day_exclusions` が空配列、`payment_month_offset = 0`、`payment_day = 0`。

処理概要: 支出方法の一覧を返す。

### POST `/payment-methods`

対応 REQ: REQ-005

要求（`closing_day` が 1 以上の例）:

```json
{
  "name": "クレジットカードA",
  "closing_day": 15,
  "closing_day_shift_direction": "earlier",
  "closing_day_exclusions": [{ "exclusion_kind": "sunday" }],
  "payment_month_offset": 1,
  "payment_day": 10,
  "payment_day_shift_direction": "later",
  "payment_day_exclusions": [{ "exclusion_kind": "nonexistent_day" }],
  "display_order": 1
}
```

`closing_day = 0` のときは、`payment_month_offset` / `payment_day` / 両ずらし方向 / 両除外条件配列を省略できる（送っても無視し、固定値で登録する）。

応答: 201（登録内容。形式は GET `/payment-methods` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空、`closing_day` が 0〜31 の範囲外 | 400 |
| `closing_day` が1以上で、`payment_month_offset` / `payment_day` / いずれかのずらし方向が未指定、または `payment_day` が1〜31の範囲外 | 400 |

処理概要: 支出方法を登録する。`closing_day = 0` のときは支払月オフセット・支払日・ずらし方向・除外条件を即時支払を表す固定値にする。

### PATCH `/payment-methods/{payment_method_id}`

対応 REQ: REQ-006

要求: POST `/payment-methods` と同じ形式（全項目を送る）

応答: 200（更新後の内容。形式は GET `/payment-methods` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の未削除の支出方法でない | 404 |

処理概要: 支出方法を更新する。`closing_day` を 0 に変更したときは、支払月オフセット・支払日・ずらし方向を固定値にし、除外条件をすべて削除する。

### DELETE `/payment-methods/{payment_method_id}`

対応 REQ: REQ-006

要求: なし

応答: 204

エラー:

| 状況 | 応答 |
|------|------|
| 本人の未削除の支出方法でない | 404 |

処理概要: 支出方法を論理削除する。既存の支出記録の `payment_method_id` は変えない。

### GET `/payment-methods/{payment_method_id}/estimated-payment-date`

対応 REQ: REQ-013

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `usage_date` | 必須 | 利用日 |

応答: 200

```json
{ "payment_date": "2026-10-10" }
```

処理概要: 指定した支出方法と利用日から、実際の締め日・支払月オフセット・実際の支払日を用いて支払日を算出して返す。締め日が0の支出方法は利用日をそのまま返す。フロントは、支出記録フォームで利用日または支出方法が変わるたびにこの API を呼び、算出結果を支払日欄の初期値・再算出値として表示する。ユーザはその値を手入力で修正できる（REQ-008、REQ-009）。

エラー:

| 状況 | 応答 |
|------|------|
| `usage_date` が無い、日付でない | 400 |
| 本人の未削除の支出方法でない | 404 |

### GET `/expenses`

対応 REQ: REQ-010

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `start_date` | 必須 | 利用日の範囲開始 |
| `end_date` | 必須 | 利用日の範囲終了 |

応答: 200

```json
{
  "items": [
    {
      "id": 100,
      "usage_date": "2026-09-05",
      "budget_item_id": 10,
      "purpose": "ランチ代",
      "amount": "980.00",
      "payment_method_id": 1,
      "memo": null,
      "payment_date": "2026-10-10",
      "created_at": "2026-09-05T12:30:00+09:00"
    }
  ]
}
```

`items` は削除フラグが立っていない本人の支出記録を、利用日の新しい順に返す。`memo` が無いときは `null`。

処理概要: 指定した利用日の範囲に含まれる、削除されていない支出記録を返す。

エラー:

| 状況 | 応答 |
|------|------|
| クエリが無い、日付でない、`end_date` が `start_date` より前 | 400 |

### POST `/expenses`

対応 REQ: REQ-008

要求:

```json
{
  "usage_date": "2026-09-05",
  "budget_item_id": 10,
  "purpose": "ランチ代",
  "amount": "980.00",
  "payment_method_id": 1,
  "memo": null,
  "payment_date": "2026-10-10"
}
```

応答: 201（登録内容。形式は GET `/expenses` の `items` の要素と同じ。`created_at` はシステムが設定）

エラー:

| 状況 | 応答 |
|------|------|
| `purpose` が空、`amount` が負、必須項目が無い | 400 |
| `budget_item_id` が本人の未削除の予算項目でない | 400 |
| `payment_method_id` が本人の未削除の支出方法でない | 400 |

処理概要: 支出記録を登録する。`payment_date` はフロントが `GET /payment-methods/{id}/estimated-payment-date` で算出・表示した値（ユーザが修正した場合はその値）をそのまま受け取り保存する。`created_at` は現在時刻を自動設定する。

### PATCH `/expenses/{expense_id}`

対応 REQ: REQ-009

要求: POST `/expenses` と同じ形式（全項目を送る。`created_at` は送らない）

応答: 200（更新後の内容。形式は GET `/expenses` の `items` の要素と同じ）

エラー:

| 状況 | 応答 |
|------|------|
| POST と同じ入力検査 | 400 |
| 本人の削除されていない支出記録でない | 404 |

処理概要: 支出記録を更新する。`created_at` は変えない。

### DELETE `/expenses/{expense_id}`

対応 REQ: REQ-009

要求: なし

応答: 204

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない支出記録でない | 404 |

処理概要: 支出記録に削除フラグを立てる（論理削除）。

### GET `/reports/usage-date`

対応 REQ: REQ-011

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `budget_period_id` | 必須 | 集計対象の予算期間 |

応答: 200

```json
{
  "budget_period": { "id": 1, "title": "2026年9月分", "start_date": "2026-09-01", "end_date": "2026-09-30" },
  "items": [
    {
      "budget_item_id": 10,
      "name": "食費",
      "budget_amount": "30000.00",
      "actual_amount": "12500.00",
      "difference": "17500.00"
    }
  ]
}
```

`items` は当該予算期間に属する予算項目（表示順）ごとに、その予算項目を予算区分とする、利用日が当該予算期間内かつ削除フラグが立っていない支出記録の金額を合計する。`difference` は `budget_amount - actual_amount`。

処理概要: 予算期間を選択した利用日基準の予算対実績集計を返す。

エラー:

| 状況 | 応答 |
|------|------|
| `budget_period_id` が本人の予算期間でない | 404 |

### GET `/reports/payment-month`

対応 REQ: REQ-012

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `year_month` | 必須 | 集計対象の年月（`YYYY-MM`） |

応答: 200

```json
{
  "items": [
    { "budget_item_id": 10, "name": "食費", "actual_amount": "8000.00" }
  ]
}
```

`items` は、支払日の年月が `year_month` と一致し、削除フラグが立っていない本人の支出記録を、`budget_item_id` ごとに合計する。対象の予算項目（論理削除済みを含む）の名称を付す。金額が0より大きい予算項目のみを含む。

処理概要: 年月を選択した支払発生月基準の集計を返す。

エラー:

| 状況 | 応答 |
|------|------|
| `year_month` が無い、形式が不正 | 400 |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-18 | 未承認 | 初版 |
| 2026-09-18 | 承認済み | 初版を承認 |
| 2026-09-18 | 未承認 | design.md の「未ログインはログイン画面URLへ誘導、戻る先はメニュー画面URL」を実現するため、GET /settings（認証不要）を追加 |
| 2026-09-18 | 承認済み | GET /settings の追加を承認 |
| 2026-09-18 | 未承認 | 予算期間に `title` を追加。期間重複エラー（409）を撤廃 |
| 2026-09-18 | 承認済み | 予算期間の `title` 追加と期間重複エラー撤廃を承認 |
