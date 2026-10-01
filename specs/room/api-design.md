# API設計: room（ROOM）

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。テーブル定義は `db-design.md` を参照する。ログイン・ログアウトの API は持たない。他機能向けの利用可否判定 API は提供しない。

機器の状態の取得と変更は、SwitchBot の Web API を通して行う（`design.md` の外部連携）。画面、定期実行ジョブ、AI（MCP）は、同じ内容の機能を使う（REQ-011）。定期実行ジョブは HTTP を介さず、同じサービス層を直接呼ぶ。

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
- ログイン中でも、識別子 `room` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外は認証要かつ本機能の割当要。

#### API キーによる認証

他システム連携（AI（MCP）など）のため、Cookie に加えて API キーによる認証を受け付ける。API キーの発行・失効は `api-key-management` が担う。契約の詳細は `specs/api-key-management/api-design.md` の「対象機能の API キー認証」。

- 要求ヘッダ `Authorization: Bearer <API キー>` で受け取る（スキーム名は大文字小文字を区別しない）。URL では受け取らない。Cookie は不要。
- `Authorization` ヘッダがあるときは API キーだけで判定し、Cookie・`DEBUG_USER` での判定に戻らない。無いときは従来どおり。
- `Bearer` 方式でない、キーが空、該当なし、失効済み、有効期限切れ、持ち主が論理削除済みは、いずれも未ログイン（401）。このときヘッダ `WWW-Authenticate: Bearer` を付ける。理由は本文で区別しない。
- 持ち主に識別子 `room` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- 許可したときは持ち主をログイン中ユーザとして処理し、API キーの最終利用日時を更新する。セッションの期限は延ばさない。
- GET `/settings` は、`Authorization` ヘッダがあっても判定しない（従来どおり認証不要）。
- 各エンドポイントのパス・要求・応答・エラーは、Cookie で利用したときと同じ。API キーでも、玄関ドアの施錠・開錠を含むすべての操作ができる。

### 共通の値

- 日時: ISO 8601。日本標準時のオフセット付き（例: `2026-10-01T10:15:30+09:00`）。
- 時刻: `HH:MM`（24 時間。秒は付けない。日本標準時）。
- `device`（機器）は次の 5 つ。

  | 値 | 機器 | 取り得る `state` |
  |----|------|------------------|
  | `ceiling_light` | 電灯 | `off`（常に。未実装） |
  | `indirect_light` | 間接照明 | `on`、`off` |
  | `indoor_speaker` | 屋内スピーカー | `on`、`off` |
  | `bedside_speaker` | 枕元スピーカー | `on`、`off` |
  | `front_door` | 玄関ドア | `locked`（施錠中）、`unlocked`（開錠中） |

- `scene`（一括切替）は次の 5 つ。

  | 値 | 名称 | 各機器の目標 |
  |----|------|--------------|
  | `indoor_speaker` | 屋内スピーカー選択 | `indoor_speaker` を `on`、`bedside_speaker` を `off` |
  | `bedside_speaker` | 枕元スピーカー選択 | `indoor_speaker` を `off`、`bedside_speaker` を `on` |
  | `ceiling_light` | 電灯選択 | `ceiling_light` を `on`、`indirect_light` を `off` |
  | `indirect_light` | 間接照明選択 | `ceiling_light` を `off`、`indirect_light` を `on` |
  | `out` | お出かけ | `ceiling_light`、`indirect_light`、`indoor_speaker`、`bedside_speaker` をすべて `off` |

  どの一括切替も、`front_door` は変えない。`ceiling_light` を対象とする指示は、機器へ何も指示せず、結果を `skipped`（未実装）とする（REQ-006、REQ-007）。

- `condition`（実行条件）は `daily`（毎日）、`weekdays`（曜日の指定）、`holiday`（祝日の指定）。
- `weekdays`（曜日）は 1〜7 の整数の配列。1 = 月曜、…、7 = 日曜（ISO 8601）。
- 機器の状態の項目（`device_state`）は次の形とする。

  ```json
  { "status": "ok", "state": "on" }
  ```

  - `status`: `ok`（取得できた）または `error`（取得できなかった）。`error` のとき `state` は `null`。状態を推測した値は返さない（REQ-001、REQ-012）。
  - `front_door` は、さらに `battery`（電池残量。0〜100 の整数。取得できなければ `null`）を持つ。
  - `ceiling_light` は、さらに `implemented`（常に `false`）を持つ。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正 | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし | 404、本文 `{ "detail": "対象がありません" }` |
| 機器の操作の失敗（SwitchBot に接続できない、SwitchBot がエラーを返した） | 502、本文 `{ "detail": "機器を操作できませんでした" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由（SwitchBot のエラー内容を含む）はログにだけ残す。本文には上表の文言だけを使う。SwitchBot の認証情報と機器の識別子は、応答にもログにも出さない。

## エンドポイント一覧

| メソッド | パス | 認証 | 概要 | 対応 REQ |
|----------|------|------|------|----------|
| GET | `/settings` | 不要 | ログイン URL、メニュー URL、アイコン | REQ-001 |
| GET | `/state` | 要 | 5 機器の状態と取得日時 | REQ-001、REQ-003、REQ-011、REQ-012 |
| PUT | `/devices/{device}/state` | 要 | 1 機器の個別切替 | REQ-004、REQ-005、REQ-006、REQ-011、REQ-012 |
| POST | `/scenes/{scene}` | 要 | 一括切替の実行 | REQ-007、REQ-011、REQ-012 |
| GET | `/schedules` | 要 | 定期実行の一覧 | REQ-008、REQ-010、REQ-011 |
| POST | `/schedules` | 要 | 定期実行の登録 | REQ-008、REQ-011 |
| PUT | `/schedules/{schedule_id}` | 要 | 定期実行の変更 | REQ-008、REQ-011 |
| PUT | `/schedules/{schedule_id}/enabled` | 要 | 定期実行の有効／無効の切替 | REQ-008、REQ-011 |
| DELETE | `/schedules/{schedule_id}` | 要 | 定期実行の削除 | REQ-008、REQ-011 |

定期実行の自動実行（REQ-009）と操作の記録（REQ-013）は、API を持たない（ジョブとログの処理）。

## エンドポイント詳細

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

### GET `/state`

- 認証: 要
- 対応 REQ: REQ-001、REQ-003、REQ-011、REQ-012

要求: なし

応答: 200

```json
{
  "fetched_at": "2026-10-01T10:15:30+09:00",
  "devices": {
    "ceiling_light": { "status": "ok", "state": "off", "implemented": false },
    "indirect_light": { "status": "ok", "state": "on" },
    "indoor_speaker": { "status": "error", "state": null },
    "bedside_speaker": { "status": "ok", "state": "off" },
    "front_door": { "status": "ok", "state": "locked", "battery": 35 }
  }
}
```

処理概要:

- 電灯を除く 4 機器の状態を、SwitchBot へ並行して問い合わせる。キャッシュしない。
- `fetched_at` は、問い合わせを終えた時刻。
- ある機器の取得に失敗しても、他の機器の取得は続ける。失敗した機器は `status: "error"` とし、HTTP は 200 のままとする。全機器の取得に失敗したときも 200 とする（画面が全機器の失敗を判断する）。
- 電灯は問い合わせず、常に `off`、`implemented: false` とする（REQ-006）。
- 玄関ドアは、SwitchBot が `locked` を返したら `locked`、`unlocked` を返したら `unlocked` とする。それ以外の値（施錠が不完全な状態など）は `status: "error"` とする。電池残量は、SwitchBot の値をそのまま使う。
- 間接照明、屋内スピーカー、枕元スピーカーは、SwitchBot の電源の状態（`on`／`off`）を使う。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### PUT `/devices/{device}/state`

- 認証: 要
- 対応 REQ: REQ-004、REQ-005、REQ-006、REQ-011、REQ-012

パス: `device` は共通の値の 5 機器のいずれか。

要求（本文）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `state` | string | 必須 | 目標の状態。`ceiling_light`・`indirect_light`・`indoor_speaker`・`bedside_speaker` は `on` または `off`。`front_door` は `locked` または `unlocked` |

「反転（今の逆）」の指示は受けない。目標の状態を必ず明示する（誤って逆に切り替えないため。`design.md` の業務ロジック）。玄関ドアの確認は、画面（フロント）の責務である。API は確認済みの要求として受ける。

応答: 200

```json
{
  "device": "indirect_light",
  "applied": true,
  "fetched_at": "2026-10-01T10:15:33+09:00",
  "result": { "status": "ok", "state": "on" }
}
```

- `applied`: 機器へ指示を送ったか。電灯への要求は `false`（何も指示しない）。それ以外で成功したときは `true`。
- `result`: 指示のあとに、その機器の状態を取得し直した結果（`device_state`）。指示が成功しても、取得し直した値が目標と食い違うときは、取得した値を返す。指示は成功したが、取得し直しに失敗したときは、`status: "error"` を返す（HTTP は 200）。

処理概要:

- `ceiling_light` への要求は、機器へ何も指示せず、`applied: false`、`result` は `{ "status": "ok", "state": "off", "implemented": false }` とする（`state` が `off` 以外でも同じ。REQ-006）。
- `indirect_light`、`indoor_speaker`、`bedside_speaker` は、SwitchBot へ `turnOn`／`turnOff` を指示する。
- `front_door` は、SwitchBot へ `lock`／`unlock` を指示する。
- 指示は 1 回だけ行い、自動で再試行しない。他の機器の状態は変えない。

エラー:

| 状況 | 応答 |
|------|------|
| `device` が 5 機器のいずれでもない | 404 |
| `state` が無い、またはその機器で取り得る値でない（例: 玄関ドアに `on`、照明に `locked`） | 400 |
| SwitchBot に接続できない、SwitchBot が指示の失敗を返した | 502（状態は変えない） |
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/scenes/{scene}`

- 認証: 要
- 対応 REQ: REQ-007、REQ-011、REQ-012

パス: `scene` は共通の値の 5 つのいずれか。

要求: 本文なし。

応答: 200

```json
{
  "scene": "ceiling_light",
  "outcome": "success",
  "results": [
    { "device": "ceiling_light", "target": "on", "outcome": "skipped" },
    { "device": "indirect_light", "target": "off", "outcome": "success" }
  ],
  "fetched_at": "2026-10-01T10:15:36+09:00",
  "devices": {
    "ceiling_light": { "status": "ok", "state": "off", "implemented": false },
    "indirect_light": { "status": "ok", "state": "off" },
    "indoor_speaker": { "status": "ok", "state": "off" },
    "bedside_speaker": { "status": "ok", "state": "off" },
    "front_door": { "status": "ok", "state": "locked", "battery": 35 }
  }
}
```

- `results`: 一括切替の目標（共通の値の表）に含まれる機器ごとの結果。`outcome` は `success`（成功）、`failure`（失敗）、`skipped`（電灯。未実装のため指示しない）。
- `outcome`（全体）: 指示した機器（`skipped` を除く）がすべて成功したら `success`、すべて失敗したら `failure`、成功と失敗が混在したら `partial`。
- `fetched_at` と `devices`: 実行のあとに、各機器の状態を取得し直した結果（`GET /state` の応答と同じ形）。
- 一括切替で一部の機器が失敗しても、HTTP は 200 とする（どの機器が成功し、どの機器が失敗したかを `results` で示す。成功した機器は元に戻さない）。

処理概要:

- 対象機器へ個別の指示を並行して行い、機器ごとの成否を集める。指示は 1 回だけ行い、自動で再試行しない。
- 玄関ドアは変えない（どの一括切替も対象に含まない）。
- 実行後に、全機器の状態を取得し直して返す。

エラー:

| 状況 | 応答 |
|------|------|
| `scene` が 5 つのいずれでもない | 404 |
| 未ログイン | 401 |
| 権限なし | 403 |

### GET `/schedules`

- 認証: 要
- 対応 REQ: REQ-008、REQ-010、REQ-011

要求: なし

応答: 200

```json
{
  "schedules": [
    {
      "id": 1,
      "condition": "weekdays",
      "weekdays": [1, 3, 5],
      "run_time": "07:00",
      "scene": "indoor_speaker",
      "is_enabled": true,
      "last_run": {
        "at": "2026-10-01T07:00:02+09:00",
        "result": "partial",
        "failed_devices": ["bedside_speaker"]
      }
    },
    {
      "id": 2,
      "condition": "holiday",
      "weekdays": [],
      "run_time": "22:30",
      "scene": "out",
      "is_enabled": false,
      "last_run": null
    }
  ]
}
```

- `weekdays`: `condition` が `weekdays` のときは 1 件以上（昇順）。それ以外は空配列。
- `last_run`: 未実行は `null`。`result` は `success`、`partial`、`failure`。`failed_devices` は失敗した機器（`ceiling_light`、`indirect_light`、`indoor_speaker`、`bedside_speaker` のいずれか）。成功のときは空配列。
- 並びは、`run_time` の昇順、同じ時刻なら `scene` の名称順。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/schedules`

- 認証: 要
- 対応 REQ: REQ-008、REQ-011

要求（本文）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `condition` | string | 必須 | `daily`、`weekdays`、`holiday` のいずれか |
| `weekdays` | integer[] | 条件付き | `condition` が `weekdays` のとき必須（1 件以上、各値は 1〜7、重複なし）。それ以外のときは省略または空配列 |
| `run_time` | string | 必須 | `HH:MM`（00:00〜23:59） |
| `scene` | string | 必須 | 一括切替の 5 種のいずれか。玄関ドアの施錠・開錠は指定できない |
| `is_enabled` | boolean | 任意 | 既定は `true` |

応答: 201。`GET /schedules` の 1 件と同じ形（`last_run` は `null`）。

処理概要: 作成した利用者を残して登録する。`condition` が `weekdays` のときは、曜日も登録する。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、値が取り得る範囲外（実行条件、時刻の形式、一括切替）、`weekdays` が条件と合わない（`weekdays` で 0 件、`daily`／`holiday` で 1 件以上、範囲外、重複） | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### PUT `/schedules/{schedule_id}`

- 認証: 要
- 対応 REQ: REQ-008、REQ-011

要求（本文）: `POST /schedules` と同じ。ただし `is_enabled` も指定する（省略時は現在の値を維持する）。全項目を置き換える（`weekdays` は置き換える）。

応答: 200。`GET /schedules` の 1 件と同じ形。

処理概要: 定義を変更する。最終実行（`last_run`）は変えない。

エラー:

| 状況 | 応答 |
|------|------|
| 入力不正（`POST /schedules` と同じ） | 400 |
| `schedule_id` の定期実行が無い | 404 |
| 未ログイン | 401 |
| 権限なし | 403 |

### PUT `/schedules/{schedule_id}/enabled`

- 認証: 要
- 対応 REQ: REQ-008、REQ-011

要求（本文）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `is_enabled` | boolean | 必須 | 有効なら `true`、無効なら `false` |

応答: 200。`GET /schedules` の 1 件と同じ形。

処理概要: 有効／無効だけを更新する。他の項目と最終実行は変えない。

エラー:

| 状況 | 応答 |
|------|------|
| `is_enabled` が無い、または真偽値でない | 400 |
| `schedule_id` の定期実行が無い | 404 |
| 未ログイン | 401 |
| 権限なし | 403 |

### DELETE `/schedules/{schedule_id}`

- 認証: 要
- 対応 REQ: REQ-008、REQ-011

要求: なし

応答: 204（本文なし）

処理概要: 定期実行を削除する（物理削除。曜日と実行記録も連動して消える。`db-design.md`）。

エラー:

| 状況 | 応答 |
|------|------|
| `schedule_id` の定期実行が無い | 404 |
| 未ログイン | 401 |
| 権限なし | 403 |

## 要件トレーサビリティ

| 要件 | API設計 |
|------|---------|
| REQ-001 | 共通の認証。GET `/settings`。GET `/state`（取得に失敗した機器の `status: "error"`）。各 API の 401 / 403 |
| REQ-002 | API なし（画面の図示。UI 設計） |
| REQ-003 | GET `/state`（再取得）。PUT `/devices/{device}/state` と POST `/scenes/{scene}` の応答に含む再取得の結果 |
| REQ-004 | PUT `/devices/{device}/state`（間接照明、屋内スピーカー、枕元スピーカー） |
| REQ-005 | PUT `/devices/{device}/state`（`front_door`。目標の状態を明示。確認は画面の責務）。電池残量は GET `/state` の `battery`（表示のみ。変更する API なし） |
| REQ-006 | GET `/state`（`ceiling_light` は常に `off`、`implemented: false`）。PUT `/devices/{device}/state`（何もしない）。POST `/scenes/{scene}` の `skipped` |
| REQ-007 | POST `/scenes/{scene}`（5 種。機器ごとの `results`、全体の `outcome`、再取得した `devices`） |
| REQ-008 | GET / POST / PUT / DELETE `/schedules`、PUT `/schedules/{schedule_id}/enabled`（玄関ドアの施錠・開錠は `scene` に指定できない） |
| REQ-009 | API なし（ジョブの処理。`design.md`） |
| REQ-010 | GET `/schedules` の `last_run` |
| REQ-011 | 本書全体。API キー認証。画面・ジョブ・API が同じサービス層を使う |
| REQ-012 | GET `/state`、PUT `/devices/{device}/state`、POST `/scenes/{scene}`。認証情報と機器の識別子は応答に出さない。取得失敗時に推測値を返さない |
| REQ-013 | API なし（ログの処理。`design.md`） |

## 未決事項

- 玄関ドアの `lock`（施錠）の指示は、実機での動作確認が済んでいない（`unlock` は確認済み）。実装時の結合テストで確認する。
- 玄関ドアの状態は、実機の確認で `lockState` が `locked`、電池残量が `battery`（整数）であることを確かめた。`unlocked` と、施錠が不完全な状態の値は、実機の確認が済んでいない。実装時に確認する。

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-10-01 10:13 | 未承認 | 初版 |
| 2026-10-01 10:17 | 承認済み | 初版を承認 |
