# API設計: schedule（スケジュール管理）

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
- ログイン中でも、識別子 `schedule` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外は認証要かつ本機能の割当要。他ユーザの行は対象なし（404）とする。存在しないことと区別しない。

### 日時の形式

- 日付: `YYYY-MM-DD`（日本標準時の年月日）
- 時刻: `HH:MM`（24 時間。秒は付けない）
- `kind` は `event`（予定）または `todo`（TODO）
- `granularity` は `day`（日単位）または `time`（時間単位）
- `week_starts_on` は `sunday` または `monday`
- `occurrence_type` は `date`（日付指定）または `weekday`（曜日指定）
- `date_rule` は `last_day`（月末日）または `day_of_month`（毎月 X 日）
- `weekday_rule` は `nth`（N 番目）または `nth_from_last`（最終から N 番目）
- `weekday` は `sunday`〜`saturday`
- `shift_direction` は `earlier`（前）または `later`（後）
- `exclusion_kind` は `holiday`、`sunday`、`monday`、`tuesday`、`wednesday`、`thursday`、`friday`、`saturday`
- `needs_notification` は `true`（要）または `false`（不要）
- 色は `#` に続く 16 進 6 桁（例: `#4DA3FF`）

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし | 404、本文 `{ "detail": "対象がありません" }` |
| 保存の失敗（重複など） | 409、本文 `{ "detail": "保存できませんでした" }` |
| 削除の失敗 | 409、本文 `{ "detail": "削除できませんでした" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | REQ-001 |
| GET | `/schedules` | 要 | REQ-002, REQ-019, REQ-020 |
| POST | `/schedules` | 要 | REQ-007 |
| PATCH | `/schedules/{schedule_id}` | 要 | REQ-008 |
| PATCH | `/schedules/{schedule_id}/completion` | 要 | REQ-010 |
| DELETE | `/schedules/{schedule_id}` | 要 | REQ-009 |
| GET | `/categories` | 要 | REQ-011 |
| POST | `/categories` | 要 | REQ-011 |
| PATCH | `/categories/{category_id}` | 要 | REQ-012 |
| DELETE | `/categories/{category_id}` | 要 | REQ-013 |
| GET | `/preferences` | 要 | REQ-014, REQ-015, REQ-017 |
| PUT | `/preferences` | 要 | REQ-014, REQ-015, REQ-017 |
| GET | `/holidays` | 要 | REQ-018 |
| GET | `/user-holidays` | 要 | REQ-028 |
| POST | `/user-holidays` | 要 | REQ-028 |
| PATCH | `/user-holidays/{user_holiday_id}` | 要 | REQ-029 |
| DELETE | `/user-holidays/{user_holiday_id}` | 要 | REQ-030 |
| GET | `/routines` | 要 | REQ-031, REQ-032, REQ-035 |
| POST | `/routines` | 要 | REQ-033 |
| PATCH | `/routines/{routine_id}` | 要 | REQ-040 |
| DELETE | `/routines/{routine_id}` | 要 | REQ-034 |
| POST | `/routines/{routine_id}/apply` | 要 | REQ-036, REQ-038, REQ-039 |
| POST | `/routines/apply-all` | 要 | REQ-037, REQ-038, REQ-039 |

REQ-003〜REQ-006、REQ-016、REQ-021〜REQ-026、REQ-035 の画面配置は画面側。REQ-027 は各操作 API のログであり、専用エンドポイントは無い。

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

### GET `/schedules`

- 認証: 要
- 対応 REQ: REQ-002, REQ-019, REQ-020

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `start_date` | 必須 | 範囲の開始日 |
| `end_date` | 必須 | 範囲の終了日 |

応答: 200

```json
{
  "items": [
    {
      "id": 1,
      "title": "string",
      "location": "string",
      "detail": "string",
      "kind": "event",
      "granularity": "day",
      "start_date": "2026-08-01",
      "end_date": "2026-08-01",
      "start_time": null,
      "end_time": null,
      "category_id": 1,
      "is_completed": null,
      "routine_id": null,
      "needs_notification": false
    }
  ]
}
```

`location` と `detail` は無いとき `null`。日単位のとき `start_time` と `end_time` は `null`。予定のとき `is_completed` は `null`。TODO のとき `true` または `false`。`routine_id` は手入力なら `null`。適用で作ったものはルーチンの `id`。`needs_notification` は要なら `true`、不要なら `false`。

`items` は REQ-019 の順。範囲に重なる本人の未削除だけ。カテゴリの表示／非表示では落とさない。0 件なら空配列。

処理概要: 指定期間に重なる本人の未削除スケジュールを返す。

エラー:

| 状況 | 応答 |
|------|------|
| クエリが無い、日付でない、または `end_date` が `start_date` より前 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/schedules`

- 認証: 要
- 対応 REQ: REQ-007

要求:

```json
{
  "title": "string",
  "location": "string",
  "detail": "string",
  "kind": "todo",
  "granularity": "time",
  "start_date": "2026-08-27",
  "end_date": "2026-08-27",
  "start_time": "09:00",
  "end_time": "10:00",
  "category_id": 1,
  "needs_notification": false
}
```

`location` と `detail` は省略可。空または省略なら `null` として保存する。日単位のとき `start_time` と `end_time` は省略するか `null`。時間単位のときは必須。`needs_notification` は必須。要なら `true`、不要なら `false`。`is_completed` は受け付けない。TODO は未実施で作る。`routine_id` は受け付けない。常に無しで作る。

応答: 201。GET 一件と同じ形。

処理概要: 操作中ユーザのスケジュールとして追加する。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い／空、粒度と時刻の組合せが不正、終了が開始より前、`needs_notification` が無いまたは真偽でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| カテゴリが無い／論理削除済み／他ユーザ | 404 |

### PATCH `/schedules/{schedule_id}`

- 認証: 要
- 対応 REQ: REQ-008

要求: POST と同じ項目。すべて必須（`location` と `detail` は空可）。`needs_notification` は必須。`kind` を予定から TODO にするときは未実施にする。TODO から予定にするときは実施状態を捨てる。更新時の `is_completed` は受け付けない（実施状態は completion で変える。種別変更に伴う未実施化は本 API が行う）。`routine_id` は受け付けない。既存の値は変えない。

応答: 200。GET 一件と同じ形。

処理概要: 本人の未削除スケジュールを更新する。カテゴリは本人の未削除だけを指定できる。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い／空、粒度と時刻の組合せが不正、終了が開始より前、`needs_notification` が無いまたは真偽でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| スケジュールまたは指定カテゴリが無い／論理削除済み／他ユーザ | 404 |

### PATCH `/schedules/{schedule_id}/completion`

- 認証: 要
- 対応 REQ: REQ-010

要求:

```json
{
  "is_completed": true
}
```

応答: 200。GET 一件と同じ形。

処理概要: 本人の未削除 TODO の実施状態だけを更新する。

エラー:

| 状況 | 応答 |
|------|------|
| `is_completed` が無い、または真偽でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、論理削除済み、他ユーザ | 404 |
| 予定に対する実施状態変更 | 409、保存できませんでした |

### DELETE `/schedules/{schedule_id}`

- 認証: 要
- 対応 REQ: REQ-009

要求: なし

応答: 204。本文なし。

処理概要: 本人の未削除スケジュールを論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、既に論理削除済み、他ユーザ | 404 |

### GET `/categories`

- 認証: 要
- 対応 REQ: REQ-011

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `include_deleted` | 任意 | `true` のとき削除済みも含める。省略時は未削除のみ |

応答: 200

```json
{
  "items": [
    {
      "id": 1,
      "name": "string",
      "color": "#4DA3FF",
      "is_deleted": false
    }
  ]
}
```

本人分のみ。並びは名称の昇順。0 件なら空配列。

処理概要: 本人のカテゴリを返す。

エラー:

| 状況 | 応答 |
|------|------|
| `include_deleted` が真偽として解釈できない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/categories`

- 認証: 要
- 対応 REQ: REQ-011

要求:

```json
{
  "name": "string",
  "color": "#4DA3FF"
}
```

応答: 201。GET 一件と同じ形（`is_deleted` は `false`）。

処理概要: 本人のカテゴリを追加する。

エラー:

| 状況 | 応答 |
|------|------|
| `name` が無い／空、または `color` の形式が不正 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 同一ユーザの未削除で名称が重複 | 409、保存できませんでした |

### PATCH `/categories/{category_id}`

- 認証: 要
- 対応 REQ: REQ-012

要求:

```json
{
  "name": "string",
  "color": "#4DA3FF"
}
```

応答: 200。GET 一件と同じ形。

処理概要: 本人の未削除カテゴリの名称と色を更新する。

エラー:

| 状況 | 応答 |
|------|------|
| `name` が無い／空、または `color` の形式が不正 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、論理削除済み、他ユーザ | 404 |
| 同一ユーザの別の未削除と名称が重複 | 409、保存できませんでした |

### DELETE `/categories/{category_id}`

- 認証: 要
- 対応 REQ: REQ-013

要求: なし

応答: 204。本文なし。

処理概要: 本人の未削除カテゴリを論理削除する。紐づくスケジュールとルーチンの `category_id` は変えない。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、既に論理削除済み、他ユーザ | 404 |

### GET `/preferences`

- 認証: 要
- 対応 REQ: REQ-014, REQ-015, REQ-017

要求: なし

応答: 200

```json
{
  "week_starts_on": "sunday",
  "show_deleted": false,
  "hidden_category_ids": [1]
}
```

行が無いときは初期値（`week_starts_on` は `sunday`、`show_deleted` は `false`、`hidden_category_ids` は空配列）。

処理概要: 本人の表示設定を返す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### PUT `/preferences`

- 認証: 要
- 対応 REQ: REQ-014, REQ-015, REQ-017

要求:

```json
{
  "week_starts_on": "monday",
  "show_deleted": true,
  "hidden_category_ids": [1, 2]
}
```

`hidden_category_ids` は非表示にするカテゴリの ID。空配列はすべて表示。本人のカテゴリ以外の ID は入力不正。

応答: 200。GET と同じ形。

処理概要: 本人の表示設定を保存する。行が無ければ作る。非表示の集合は要求の配列で置き換える。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、`week_starts_on` が不正、配列でない、または他ユーザ／存在しないカテゴリ ID | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### GET `/holidays`

- 認証: 要
- 対応 REQ: REQ-018

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `start_date` | 必須 | 範囲の開始日 |
| `end_date` | 必須 | 範囲の終了日 |

応答: 200

```json
{
  "items": [
    {
      "date": "2026-01-01",
      "name": "元日"
    }
  ]
}
```

日本の国民の祝日と振替休日。日付の昇順。0 件なら空配列。外部の祝日 API は呼ばない。本機能のバックエンドで算出する。

処理概要: 指定期間の日本の祝日を返す。

エラー:

| 状況 | 応答 |
|------|------|
| クエリが無い、日付でない、または `end_date` が `start_date` より前 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### GET `/user-holidays`

- 認証: 要
- 対応 REQ: REQ-028

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `start_date` | 任意 | 付けたときは範囲の開始日 |
| `end_date` | 任意 | 付けたときは範囲の終了日 |

両方付けるか、両方省略する。片方だけは入力不正。省略時は本人の未削除をすべて返す。

応答: 200

```json
{
  "items": [
    {
      "id": 1,
      "holiday_date": "2026-08-15",
      "name": "string"
    }
  ]
}
```

本人の未削除のみ。`holiday_date` の昇順。0 件なら空配列。

処理概要: 本人のユーザ休日を返す。

エラー:

| 状況 | 応答 |
|------|------|
| 日付でない、片方だけ指定、または範囲の終了が開始より前 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/user-holidays`

- 認証: 要
- 対応 REQ: REQ-028

要求:

```json
{
  "holiday_date": "2026-08-15",
  "name": "string"
}
```

応答: 201。GET 一件と同じ形。

処理概要: 本人のユーザ休日を追加する。

エラー:

| 状況 | 応答 |
|------|------|
| `holiday_date` が無い／日付でない、または `name` が無い／空 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 同一ユーザの未削除で年月日が重複 | 409、保存できませんでした |

### PATCH `/user-holidays/{user_holiday_id}`

- 認証: 要
- 対応 REQ: REQ-029

要求:

```json
{
  "holiday_date": "2026-08-16",
  "name": "string"
}
```

応答: 200。GET 一件と同じ形。

処理概要: 本人の未削除ユーザ休日の年月日と名称を更新する。

エラー:

| 状況 | 応答 |
|------|------|
| `holiday_date` が無い／日付でない、または `name` が無い／空 | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、論理削除済み、他ユーザ | 404 |
| 同一ユーザの別の未削除と年月日が重複 | 409、保存できませんでした |

### DELETE `/user-holidays/{user_holiday_id}`

- 認証: 要
- 対応 REQ: REQ-030

要求: なし

応答: 204。本文なし。

処理概要: 本人の未削除ユーザ休日を論理削除する。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、既に論理削除済み、他ユーザ | 404 |

### GET `/routines`

- 認証: 要
- 対応 REQ: REQ-031, REQ-032, REQ-035

要求: なし

応答: 200

```json
{
  "items": [
    {
      "id": 1,
      "title": "string",
      "detail": "string",
      "kind": "event",
      "category_id": 1,
      "occurrence_type": "date",
      "date_rule": "last_day",
      "day_of_month": null,
      "weekday_rule": null,
      "weekday_n": null,
      "weekday": null,
      "adjust_excluded": false,
      "shift_direction": null,
      "needs_notification": false,
      "months": [1, 4, 7, 10],
      "exclusions": ["holiday", "sunday"]
    }
  ]
}
```

本人の未削除のみ。`title` の昇順、同じなら `id` の昇順。0 件なら空配列。`detail` は無いとき `null`。日付指定のとき `weekday_rule` / `weekday_n` / `weekday` は `null`。`date_rule` が `last_day` のとき `day_of_month` は `null`。曜日指定のとき `date_rule` / `day_of_month` は `null`。除外調整が無のとき `shift_direction` は `null`、`exclusions` は空配列。`months` は 1〜12 の配列（重複なし、昇順）。`needs_notification` は要なら `true`、不要なら `false`。

処理概要: 本人の未削除ルーチンを返す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/routines`

- 認証: 要
- 対応 REQ: REQ-033

要求:

```json
{
  "title": "string",
  "detail": "string",
  "kind": "event",
  "category_id": 1,
  "occurrence_type": "date",
  "date_rule": "day_of_month",
  "day_of_month": 15,
  "weekday_rule": null,
  "weekday_n": null,
  "weekday": null,
  "adjust_excluded": true,
  "shift_direction": "earlier",
  "needs_notification": false,
  "months": [1, 4, 7, 10],
  "exclusions": ["holiday", "sunday"]
}
```

`detail` は省略可。空または省略なら `null`。日付指定のとき `date_rule` は必須。`last_day` なら `day_of_month` は省略または `null`。`day_of_month` なら 1〜31。曜日の項目は省略または `null`。曜日指定のとき `weekday_rule`、`weekday_n`（1〜5）、`weekday` は必須。日付の項目は省略または `null`。`months` は 1〜12 を 1 件以上（重複不可）。除外調整が無のとき `shift_direction` は省略または `null`、`exclusions` は省略または空配列。有のとき `shift_direction` は必須、`exclusions` は 1 件以上。`needs_notification` は必須。要なら `true`、不要なら `false`。

応答: 201。GET 一件と同じ形。

処理概要: 操作中ユーザのルーチンとして追加する。識別はサーバが付与する。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い／空、適用日タイプと項目の組合せが不正、`months` が 0 件または範囲外、除外調整が有なのに除外 0 件またはずらしかたが無い、`needs_notification` が無いまたは真偽でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| カテゴリが無い／論理削除済み／他ユーザ | 404 |

### PATCH `/routines/{routine_id}`

- 認証: 要
- 対応 REQ: REQ-040

要求: POST `/routines` と同じ形。

応答: 200。GET 一件と同じ形。

処理概要: 本人の未削除ルーチンの項目を更新する。反映月と除外対象は置き換える。紐づくスケジュールは変えない。`routine_id`（識別）は変えない。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い／空、適用日タイプと項目の組合せが不正、`months` が 0 件または範囲外、除外調整が有なのに除外 0 件またはずらしかたが無い、`needs_notification` が無いまたは真偽でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、既に論理削除済み、他ユーザ | 404 |
| カテゴリが無い／論理削除済み／他ユーザ | 404 |

### DELETE `/routines/{routine_id}`

- 認証: 要
- 対応 REQ: REQ-034

要求: なし

応答: 204。本文なし。

処理概要: 本人の未削除ルーチンを論理削除する。紐づくスケジュールの `routine_id` は変えない。反映月と除外対象の行は残す。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |
| 対象なし、既に論理削除済み、他ユーザ | 404 |

### POST `/routines/{routine_id}/apply`

- 認証: 要
- 対応 REQ: REQ-036, REQ-038, REQ-039

要求:

```json
{
  "year": 2026,
  "month": 8
}
```

`year` は西暦。`month` は 1〜12。

応答: 200

```json
{
  "items": [
    {
      "id": 10,
      "title": "string",
      "location": null,
      "detail": "string",
      "kind": "event",
      "granularity": "day",
      "start_date": "2026-08-15",
      "end_date": "2026-08-15",
      "start_time": null,
      "end_time": null,
      "category_id": 1,
      "is_completed": null,
      "routine_id": 1,
      "needs_notification": false
    }
  ]
}
```

作ったスケジュールは GET `/schedules` 一件と同じ形。日単位。開始と終了は適用日。場所は `null`。TODO なら `is_completed` は `false`。`routine_id` は当該ルーチンの `id`。`needs_notification` はルーチンの値。登録しなかったときは `items` は空配列（200 のまま）。

処理概要: 指定年月に当該ルーチンを適用する。反映月に含まれない、指定年月に同一 `routine_id` の未削除がある、基準日または適用日を決められない、カテゴリが論理削除済みまたは本人のものでない、ときは登録しない。失敗にはしない。基準日・適用日の決め方は `design.md`。

エラー:

| 状況 | 応答 |
|------|------|
| `year` / `month` が無い、整数でない、または `month` が 1〜12 でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |
| ルーチンが無い／論理削除済み／他ユーザ | 404 |

### POST `/routines/apply-all`

- 認証: 要
- 対応 REQ: REQ-037, REQ-038, REQ-039

要求: POST `/routines/{routine_id}/apply` と同じ（`year` と `month`）。

応答: 200。形は 1 件適用と同じ。`items` は今回作ったスケジュールをすべて含む。0 件なら空配列。並びは REQ-019。

処理概要: 本人の未削除ルーチンのそれぞれについて、1 件適用と同じ規則で指定年月へ適用する。ある件が登録しなくても他件を続ける。

エラー:

| 状況 | 応答 |
|------|------|
| `year` / `month` が無い、整数でない、または `month` が 1〜12 でない | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通の認証。GET `/settings`。各操作 API の 401 / 403 |
| REQ-002 | 各 GET が本人分のみ。他ユーザは 404 |
| REQ-003 | POST/PATCH `/schedules` の `kind` と `is_completed` |
| REQ-004 | スケジュールの要求・応答項目。`routine_id` は応答のみ。`needs_notification` は要／不要 |
| REQ-005 | `granularity` と日付／時刻 |
| REQ-006 | 終了が開始より前は 400 |
| REQ-007 | POST `/schedules`。`routine_id` は受け付けない。`needs_notification` は必須 |
| REQ-008 | PATCH `/schedules/{schedule_id}`。`routine_id` は変えない。`needs_notification` は変えられる |
| REQ-009 | DELETE `/schedules/{schedule_id}` |
| REQ-010 | PATCH `/schedules/{schedule_id}/completion` |
| REQ-011 | GET/POST `/categories` |
| REQ-012 | PATCH `/categories/{category_id}` |
| REQ-013 | DELETE `/categories/{category_id}` |
| REQ-014 | GET/PUT `/preferences` の `show_deleted` |
| REQ-015 | GET/PUT `/preferences` の `hidden_category_ids` |
| REQ-016 | エンドポイントなし（画面状態） |
| REQ-017 | GET/PUT `/preferences` の `week_starts_on` |
| REQ-018 | GET `/holidays` |
| REQ-019 | GET `/schedules` の並び |
| REQ-020 | GET `/schedules` の期間重なり |
| REQ-021〜REQ-026 | エンドポイントなし（画面） |
| REQ-027 | 各操作 API のログ（専用パスなし） |
| REQ-028 | GET/POST `/user-holidays` |
| REQ-029 | PATCH `/user-holidays/{user_holiday_id}` |
| REQ-030 | DELETE `/user-holidays/{user_holiday_id}` |
| REQ-031 | GET/POST `/routines` の `id` |
| REQ-032 | GET/POST/PATCH `/routines` の項目。`needs_notification` を含む |
| REQ-033 | POST `/routines` |
| REQ-034 | DELETE `/routines/{routine_id}` |
| REQ-035 | GET `/routines`。画面配置は `ui-design.md` |
| REQ-036 | POST `/routines/{routine_id}/apply`。`needs_notification` はルーチンの値 |
| REQ-037 | POST `/routines/apply-all` |
| REQ-038 | 適用 API の基準日算出（専用パスなし） |
| REQ-039 | 適用 API の除外調整（専用パスなし） |
| REQ-040 | PATCH `/routines/{routine_id}` |

## 未決事項

- なし

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-27 21:55 | 未承認 | 初版 |
| 2026-08-27 22:00 | 承認済み | 初版を承認 |
| 2026-08-29 23:41 | 未承認 | ルーチンの一覧・追加・削除・適用 API。スケジュール応答に `routine_id` |
| 2026-08-29 23:46 | 承認済み | ルーチン API とスケジュールの `routine_id` を承認 |
| 2026-08-30 00:17 | 未承認 | PATCH `/routines/{routine_id}`（項目更新。紐づくスケジュールは変えない） |
| 2026-08-30 00:23 | 承認済み | PATCH `/routines/{routine_id}` を承認 |
| 2026-08-30 08:01 | 未承認 | スケジュールとルーチンの要求・応答に `needs_notification` を追加。適用時はルーチンの値 |
| 2026-08-30 08:02 | 承認済み | スケジュールとルーチンの `needs_notification` を承認 |
