# room（ROOM）タスク分解

> `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後に作成する。
> タスクは 1〜4 時間程度で完了できる粒度にする。

## 方針

- 実装は、本書のタスクのみを対象とする。要件と設計にない機能は足さない。
- 実装コードは `src/features/room/{backend,frontend,tests}` に置く（`rules/02-project.md`）。バックエンドのテストは `tests/` に置き、`backend/venv` を使う。フロントエンドのテストはフロントエンドの `package.json` の仕組みで動かす。
- Python は型ヒントを付ける。TypeScript は strict で書く。コメントと git のコミットメッセージは日本語で書く。
- 各タスクは、実装とあわせて、そのタスクの振る舞いのテストを書く。テストは、SwitchBot をモックして行う。実機を使う確認は T-019 にまとめる。
- 他機能・他フォルダの Python を import しない。`switchbot` のクライアントは、T-004 で `backend` へ複製する。
- 秘密情報（SwitchBot の認証情報、機器の識別子、API キー、セッション ID）は、コード・ログ・応答に出さない。
- 実行の順は、おおむね T-001 から番号順。T-010〜T-016（フロントエンド）は、T-003 のあとなら並行して進めてよい。

## タスク一覧

### バックエンド

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-001 | バックエンドの土台: venv、依存（fastapi、uvicorn、requests、psycopg、python-dotenv、jpholiday、pytest）、`app/main.py`（CORS、ルータ登録）、`app/config.py`（接続情報、CORS、セッション期間、`DEBUG_USER`、SwitchBot の認証情報、機器の識別子、`ROOM_SCHEDULE_GRACE_MINUTES`、`SWITCHBOT_TIMEOUT_SECONDS`、ログ設定。不正値は既定にしてログに残す）、`app/logger.py`（サイズローテーション、出力元の区別）、`app/db.py`、`.env` のひな型 | REQ-012、REQ-013 / design.md §バックエンド設計（起動、モジュール構成、設定値）、`rules/12-backend.md`、`rules/16-logging.md` | `src/features/room/backend/`、`src/features/room/tests/` | 3h | `backend` で `uvicorn app.main:app --port 8011` が起動する。設定の既定と不正値の扱いが設計どおりである（テストあり）。`.env` を読み、秘密情報をソースに直書きしていない。`log/` にローテーションつきでログが出る |
| T-002 | スキーマ `room` の DDL（`room_schedules`、`schedule_weekdays`、`schedule_runs`、制約、インデックス）。適用とテスト | REQ-008、REQ-009、REQ-010 / db-design.md §テーブル設計 | `src/features/room/backend/sql/`、`src/features/room/tests/` | 2h | DDL を開発用 DB へ適用できる（繰り返し適用しても壊れない）。CHECK、外部キー、`ON DELETE CASCADE`、`INSERT ... ON CONFLICT DO NOTHING` による同日の重複拒否が、テストで確認できる |
| T-003 | 認証・認可と `GET /settings`: `app/security.py`、`app/deps.py`、`app/services/access_service.py`、`app/repos.py`（ユーザ、セッション、機能マスタ、メニュー割当、API キー、システム設定）、`app/routers/settings.py`。Cookie、API キー、`DEBUG_USER` の判定 | REQ-011 / design.md §認証 / 認可、api-design.md §共通（認証、API キーによる認証）、`GET /settings` | `src/features/room/backend/app/`、`src/features/room/tests/` | 4h | Cookie と API キーで、未ログイン（401、API キーでは `WWW-Authenticate: Bearer` つき）、権限なし（403）、許可が、設計どおり判定される。API キーでの許可時に最終利用日時が更新され、セッション期限は延びない。API キー全体とそのハッシュがログに出ない。`GET /settings` が認証なしで返る（テストあり） |
| T-004 | SwitchBot クライアントの複製と、機器の状態取得: `app/switchbot/client.py`（署名、状態取得、コマンド送信、タイムアウト、再試行なし）、`app/services/device_service.py` の取得、`GET /state`（並行取得、機器ごとの失敗、電灯の固定、玄関ドアの値の変換、推測値を返さない） | REQ-001、REQ-003、REQ-006、REQ-012 / design.md §業務ロジック（状態の取得）、api-design.md §GET `/state` | `src/features/room/backend/app/switchbot/`、`src/features/room/backend/app/services/`、`src/features/room/backend/app/routers/room.py`、`src/features/room/tests/` | 4h | SwitchBot をモックして、5 機器の状態と取得日時が返る。1 機器の失敗が他に影響せず `status: "error"` になる。電灯は常に `off`・`implemented: false`。玄関ドアの `locked`／`unlocked` 以外は `error`。認証情報と機器の識別子が応答・ログに出ない。署名が仕様どおり（テストあり） |
| T-005 | 個別切替: `device_service` の切替、`PUT /devices/{device}/state`（目標の状態の検証、電灯は何もしない、指示のあとの再取得、502、再試行なし） | REQ-004、REQ-005、REQ-006、REQ-011、REQ-012 / design.md §業務ロジック（個別切替、玄関ドアの確認）、api-design.md §PUT `/devices/{device}/state` | `src/features/room/backend/app/services/device_service.py`、`src/features/room/backend/app/routers/room.py`、`src/features/room/tests/` | 3h | 間接照明・屋内スピーカー・枕元スピーカーが `turnOn`／`turnOff`、玄関ドアが `lock`／`unlock` で指示される。「反転」は受けず、機器に合わない `state` は 400、不明な `device` は 404。電灯は機器へ何も指示せず `applied: false`。SwitchBot の失敗は 502 で、状態は変わらない。他の機器に影響しない（テストあり） |
| T-006 | 一括切替: `app/services/scene_service.py`、`POST /scenes/{scene}`（5 種の定義、並行実行、機器ごとの `results`、全体の `outcome`、電灯の `skipped`、玄関ドアを変えない、実行後の再取得） | REQ-007、REQ-011 / design.md §業務ロジック（一括切替）、api-design.md §POST `/scenes/{scene}` | `src/features/room/backend/app/services/scene_service.py`、`src/features/room/backend/app/routers/room.py`、`src/features/room/tests/` | 3h | 5 種の目標が要件どおりである（電灯選択は間接照明の OFF だけが実行される）。一部失敗が `partial`、全失敗が `failure`、成功した機器が元に戻されない。玄関ドアに指示が行かない。不明な `scene` は 404（テストあり） |
| T-007 | 定期実行の定義の管理: `app/services/schedule_service.py`、`app/repos.py`（定期実行、曜日）、`app/routers/room_schedules.py`（一覧、登録、変更、有効／無効、削除）。検証、並び順、`last_run` の出力 | REQ-008、REQ-010、REQ-011 / design.md §業務ロジック（定期実行の定義）、api-design.md §GET/POST/PUT/DELETE `/schedules`、PUT `/schedules/{schedule_id}/enabled` | `src/features/room/backend/app/services/schedule_service.py`、`src/features/room/backend/app/routers/room_schedules.py`、`src/features/room/tests/` | 4h | 登録・変更・有効／無効・削除が仕様どおり動く。実行条件と曜日の整合、時刻の形式、一括切替の 5 種、が検証される（不正は 400）。存在しない ID は 404。変更で `last_run` が変わらない。削除で曜日と実行記録が消える。並びが `run_time` の昇順、同じ時刻なら `scene` の名称順（テストあり） |
| T-008 | 定期実行ジョブ: `app/services/holiday_service.py`（`jpholiday`）、`app/services/runner_service.py`（対象の選定、猶予、実行、実行記録による重複防止、最終実行の更新、失敗しても続行）、`app/jobs/__main__.py`（`python -m app.jobs`） | REQ-009、REQ-010、REQ-013 / design.md §業務ロジック（定期実行の判定、重複実行の防止、定期実行の失敗）、db-design.md §schedule_runs | `src/features/room/backend/app/services/`、`src/features/room/backend/app/jobs/`、`src/features/room/tests/` | 4h | 毎日・曜日・祝日の条件と、判定時刻が合うものだけが実行される（無効は実行されない）。猶予内（既定 5 分）の遅れで実行され、同じ日には 1 回だけ実行される（2 つのジョブを同時に動かしても重複しない）。ある定期実行が失敗しても他は続く。最終実行（日時、結果、失敗した機器）が更新される。日付と時刻の判定が日本標準時である。祝日（振替休日を含む）の判定がテストされている |
| T-009 | 操作ログの契機の点検: 個別切替、一括切替、定期実行の判定と実行、認証の各所のログが、設計の契機（入力、判断結果、理由）を満たすこと。秘密情報が出ないことのテスト | REQ-012、REQ-013 / design.md §業務ロジック（ログ）、`rules/16-logging.md` | `src/features/room/backend/app/`、`src/features/room/tests/` | 2h | 機器の変更ごとに、対象、変更後の状態、主体（画面の利用者／API の利用者／定期実行）、成否、失敗の理由がログに残る。定期実行の判定ごとに、対象、実行する／しない、理由が残る。SwitchBot の認証情報、機器の識別子、セッション ID、API キーがログにない（テストあり） |

### フロントエンド

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-010 | フロントエンドの土台: Vue + TypeScript（strict）、Vite（`base` は `/portal_room/`）、Vue Router（`createWebHistory(import.meta.env.BASE_URL)`）、`.env`（`VITE_API_ROOM_URL`）、トークン CSS（`--color-primary` は Violet `#A78BFA`）、殻（ヘッダ、PC の左ナビ、スマートフォンの下ナビ）、`Icon.vue`、API クライアント（Cookie つき）、未ログインの誘導、権限なしの表示、`GET /settings` の利用 | REQ-001 / design.md §フロントエンド設計、ui-design.md §共通UI、`rules/11-frontend.md`、`rules/15-ui-style.md` | `src/features/room/frontend/` | 4h | `npm run dev` で起動する。ヘッダ（戻る、見出し、システムアイコン）とナビ（ROOM、定期実行）が、PC とスマートフォンで設計どおり切り替わる。未ログインでログイン画面 URL へ進む。権限なしで「この機能は利用できません」が出る。他機能のコードを import していない |
| T-011 | 部屋の図: SVG のコンポーネント（5 パーツ、状態ごとの見た目、形・記号・文言の併用、取得失敗の表示、切替中の表示、電池残量、電灯の「未実装」、フォーカスリング、`aria-label`、44px のタップ領域） | REQ-002、REQ-006 / ui-design.md §SCR-001（部屋の図） | `src/features/room/frontend/src/components/` | 4h | 状態の入力（5 機器の `device_state`）に応じて、パーツの見た目と文言が変わる。操作できるパーツだけがボタンとして振る舞い、電灯と電池残量は何も起きない。キーボード（Enter・Space）で操作できる。状態の区別が色だけに頼らない。コンポーネントのテストがある |
| T-012 | ROOM ページ（取得と個別切替）: 画面を開いたときの取得、「更新」、取得日時の表示、読込中・エラーの表示、間接照明・屋内スピーカー・枕元スピーカーの切替、玄関ドアの確認ダイアログ（確定・キャンセル。背景では閉じない）、切替失敗時の表示 | REQ-001、REQ-003、REQ-004、REQ-005 / ui-design.md §SCR-001（部品配置、確認ダイアログ、状態別の表示） | `src/features/room/frontend/src/pages/`、`src/features/room/frontend/src/components/` | 4h | 画面を開くと状態が表示され、取得日時が出る。「更新」で取り直される（取得中は重ねて押せない）。切替の成功で図が更新され、失敗で元の状態のまま一文が出る。玄関ドアは確認で確定したときだけ切り替わる。取得できなかった機器は切り替えられない。テストがある |
| T-013 | ROOM ページ（一括切替とレイアウト）: 一括切替ボタン 5 つ、実行中の無効化、機器ごとの成否のステータス表示、PC とスマートフォンのレイアウト | REQ-002、REQ-007 / ui-design.md §SCR-001（レイアウト、ステータス） | `src/features/room/frontend/src/pages/`、`src/features/room/frontend/src/components/` | 3h | 5 つのボタンが、押すと対応する一括切替を実行する（確認は挟まない）。一部失敗のとき、成功した機器と失敗した機器が示される。実行のあと、図が最新の状態になる。PC は右の列、スマートフォンは 2 列で配置される。ページ全体がスクロールしない。テストがある |
| T-014 | 定期実行ページ: 一覧（PC は表、スマートフォンはカード）、最終実行の表示（日時、結果、失敗した機器。文言と記号で区別）、有効／無効の切替、削除の確認ダイアログ、読込中・空・エラーの表示 | REQ-008、REQ-010 / ui-design.md §SCR-002（部品配置、状態別の表示） | `src/features/room/frontend/src/pages/`、`src/features/room/frontend/src/components/` | 3h | 一覧が時刻の昇順で表示される。有効／無効がその場で切り替わる。削除は確認で確定したときだけ行われる。最終実行の結果と失敗した機器が分かる。「データがありません」が出る。テストがある |
| T-015 | 定期実行入力（モーダル）: 実行条件（ラジオ）、曜日（チップ。チェックの記号つき）、時刻（`HH:MM`）、一括切替（5 種）、有効／無効、送信前の検証、登録と変更。背景では閉じない | REQ-008 / ui-design.md §SCR-002（定期実行入力）、design.md §フロントエンド設計（バリデーション） | `src/features/room/frontend/src/components/`、`src/features/room/frontend/src/pages/` | 3h | 登録と変更ができ、保存後に一覧が更新される。曜日の指定で 1 つ以上を選ばないと送信できず、時刻の形式が不正でも送信できない（理由が示される）。選択肢に玄関ドアの施錠・開錠がない。テストがある |
| T-016 | nginx と配置: `nginx.example.conf`、`vite build`、公開 URL `/portal_room/`、ディスク配置 `features/room/` | REQ-001 / design.md §全体構成、`rules/17-nginx-deploy.md` | `src/features/room/frontend/` | 1h | `dist` を配置して、公開 URL `/portal_room/` と `/portal_room/schedules`（直接開いたとき）が表示される。スラッシュなしの `/portal_room` が `/portal_room/` へ 301 される |

### 運用・結合・改訂

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-017 | 機能マスタへの `room` の登録（識別子 `room`、タイトル、遷移先 URL `/portal_room/`、アイコン）とメニュー割当の手順の確定 | REQ-011（認証）/ design.md §未決事項、db-design.md §public.features・public.menu_assignments | 手順書（`src/features/room/README.md`） | 1h | 手順書のとおりに、`room` がメニューに現れ、メニューから ROOM を開ける。割当のないユーザでは「この機能は利用できません」になる |
| T-018 | `api-key-management` の改訂: 対象機能に `room` を加える（`requirements.md` と `design.md` の「対象機能」の改訂）。承認欄に未承認の行を足し、再承認を受ける。ルールの改訂 | REQ-011 / design.md §ルールの改訂 | `specs/api-key-management/` | 2h | `specs/api-key-management/` の要件・設計の対象機能に `room` が含まれ、再承認されている。`room` の API が API キーで利用できる（T-003 の結合確認） |
| T-019 | 実機での結合確認（SwitchBot の実機、開発用 DB）。間接照明・屋内スピーカー・枕元スピーカーの ON／OFF、一括切替 5 種、玄関ドアの施錠（`lock`）と開錠（`unlock`）、状態値（`unlocked`、施錠が不完全な状態）の確認、定期実行の実行、API キーでの利用 | REQ-001〜REQ-012 / api-design.md §未決事項 | `src/features/room/tests/`（実機用は通常のテストから分ける）、確認結果を `README.md` に記す | 3h | 玄関ドアの `lock`／`unlock` と、状態の値が実機で確認される（利用者の立ち会いで行う）。5 種の一括切替が実機で動く。定期実行ジョブが、登録した時刻に 1 回だけ実行される。結果が `README.md` に残る |
| T-020 | 運用手順の整備: 定期実行ジョブのタスクスケジューラへの登録（毎分起動）、`.env` の項目、起動・停止、ログの場所、トラブルの切り分け | REQ-009 / design.md §未決事項 | `src/features/room/README.md` | 1h | 手順書のとおりに、タスクスケジューラへジョブを登録でき、毎分の起動で定期実行が動く。`.env` の項目が漏れなく記載されている |

## 要件トレーサビリティ

| 要件 | タスク |
|------|--------|
| REQ-001 | T-004、T-010、T-011、T-012、T-016、T-019 |
| REQ-002 | T-011、T-013 |
| REQ-003 | T-004、T-012 |
| REQ-004 | T-005、T-012 |
| REQ-005 | T-005、T-012 |
| REQ-006 | T-004、T-005、T-011 |
| REQ-007 | T-006、T-013 |
| REQ-008 | T-002、T-007、T-014、T-015 |
| REQ-009 | T-002、T-008、T-020 |
| REQ-010 | T-002、T-007、T-008、T-014 |
| REQ-011 | T-003、T-005、T-006、T-007、T-017、T-018 |
| REQ-012 | T-001、T-004、T-005、T-006、T-009、T-019 |
| REQ-013 | T-001、T-008、T-009 |

## 範囲外（別の SPEC で扱う）

- MCP サーバへのツール追加: ROOM の実装が終わったあとに、`mcp` 側の SPEC（`requirements.md`、`design.md`、`tool-design.md`）を改訂して扱う。
- 電灯の実際の制御、屋内状態（温度・湿度）の表示: 後日の要件で扱う。

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-10-01 10:18 | 未承認 | 初版 |
| 2026-10-01 10:19 | 承認済み | 初版を承認 |
