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
  | `ceiling_light` | 電灯 | `on`、`off` |
  | `indirect_light` | 間接照明 | `on`、`off` |
  | `indoor_speaker` | 屋内スピーカー | `on`、`off` |
  | `bedside_speaker` | 枕元スピーカー | `on`、`off` |
  | `front_door` | 玄関ドア | `locked`（施錠中）、`unlocked`（開錠中） |

- `scene`（一括切替）は次の 5 つ。

  | 値 | 名称 | 各機器の目標 |
  |----|------|--------------|
  | `indoor_speaker` | 屋内スピーカー選択 | `indoor_speaker` を `on`、`bedside_speaker` を `off` |
  | `bedside_speaker` | 枕元スピーカー選択 | `indoor_speaker` を `off`、`bedside_speaker` を `on` |
  | `ceiling_light` | 電灯選択 | `ceiling_light` を `on`（調光パターンは `pattern`。省略時は既定）、`indirect_light` を `off` |
  | `indirect_light` | 間接照明選択 | `ceiling_light` を `off`、`indirect_light` を `on` |
  | `out` | お出かけ | `ceiling_light`、`indirect_light`、`indoor_speaker`、`bedside_speaker` をすべて `off` |

  どの一括切替も、`front_door` は変えない。

- `pattern`（調光パターン）は次の 4 つ。電灯を `on` にするときだけ指定できる。省略したときは、既定の `full`。

  | 値 | 名称 | 明るさ | 色温度 |
  |----|------|--------|--------|
  | `full` | 全灯（既定） | 100 | 6200 |
  | `reading` | 読書 | 80 | 5000 |
  | `relax` | くつろぎ | 50 | 3000 |
  | `night` | 夜 | 10 | 2700 |

- `condition`（実行条件）は `daily`（毎日）、`weekdays`（曜日の指定）。祝日だけの条件は無い。
- 祝日は、日本の国民の祝日に加えて、定期実行を登録した利用者のユーザ休日を含む。
- `holiday_mode`（祝日の扱い。`condition` が `weekdays` のときだけ意味を持つ）は `none`（指定した曜日のみ。既定）、`include`（祝日も実行）、`exclude`（祝日は実行しない）。
- `day_shift`（実行日の取り方。`condition` が `weekdays` のときだけ意味を持つ）は `same`（当日。既定）、`before`（の前の日）、`after`（の次の日）。
  基準日（曜日と祝日の扱いで決まる日）に対して、実行する日を決める。`before` は、翌日が基準日である日に、`after` は、前日が基準日である日に実行する（`design.md` の基準日の判定）。
- 定期実行の実行内容は、次の 2 種のどちらか 1 つ。
  - 一括切替: `scene`（上の 5 つのいずれか）を指定する。
  - 機器の個別切替: `device`（`ceiling_light`、`indirect_light`、`indoor_speaker`、`bedside_speaker` のいずれか。`front_door` は指定できない）と、`state`（`on` または `off`）を指定する。`device` が `ceiling_light` で、`state` が `on` のときだけ、`pattern` も指定できる（省略時は `full`）。
- `weekdays`（曜日）は 1〜7 の整数の配列。1 = 月曜、…、7 = 日曜（ISO 8601）。
- 機器の状態の項目（`device_state`）は次の形とする。

  ```json
  { "status": "ok", "state": "on" }
  ```

  - `status`: `ok`（取得できた）または `error`（取得できなかった）。`error` のとき `state` は `null`。状態を推測した値は返さない（REQ-001、REQ-012）。
  - `front_door` は、さらに `battery`（電池残量。0〜100 の整数。取得できなければ `null`）を持つ。
  - `ceiling_light` の明るさと色温度は、返さない（REQ-006）。`state` は電源の `on` / `off` だけである。

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
| GET | `/dimming-patterns` | 要 | 調光パターンの種類 | REQ-006、REQ-011 |
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
    "ceiling_light": { "status": "ok", "state": "on" },
    "indirect_light": { "status": "ok", "state": "off" },
    "indoor_speaker": { "status": "error", "state": null },
    "bedside_speaker": { "status": "ok", "state": "off" },
    "front_door": { "status": "ok", "state": "locked", "battery": 35 }
  }
}
```

処理概要:

- 5 機器の状態を、SwitchBot へ並行して問い合わせる。キャッシュしない。
- `fetched_at` は、問い合わせを終えた時刻。
- ある機器の取得に失敗しても、他の機器の取得は続ける。失敗した機器は `status: "error"` とし、HTTP は 200 のままとする。全機器の取得に失敗したときも 200 とする（画面が全機器の失敗を判断する）。
- 玄関ドアは、SwitchBot が `locked` を返したら `locked`、`unlocked` を返したら `unlocked` とする。それ以外の値（施錠が不完全な状態など）は `status: "error"` とする。電池残量は、SwitchBot の値をそのまま使う。
- 電灯、間接照明、屋内スピーカー、枕元スピーカーは、SwitchBot の電源の状態（`on`／`off`）を使う。電灯の明るさと色温度は、読まない・返さない（REQ-006）。

エラー:

| 状況 | 応答 |
|------|------|
| 未ログイン | 401 |
| 権限なし | 403 |

### GET `/dimming-patterns`

- 認証: 要
- 対応 REQ: REQ-006、REQ-011

要求: なし

応答: 200

```json
{
  "default": "full",
  "patterns": [
    { "id": "full", "name": "全灯", "brightness": 100, "color_temperature": 6200 },
    { "id": "reading", "name": "読書", "brightness": 80, "color_temperature": 5000 },
    { "id": "relax", "name": "くつろぎ", "brightness": 50, "color_temperature": 3000 },
    { "id": "night", "name": "夜", "brightness": 10, "color_temperature": 2700 }
  ]
}
```

処理概要: 固定の調光パターン 4 種（`design.md` の `app/dimming.py`）を、この順で返す。SwitchBot へは問い合わせない。`default` は既定のパターン。

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
| `pattern` | string | 任意 | 調光パターン（`full`、`reading`、`relax`、`night`）。`device` が `ceiling_light` で、`state` が `on` のときだけ指定できる。省略時は `full`。それ以外で指定すると入力不正 |

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

- `applied`: 機器へ指示を送ったか。成功したときは常に `true`。
- `result`: 指示のあとに、その機器の状態を取得し直した結果（`device_state`）。指示が成功しても、取得し直した値が目標と食い違うときは、取得した値を返す。指示は成功したが、取得し直しに失敗したときは、`status: "error"` を返す（HTTP は 200）。

処理概要:

- `ceiling_light` を `on` にするときは、SwitchBot へ、`turnOn`、`setBrightness`（パターンの明るさ）、`setColorTemperature`（パターンの色温度）を、この順に 1 回ずつ指示する。途中の指示が失敗したら、残りは送らず 502 とする（電灯が点灯したまま、パターンが一部だけ変わっていることがある。状態は実機から取り直して確かめる）。ON の電灯に別のパターンを指定したときも、同じ 3 つを指示する。`off` のときは `turnOff` だけを指示する（REQ-006）。
- `indirect_light`、`indoor_speaker`、`bedside_speaker` は、SwitchBot へ `turnOn`／`turnOff` を指示する。
- `front_door` は、SwitchBot へ `lock`／`unlock` を指示する。
- 指示は 1 回だけ行い、自動で再試行しない。他の機器の状態は変えない。

エラー:

| 状況 | 応答 |
|------|------|
| `device` が 5 機器のいずれでもない | 404 |
| `state` が無い、またはその機器で取り得る値でない（例: 玄関ドアに `on`、照明に `locked`） | 400 |
| `pattern` が 4 種のいずれでもない、または、電灯を `on` にする要求以外で指定された | 400 |
| SwitchBot に接続できない、SwitchBot が指示の失敗を返した | 502（状態は変えない） |
| 未ログイン | 401 |
| 権限なし | 403 |

### POST `/scenes/{scene}`

- 認証: 要
- 対応 REQ: REQ-007、REQ-011、REQ-012

パス: `scene` は共通の値の 5 つのいずれか。

要求（本文）: 任意。`scene` が `ceiling_light`（電灯選択）のときだけ、次を指定できる。それ以外の一括切替は、本文なし。

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `pattern` | string | 任意 | 調光パターン（`full`、`reading`、`relax`、`night`）。電灯を `on` にするときのパターン。省略時、または本文なしのときは `full`。電灯選択以外で指定すると入力不正 |

応答: 200

```json
{
  "scene": "ceiling_light",
  "outcome": "success",
  "results": [
    { "device": "ceiling_light", "target": "on", "outcome": "success" },
    { "device": "indirect_light", "target": "off", "outcome": "success" }
  ],
  "fetched_at": "2026-10-01T10:15:36+09:00",
  "devices": {
    "ceiling_light": { "status": "ok", "state": "on" },
    "indirect_light": { "status": "ok", "state": "off" },
    "indoor_speaker": { "status": "ok", "state": "off" },
    "bedside_speaker": { "status": "ok", "state": "off" },
    "front_door": { "status": "ok", "state": "locked", "battery": 35 }
  }
}
```

- `results`: 一括切替の目標（共通の値の表）に含まれる機器ごとの結果。`outcome` は `success`（成功）、`failure`（失敗）。
- `outcome`（全体）: 指示した機器がすべて成功したら `success`、すべて失敗したら `failure`、成功と失敗が混在したら `partial`。
- `fetched_at` と `devices`: 実行のあとに、各機器の状態を取得し直した結果（`GET /state` の応答と同じ形）。
- 一括切替で一部の機器が失敗しても、HTTP は 200 とする（どの機器が成功し、どの機器が失敗したかを `results` で示す。成功した機器は元に戻さない）。

処理概要:

- 対象機器へ個別の指示を並行して行い、機器ごとの成否を集める。指示は 1 回だけ行い、自動で再試行しない。電灯を `on` にする指示は、個別切替と同じ（`turnOn`、`setBrightness`、`setColorTemperature`）で、機器ごとの成否は、その 3 つがすべて成功したときだけ成功とする。
- 玄関ドアは変えない（どの一括切替も対象に含まない）。
- 実行後に、全機器の状態を取得し直して返す。

エラー:

| 状況 | 応答 |
|------|------|
| `scene` が 5 つのいずれでもない | 404 |
| `pattern` が 4 種のいずれでもない、または、電灯選択以外で指定された | 400 |
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
      "holiday_mode": "none",
      "day_shift": "same",
      "run_time": "07:00",
      "scene": "indoor_speaker",
      "device": null,
      "state": null,
      "pattern": null,
      "is_enabled": true,
      "last_run": {
        "at": "2026-10-01T07:00:02+09:00",
        "result": "partial",
        "failed_devices": ["bedside_speaker"]
      }
    },
    {
      "id": 2,
      "condition": "weekdays",
      "weekdays": [1, 2, 3, 4, 5],
      "holiday_mode": "exclude",
      "day_shift": "before",
      "run_time": "22:30",
      "scene": null,
      "device": "indirect_light",
      "state": "off",
      "pattern": null,
      "is_enabled": false,
      "last_run": null
    },
    {
      "id": 3,
      "condition": "daily",
      "weekdays": [],
      "holiday_mode": "none",
      "day_shift": "same",
      "run_time": "23:00",
      "scene": "out",
      "device": null,
      "state": null,
      "pattern": null,
      "is_enabled": true,
      "last_run": null
    },
    {
      "id": 4,
      "condition": "daily",
      "weekdays": [],
      "holiday_mode": "none",
      "day_shift": "same",
      "run_time": "07:00",
      "scene": null,
      "device": "ceiling_light",
      "state": "on",
      "pattern": "reading",
      "is_enabled": true,
      "last_run": null
    }
  ]
}
```

- `weekdays`: `condition` が `weekdays` のときは 1 件以上（昇順）。それ以外は空配列。
- `holiday_mode`、`day_shift`: `condition` が `daily` のときは、常に `none`、`same`。
- 実行内容: 一括切替のときは `scene` が値を持ち、`device` と `state` は `null`。機器の個別切替のときは `device` と `state` が値を持ち、`scene` は `null`。
- `pattern`: 電灯を `on` にする個別切替のときだけ値を持つ（`full`、`reading`、`relax`、`night`。登録で省略したときは `full`）。それ以外は `null`。
- `last_run`: 未実行は `null`。`result` は `success`、`partial`、`failure`。`failed_devices` は失敗した機器（`ceiling_light`、`indirect_light`、`indoor_speaker`、`bedside_speaker` のいずれか）。成功のときは空配列。
- `last_run.result`: 機器の個別切替は、`success` か `failure` のみ（`partial` は一括切替のとき）。失敗のとき、`failed_devices` は、その機器 1 つ。
- 並びは、`run_time` の昇順、同じ時刻なら、一括切替（`scene` のキー名順）、続いて機器の個別切替（`device`、`state` のキー名順）、最後に `id` の昇順。

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
| `condition` | string | 必須 | `daily`、`weekdays` のいずれか |
| `weekdays` | integer[] | 条件付き | `condition` が `weekdays` のとき必須（1 件以上、各値は 1〜7、重複なし）。それ以外のときは省略または空配列 |
| `holiday_mode` | string | 任意 | `none`、`include`、`exclude`。省略時は `none`。`condition` が `daily` のときは、省略または `none` |
| `day_shift` | string | 任意 | `same`、`before`、`after`。省略時は `same`。`condition` が `daily` のときは、省略または `same` |
| `run_time` | string | 必須 | `HH:MM`（00:00〜23:59） |
| `scene` | string | 条件付き | 一括切替の 5 種のいずれか。実行内容が一括切替のとき必須。機器の個別切替のときは省略 |
| `device` | string | 条件付き | 個別切替の機器（`ceiling_light`、`indirect_light`、`indoor_speaker`、`bedside_speaker`）。実行内容が機器の個別切替のとき必須。玄関ドア（`front_door`）は指定できない。一括切替のときは省略 |
| `state` | string | 条件付き | 個別切替の目標の状態（`on`、`off`）。`device` を指定するとき必須。一括切替のときは省略 |
| `pattern` | string | 任意 | 調光パターン（`full`、`reading`、`relax`、`night`）。`device` が `ceiling_light` で、`state` が `on` のときだけ指定できる。省略時は `full`。それ以外のとき、指定すると入力不正（一括切替には指定できない。電灯選択は、定期実行では既定のパターンで点灯する） |
| `is_enabled` | boolean | 任意 | 既定は `true` |

応答: 201。`GET /schedules` の 1 件と同じ形（`last_run` は `null`）。

処理概要: 作成した利用者を残して登録する。`condition` が `weekdays` のときは、曜日も登録する。実行内容は、`scene`、または、`device` と `state` の、どちらか一方だけを指定する（両方、どちらも無い、`device` だけ、`state` だけは、入力不正）。従来どおり `scene` だけを指定する要求は、そのまま受け付ける（`holiday_mode` は `none`、`day_shift` は `same` になる）。

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、値が取り得る範囲外（実行条件、祝日の扱い、実行日の取り方、時刻の形式、一括切替、機器、状態。従来の実行条件 `holiday` を含む）、`weekdays` が条件と合わない（`weekdays` で 0 件、`daily` で 1 件以上、範囲外、重複）、`daily` なのに、`holiday_mode` が `none` でない、または `day_shift` が `same` でない、実行内容が合わない（`scene` と `device` の両方、どちらも無い、`device` と `state` の片方だけ）、`pattern` が 4 種のいずれでもない、または、電灯を `on` にする個別切替以外で指定された | 400 |
| 未ログイン | 401 |
| 権限なし | 403 |

### PUT `/schedules/{schedule_id}`

- 認証: 要
- 対応 REQ: REQ-008、REQ-011

要求（本文）: `POST /schedules` と同じ。ただし `is_enabled` も指定する（省略時は現在の値を維持する）。全項目を置き換える（`weekdays` は置き換える）。`holiday_mode` と `day_shift` は、省略すると、現在の値を維持せず、既定（`none`、`same`）になる。実行内容も置き換える（一括切替から個別切替へ、または、その逆に、変えられる）。

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
| REQ-006 | GET `/state`（`ceiling_light` の電源 `on` / `off`。明るさと色温度は返さない）。GET `/dimming-patterns`。PUT `/devices/{device}/state`（`ceiling_light` の `on` / `off` と `pattern`） |
| REQ-007 | POST `/scenes/{scene}`（5 種。電灯選択は `pattern` を受け取る。機器ごとの `results`、全体の `outcome`、再取得した `devices`） |
| REQ-008 | GET / POST / PUT / DELETE `/schedules`、PUT `/schedules/{schedule_id}/enabled`（実行内容の `scene` または `device`+`state`（+電灯の ON のときの `pattern`）、祝日の扱い、実行日の取り方。玄関ドアの施錠・開錠は指定できない） |
| REQ-009 | API なし（ジョブの処理。`design.md`） |
| REQ-010 | GET `/schedules` の `last_run` |
| REQ-011 | 本書全体。API キー認証。画面・ジョブ・API が同じサービス層を使う |
| REQ-012 | GET `/state`、PUT `/devices/{device}/state`、POST `/scenes/{scene}`。認証情報と機器の識別子は応答に出さない。取得失敗時に推測値を返さない |
| REQ-013 | API なし（ログの処理。`design.md`） |

## 未決事項

- 電灯の調光の指示（`turnOn`、`setBrightness`、`setColorTemperature`）を続けて送ってよいか、指示の間に待ちが要るかは、実機で確かめて確定する（`design.md` の未決事項）。結果によっては、指示の順序や間隔を、本書と `design.md` の改訂で決める。
- 玄関ドアの `lock`（施錠）の指示は、実機での動作確認が済んでいない（`unlock` は確認済み）。実装時の結合テストで確認する。
- 玄関ドアの状態は、実機の確認で `lockState` が `locked`、電池残量が `battery`（整数）であることを確かめた。`unlocked` と、施錠が不完全な状態の値は、実機の確認が済んでいない。実装時に確認する。

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-10-01 10:13 | 未承認 | 初版 |
| 2026-10-01 10:17 | 承認済み | 初版を承認 |
| 2026-10-01 15:05 | 未承認 | 定期実行の改訂に合わせ、`/schedules` の要求・応答に `holiday_mode`、`day_shift`、実行内容（`scene`、または `device`+`state`）を追加し、実行条件から `holiday` を廃止。個別切替の結果の扱いと並びを追記 |
| 2026-10-01 15:08 | 承認済み | 定期実行の改訂の API（実行内容、祝日の扱い、実行日の取り方）を承認 |
| 2026-10-03 22:10 | 未承認 | `holiday_mode` の「祝日」が、日本の祝日に加えて作成者のユーザ休日を含むことを明記（API の形は変更なし） |
| 2026-10-03 22:12 | 承認済み | ユーザ休日の `public` 化と祝日判定への反映の改訂を承認 |
| 2026-10-06 19:24 | 未承認 | 電灯の調光に合わせ、電灯を実機として扱う（`implemented` と `skipped` を廃止）。調光パターン 4 種（`full`／`reading`／`relax`／`night`）、GET `/dimming-patterns` の追加、PUT `/devices/{device}/state`・POST `/scenes/{scene}`（電灯選択）・`/schedules` の `pattern` の追加 |
| 2026-10-06 19:27 | 承認済み | 電灯の調光の API（`pattern`、GET `/dimming-patterns`）を承認 |
