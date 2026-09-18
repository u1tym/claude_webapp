# タスク: schedule（スケジュール管理）

## 概要

対象機能: `schedule`

ソース配置:

- フロントエンド: `src/features/schedule/frontend`
- バックエンド: `src/features/schedule/backend`
- テスト: `src/features/schedule/tests`

関連要件:

- REQ-001 〜 REQ-040

`portal` の Python は import しない。`public` の表は読むだけ（複製しない）。業務表はスキーマ `schedule`。本機能の機能マスタ登録と利用者への割当は、`portal` の運用コマンドで行う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`）
- `.cursor/rules/16-logging.mdc`

### 実装パス

- `src/features/schedule/backend/app/main.py`
- `src/features/schedule/backend/app/config.py`
- `src/features/schedule/backend/app/logger.py`
- `src/features/schedule/backend/.env`（ひな型: `docs/specs/templates/backend.env.example`）
- `src/features/schedule/backend/requirements.txt`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB、CORS、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジン、資格情報付き。起動時に `log/` へサイズローテーションするロガーを初期化する。`portal` を import しない。秘密情報をソースに直書きしない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8002` が起動できる
- [ ] `LOG_MAX_BYTES` と `LOG_BACKUP_COUNT` を `.env` から読む
- [ ] 秘密情報をソースに直書きしていない

---

## タスク 2

### タイトル

スキーマ `schedule` の DDL を用意し、適用する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-011, REQ-014, REQ-015, REQ-017, REQ-028

### 関連設計

- `db-design.md` / テーブル設計（`categories`, `schedules`, `preferences`, `hidden_categories`, `user_holidays`）
- `design.md` / バックエンド設計 / モジュール構成（`sql/`）
- `.cursor/rules/13-db.mdc`

### 実装パス

- `src/features/schedule/backend/sql/`

### 内容

スキーマ `schedule` と業務表を作る SQL を置く。部分一意、検査制約、外部キー、インデックスは `db-design.md` どおり。`public` の表は作らない（`portal` が持つ）。`tstuser` がスキーマを使えるようにする。

### 完了条件

- [ ] `db-design.md` の表・制約・インデックスが SQL にある
- [ ] `tstuser` で tstdb に適用できる
- [ ] `public` に業務表を増やしていない

---

## タスク 3

### タイトル

DB 接続とデータアクセスを実装する

### 見積もり

4時間

### 関連要件

- REQ-001, REQ-002

### 関連設計

- `design.md` / バックエンド設計 / データアクセス
- `db-design.md` / テーブル設計

### 実装パス

- `src/features/schedule/backend/app/db.py`
- `src/features/schedule/backend/app/` 配下のデータアクセス

### 内容

PostgreSQL へ接続する。スケジュール、カテゴリ、表示設定、非表示カテゴリ、ユーザ休日の取得・追加・更新・論理削除（非表示解除は行削除）を、設計の役割どおりに実装する。`public` のユーザ・セッション・システム設定・機能マスタ・メニュー割当は参照のみ。型ヒントを付ける。

### 完了条件

- [ ] `.env` の接続情報（tstdb / tstuser）で接続できる
- [ ] 各表へのアクセス関数がある（型ヒント付き）
- [ ] 接続情報をソースに直書きしていない
- [ ] `public` の業務表を更新していない

---

## タスク 4

### タイトル

セッション検証、本機能の割当判定、設定取得 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / バックエンド設計 / 認証 / 認可
- `design.md` / バックエンド設計 / モジュール構成（`deps`, `access_service`, `settings`）
- `api-design.md` / 共通 / 認証
- `api-design.md` / GET `/settings`

### 実装パス

- `src/features/schedule/backend/app/security.py`
- `src/features/schedule/backend/app/deps.py`
- `src/features/schedule/backend/app/services/access_service.py`
- `src/features/schedule/backend/app/routers/settings.py`

### 内容

Cookie `session_id` でログイン中ユーザを特定する。未ログイン・期限切れは 401。識別子 `schedule` の割当が無ければ 403。`DEBUG_USER` でも割当を判定する。セッション ID を本文に出さない。GET `/settings` は認証不要で login_url、menu_url、icon_system、icon_back を返す。アイコンは data URL。

運用として、`portal` の運用コマンドで機能 `schedule` を追加し、利用ユーザへ割り当てる。

### 完了条件

- [ ] 未ログインの操作 API が 401「未ログイン」
- [ ] 割当なしの操作 API が 403「権限がありません」
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 本文にセッション ID を含まない
- [ ] 機能マスタに `schedule` があり、利用ユーザへ割り当てられている

---

## タスク 5

### タイトル

カテゴリ API を実装する

### 見積もり

3時間

### 関連要件

- REQ-011, REQ-012, REQ-013, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（カテゴリ）
- `api-design.md` / GET POST `/categories`、PATCH DELETE `/categories/{category_id}`
- `db-design.md` / `schedule.categories`

### 実装パス

- `src/features/schedule/backend/app/services/category_service.py`
- `src/features/schedule/backend/app/routers/categories.py`
- `src/features/schedule/tests/`

### 内容

本人のカテゴリ一覧（`include_deleted`）。追加は名称と色。更新は未削除の名称と色。削除は論理削除し、スケジュールの `category_id` は変えない。未削除名称の重複は 409。空名称・色形式不正は 400。他ユーザ・既削除は 404。操作の入力・判断・失敗理由をログへ出す。

### 完了条件

- [ ] GET が本人分のみ。省略時は未削除のみ
- [ ] POST で追加でき、未削除の名称重複は 409
- [ ] PATCH で名称と色を更新できる。削除済みは 404
- [ ] DELETE で論理削除。紐づくスケジュールは残る
- [ ] 成功は INF、想定内の失敗は WRN

---

## タスク 6

### タイトル

表示設定 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-014, REQ-015, REQ-017, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（表示設定）
- `api-design.md` / GET PUT `/preferences`
- `db-design.md` / `schedule.preferences`、`schedule.hidden_categories`

### 実装パス

- `src/features/schedule/backend/app/services/preference_service.py`
- `src/features/schedule/backend/app/routers/preferences.py`
- `src/features/schedule/tests/`

### 内容

GET は行が無ければ初期値（日曜始まり、削除済みを出さない、非表示なし）。PUT は週の開始、削除済み表示、非表示カテゴリ ID の集合を保存する。他ユーザのカテゴリ ID は 400。操作をログへ出す。

### 完了条件

- [ ] GET が初期値または保存済みを返す
- [ ] PUT で保存でき、再 GET で維持される
- [ ] 不正な `week_starts_on` や他ユーザのカテゴリ ID は 400
- [ ] 操作がログに残る

---

## タスク 7

### タイトル

スケジュール API を実装する

### 見積もり

4時間

### 関連要件

- REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-019, REQ-020, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（スケジュール）
- `api-design.md` / GET POST `/schedules`、PATCH DELETE `/schedules/{schedule_id}`、PATCH `/schedules/{schedule_id}/completion`
- `db-design.md` / `schedule.schedules`

### 実装パス

- `src/features/schedule/backend/app/services/schedule_service.py`
- `src/features/schedule/backend/app/routers/schedules.py`
- `src/features/schedule/tests/`

### 内容

期間重なりの一覧（REQ-019 の順、カテゴリ非表示では落とさない）。追加・更新は種別・粒度・開始終了・カテゴリ必須。TODO 追加は未実施。予定への実施状態変更は 409。終了が開始より前は 400。削除は論理削除。他ユーザは 404。操作をログへ出す。

### 完了条件

- [ ] GET が範囲重なりの本人・未削除のみ、並びが REQ-019
- [ ] POST で追加できる。TODO は未実施。日単位に時刻を付けない
- [ ] PATCH で更新できる。予定↔TODO の実施状態の扱いが設計どおり
- [ ] completion が TODO のみ。予定は 409
- [ ] DELETE で論理削除。カレンダー対象外になる
- [ ] 操作がログに残る

---

## タスク 8

### タイトル

日本の祝日取得 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-018, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（祝日）
- `api-design.md` / GET `/holidays`

### 実装パス

- `src/features/schedule/backend/app/services/holiday_service.py`
- `src/features/schedule/backend/app/routers/holidays.py`
- `src/features/schedule/tests/`

### 内容

指定期間の日本の国民の祝日と振替休日を、名称付きで返す。実行時に外部の祝日 API は呼ばない。算出は本機能のバックエンド内で行う（ライブラリを使う場合も実行時通信しないものに限る）。日付の昇順。操作の参照はログしてよい。

### 完了条件

- [ ] GET `/holidays` が範囲内の祝日名称を返す
- [ ] 振替休日を含む
- [ ] 実行時に外部ホストへ祝日を取りに行かない
- [ ] クエリ不正は 400

---

## タスク 9

### タイトル

ユーザ休日 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-028, REQ-029, REQ-030, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（ユーザ休日）
- `api-design.md` / GET POST `/user-holidays`、PATCH DELETE `/user-holidays/{user_holiday_id}`
- `db-design.md` / `schedule.user_holidays`

### 実装パス

- `src/features/schedule/backend/app/services/user_holiday_service.py`
- `src/features/schedule/backend/app/routers/user_holidays.py`
- `src/features/schedule/tests/`

### 内容

未削除の一覧（任意の期間、年月日昇順）。追加は年月日と名称。同一ユーザの未削除で年月日重複は 409。日本の祝日と同じ日は許可。更新・論理削除。他ユーザ・既削除は 404。操作をログへ出す。

### 完了条件

- [ ] GET が本人の未削除のみ
- [ ] POST で追加でき、年月日重複は 409、祝日と同じ日は 201
- [ ] PATCH で年月日と名称を更新できる
- [ ] DELETE で論理削除。一覧とカレンダー対象外になる
- [ ] 操作がログに残る

---

## タスク 10

### タイトル

フロントエンドの Vue 起動、殻、ルーティングを用意する

### 見積もり

3時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / フロントエンド設計 / API クライアント
- `ui-design.md` / 共通UI
- `ui-design.md` / 画面遷移
- `api-design.md` / GET `/settings`

### 実装パス

- `src/features/schedule/frontend/`
- `src/features/schedule/frontend/.env`（ひな型: `docs/specs/templates/frontend.env.example`。変数名は `VITE_API_SCHEDULE_URL`）

### 内容

`npm run dev` で起動する。トークンと殻（ヘッダ / ナビ / コンテンツ。PC は左ナビ、スマートフォンは下ナビ）を `15-ui-style.mdc` どおりに置く。`--color-primary` は `#4DA3FF`。ナビは「カレンダー」のみ。ヘッダに戻るとシステムアイコン。Vite `base` は `/portal_schedule/`。パスは `/portal_schedule/`。未ログインは GET `/settings` の login_url へ。割当なしは「この機能を使えません」。API は `VITE_API_SCHEDULE_URL` と credentials のみ。セッション ID をフロントに持たない。他機能の Vue は import しない。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_SCHEDULE_URL` で API を呼び、ホストを直書きしていない
- [ ] 未ログインでログイン画面 URL へ進む
- [ ] セッション ID を `localStorage` や URL に置いていない

---

## タスク 11

### タイトル

月カレンダーのグリッド、月移動、週の開始、日付色、祝日名称を実装する

### 見積もり

4時間

### 関連要件

- REQ-016, REQ-017, REQ-018, REQ-022, REQ-025

### 関連設計

- `ui-design.md` / SCR-001 カレンダー（ツールバー、日セルの日付と名称、日付色）
- `api-design.md` / GET `/preferences`、PUT `/preferences`、GET `/holidays`、GET `/user-holidays`

### 実装パス

- `src/features/schedule/frontend/` のカレンダーページ

### 内容

表示対象月（初期は操作している日の年月）。前月・翌月。週の開始は表示設定に従い、変更は保存する。表示対象月の日がある週だけ出し、週内の前後の日は含む。その月の日が無い週は出さない。土曜日は `--color-primary`、日曜日および日本の祝日・ユーザ休日は `--color-danger`。土曜かつ休日は赤。祝日名称とユーザ休日名称を日セルに出す。ページ全体はスクロールしない。

### 完了条件

- [ ] 年月表示と前月・翌月ができる
- [ ] 日曜始まり／月曜始まりを切り替えられ、再表示しても維持される
- [ ] 土が青、日と休日が赤。土曜の休日は赤
- [ ] 日本の祝日名称とユーザ休日名称が出る

---

## タスク 12

### タイトル

日セルのスケジュール表示、追加・編集、TODO の実施状態を実装する

### 見積もり

4時間

### 関連要件

- REQ-007, REQ-008, REQ-009, REQ-010, REQ-019, REQ-020, REQ-022, REQ-023

### 関連設計

- `ui-design.md` / SCR-001（日セルのスケジュール行、残件、スケジュール入力）
- `api-design.md` / `/schedules`

### 実装パス

- `src/features/schedule/frontend/` のカレンダー日セルとスケジュール入力

### 内容

表示対象スケジュールを REQ-019 の順で日セルへ載せる（カテゴリ非表示と削除済みカテゴリの設定をフロントで適用）。日単位はタイトル、時間単位の開始日は `HH:MM` とタイトル、開始日以外はタイトルのみ。TODO はチェックと取り消し線。カテゴリ色の丸角背景。1 行で幅が収まらなければ末尾を `...`。高さに入りきらない行は日セルに出さず `＋N` へ。PC はクリックで残件（前面。下優先、画面外なら上。ポインタが外れて約 1 秒で閉じる）。日付クリックで追加、行クリックで編集。チェックでは編集を開かない。空入力・終了が開始より前は送らない。成功・失敗はカレンダー直下の 1 行ステータスへ出す。

### 完了条件

- [ ] 並びと日／時間の文言が要件どおり
- [ ] 追加・編集・削除ができる
- [ ] PC で TODO の実施状態を日セルから変えられる
- [ ] `＋N` から残件を参照し、編集できる
- [ ] カテゴリ色の丸角背景が付く
- [ ] 1 行に収まらないタイトルは末尾を `...` にする
- [ ] 成功・失敗でカレンダーの位置が動かない

---

## タスク 13

### タイトル

カテゴリ操作（PC 左カラムとスマートフォンのパネル）を実装する

### 見積もり

3時間

### 関連要件

- REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-021

### 関連設計

- `ui-design.md` / SCR-001（カテゴリ一覧、カテゴリ入力、スマートフォンのカテゴリパネル）
- `api-design.md` / `/categories`、`/preferences`

### 実装パス

- `src/features/schedule/frontend/` のカテゴリ操作

### 内容

一覧、表示／非表示、削除済みの表示切替、追加、名称・色の変更、論理削除。PC は左カラム。スマートフォンは「カテゴリ」からパネル。確認のあと削除。名称空は送らない。非表示と削除済み表示は表示設定として保存し、カレンダーを描き直す。

### 完了条件

- [ ] カテゴリの追加・更新・削除ができる
- [ ] 表示／非表示でカレンダーから消える／戻る
- [ ] 削除済みの表示切替ができる
- [ ] 未削除の名称重複は失敗し、定型文のみ出す

---

## タスク 14

### タイトル

ユーザ休日操作を実装する

### 見積もり

3時間

### 関連要件

- REQ-021, REQ-028, REQ-029, REQ-030

### 関連設計

- `ui-design.md` / SCR-001（日のメニュー、休日入力）
- `api-design.md` / `/user-holidays`

### 実装パス

- `src/features/schedule/frontend/` の休日操作

### 内容

未削除の休日を年月日順で取得する。日セルの右クリック（スマートフォンは長押し）でメニューを出す。ユーザ休日でなければ名称入力のあと追加。ユーザ休日ならその場で論理削除。設定ダイアログに休日一覧は置かない。空は送らない。保存・削除後にカレンダーの名称と日付色を更新する。

### 完了条件

- [ ] 日の右クリックでユーザ休日の追加・削除ができる
- [ ] 設定ダイアログに祝日の一覧・追加が無い
- [ ] カレンダーに名称が出て、日付が赤になる
- [ ] 同一年月日の重複は失敗し、定型文のみ出す
- [ ] 日本の祝日と同じ日でも登録できる

---

## タスク 15

### タイトル

スマートフォン向けの点表示、詳細欄、新規追加を実装する

### 見積もり

4時間

### 関連要件

- REQ-010, REQ-016, REQ-024, REQ-025, REQ-026

### 関連設計

- `ui-design.md` / SCR-001 スマートフォン
- `ui-design.md` / レスポンシブ

### 実装パス

- `src/features/schedule/frontend/` のスマートフォン向けカレンダーと詳細

### 内容

768px 未満では日セルは日付とカテゴリ色の点。日付選択で詳細を出し、出しきれないときは詳細内スクロール。詳細から実施状態は変えない。編集で変える。右下の円形「＋」で追加。ページ全体はスクロールしない。

### 完了条件

- [ ] 日付選択前は詳細が出ない。選択後に出る
- [ ] 点表示がある日と無い日が分かる
- [ ] 詳細の文言が要件どおり。TODO のその場変更が無い
- [ ] 「＋」と詳細タップで追加・編集できる

---

## タスク 16

### タイトル

ルーチン表とスケジュールの `routine_id` の DDL を追加し、適用する

### 見積もり

2時間

### 関連要件

- REQ-004, REQ-031, REQ-032

### 関連設計

- `db-design.md` / テーブル設計（`routines`, `routine_months`, `routine_exclusions`, `schedules.routine_id`）
- `design.md` / バックエンド設計 / モジュール構成（`sql/`）

### 実装パス

- `src/features/schedule/backend/sql/`

### 内容

`routines`、`routine_months`、`routine_exclusions` を作る。`schedules` に `routine_id`（NULL 可、既定 NULL、外部キー）と部分インデックスを足す。検査制約は `db-design.md` どおり。既存のスケジュール行は `routine_id` が NULL のまま。`public` の表は変えない。適用手順は既存の SQL 適用に合わせる。

### 完了条件

- [ ] `db-design.md` のルーチン関連の表・制約・インデックスが SQL にある
- [ ] 既存の `schedules` に `routine_id` が付き、既存行は NULL
- [ ] `tstuser` で tstdb に適用できる
- [ ] `public` に業務表を増やしていない

---

## タスク 17

### タイトル

ルーチンと `routine_id` 付きスケジュールのデータアクセスを実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-004, REQ-007, REQ-008, REQ-031, REQ-032

### 関連設計

- `design.md` / バックエンド設計 / データアクセス
- `db-design.md` / `schedule.routines`、`schedule.routine_months`、`schedule.routine_exclusions`、`schedule.schedules.routine_id`

### 実装パス

- `src/features/schedule/backend/app/repos.py`
- `src/features/schedule/backend/app/services/schedule_service.py`

### 内容

ルーチンの未削除一覧、ID 取得、追加（反映月・除外対象を含む）、論理削除を実装する。スケジュールは `routine_id` を読み書きできる。手入力追加では `routine_id` を NULL にする。更新では `routine_id` を変えない。指定ユーザ・指定ルーチン・指定年月の開始日を持つ未削除の有無を確認できる。型ヒントを付ける。

### 完了条件

- [ ] ルーチンの一覧・追加・論理削除のアクセス関数がある
- [ ] GET `/schedules` の応答に `routine_id` が含まれる（無いときは `null`）
- [ ] POST `/schedules` が `routine_id` を付けない
- [ ] PATCH `/schedules/{schedule_id}` が `routine_id` を変えない
- [ ] 指定年月かつ指定 `routine_id` の未削除有無を確認できる

---

## タスク 18

### タイトル

ルーチンの一覧・追加・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-031, REQ-032, REQ-033, REQ-034, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（ルーチン）
- `api-design.md` / GET POST `/routines`、DELETE `/routines/{routine_id}`
- `db-design.md` / `schedule.routines`、`schedule.routine_months`、`schedule.routine_exclusions`

### 実装パス

- `src/features/schedule/backend/app/services/routine_service.py`
- `src/features/schedule/backend/app/routers/routines.py`
- `src/features/schedule/tests/`

### 内容

未削除一覧（タイトル昇順）。追加は必須項目と適用日タイプに応じた項目、反映月 1 件以上、除外調整が有なら除外 1 件以上とずらしかた。カテゴリは本人の未削除のみ。削除は論理削除し、スケジュールの `routine_id` は変えない。入力不正は 400。他ユーザ・既削除は 404。操作をログへ出す。

### 完了条件

- [ ] GET が本人の未削除のみ
- [ ] POST で追加でき、識別が付く。必須欠落は 400
- [ ] 日付指定／曜日指定の項目組合せが不正なら 400
- [ ] DELETE で論理削除。紐づくスケジュールは残る
- [ ] 成功は INF、想定内の失敗は WRN

---

## タスク 19

### タイトル

ルーチン適用の基準日と適用日の算出を実装する

### 見積もり

3時間

### 関連要件

- REQ-038, REQ-039

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（基準日・除外調整）
- `db-design.md` / テーブルなし（算出）
- `api-design.md` / 適用 API の処理概要

### 実装パス

- `src/features/schedule/backend/app/services/routine_service.py`
- `src/features/schedule/tests/`

### 内容

指定年月と適用日タイプから基準日を決める。月末日、毎月 X 日（その月に無い日は無し）、N 番目の曜日、最終から N 番目の曜日。除外調整が有なら、祝日（`holiday_service`）と選んだ曜日に当たるあいだ 1 日ずつずらす。31 日上限。ユーザ休日は含めない。単体で確認する。

### 完了条件

- [ ] 月末日・毎月 X 日・第 N 曜日・最終から N 番目が設計どおり
- [ ] その月に存在しない日・第 N 曜日は基準日なし
- [ ] 除外調整の前ずらし・後ずらしができる。祝日除外は日本の祝日
- [ ] 31 日ずらしても除外なら適用日なし
- [ ] 実行時に外部ホストへ祝日を取りに行かない

---

## タスク 20

### タイトル

ルーチンの指定年月への適用 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-036, REQ-037, REQ-038, REQ-039, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（適用）
- `api-design.md` / POST `/routines/{routine_id}/apply`、POST `/routines/apply-all`

### 実装パス

- `src/features/schedule/backend/app/services/routine_service.py`
- `src/features/schedule/backend/app/routers/routines.py`
- `src/features/schedule/tests/`

### 内容

1 件適用と一括適用。指定年月の月が反映月に無い、同一 `routine_id` が指定年月の開始日として既にある、基準日／適用日なし、カテゴリが使えない、ときは登録せず 200（`items` は空または他件のみ）。作るスケジュールは日単位、開始＝終了＝適用日、`routine_id` 付き。TODO は未実施。一括は未削除すべてを独立に処理。操作と登録しなかった理由をログへ出す。

### 完了条件

- [ ] 1 件適用でスケジュールが作れ、`routine_id` が付く
- [ ] 同じ年月へ再適用すると登録せず 200
- [ ] 反映月外は登録しない
- [ ] 一括適用で、ある件が登録しなくても他件を続ける
- [ ] `year` / `month` 不正は 400。無いルーチンは 404
- [ ] 操作がログに残る

---

## タスク 21

### タイトル

設定ダイアログのルーチン一覧・追加・削除・適用を実装する

### 見積もり

4時間

### 関連要件

- REQ-021, REQ-033, REQ-034, REQ-035, REQ-036, REQ-037

### 関連設計

- `ui-design.md` / SCR-001（設定ダイアログ、ルーチン入力）
- `api-design.md` / `/routines`

### 実装パス

- `src/features/schedule/frontend/` の設定ダイアログとルーチン入力

### 内容

設定ダイアログに Routines 一覧を置く。新規でルーチン入力を開く。行選択と Apply、Apply all。適用する年月の初期値は表示対象月（カレンダーの月は変えない）。削除は確認のあと。送信前に必須と項目組合せを確認する。成功なら一覧とカレンダーを読み直す。設定ダイアログは残す。文言は英語。外側クリックでは閉じない。ルーチン識別は出さない。

### 完了条件

- [ ] 設定からルーチン一覧・追加・削除ができる
- [ ] 選んだ 1 件の適用と全件適用ができる
- [ ] 適用する年月を指定でき、カレンダーの表示月は変えない
- [ ] 必須欠落は送らない
- [ ] PC とスマートフォンで同じ設定ダイアログから操作できる

---

## タスク 22

### タイトル

ルーチンの更新 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-032, REQ-040, REQ-027

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（ルーチン更新）
- `api-design.md` / PATCH `/routines/{routine_id}`
- `db-design.md` / `schedule.routines`、`schedule.routine_months`、`schedule.routine_exclusions`

### 実装パス

- `src/features/schedule/backend/app/repos.py`
- `src/features/schedule/backend/app/services/routine_service.py`
- `src/features/schedule/backend/app/routers/routines.py`
- `src/features/schedule/tests/`

### 内容

未削除かつ本人のルーチンの項目を更新する。検証は追加と同じ。反映月と除外対象は置き換える。紐づくスケジュールは変えない。識別は変えない。入力不正は 400。他ユーザ・既削除は 404。操作をログへ出す。

### 完了条件

- [ ] PATCH で項目を更新できる
- [ ] 必須欠落・項目組合せ不正は 400
- [ ] 紐づくスケジュールの内容と `routine_id` は変わらない
- [ ] 無い／論理削除済み／他ユーザは 404
- [ ] 成功は INF、想定内の失敗は WRN

---

## タスク 23

### タイトル

設定ダイアログのルーチン編集・適用年月ダイアログ・横スクロール解消を実装する

### 見積もり

3時間

### 関連要件

- REQ-035, REQ-036, REQ-037, REQ-040

### 関連設計

- `ui-design.md` / SCR-001（設定ダイアログ、ルーチン入力、適用する年月）
- `api-design.md` / PATCH `/routines/{routine_id}`、適用 API

### 実装パス

- `src/features/schedule/frontend/` の設定ダイアログとルーチン入力

### 内容

一覧に編集アイコンを置く（削除へ寄せる）。編集は対象の項目でルーチン入力を開く。見出しは「Edit routine」。保存は更新。Apply / Apply all は一覧に年月を出さず、押すと適用する年月ダイアログを出す。初期値は表示対象月。実行はダイアログの「Apply」。設定ダイアログは残す。設定ダイアログとルーチン入力は横方向にスクロールしない。タイトルが長いときは省略する。

### 完了条件

- [ ] 一覧から編集でき、保存すると一覧が更新される
- [ ] 設定の Routines に年月は出ない
- [ ] Apply / Apply all で年月指定が出て、実行すると適用する
- [ ] カレンダーの表示月は変えない
- [ ] 設定ダイアログとルーチン入力に横スクロールが出ない
- [ ] PC とスマートフォンで同じ操作ができる

---

## タスク 24

### タイトル

スケジュールとルーチンに `needs_notification` の DDL を追加し、適用する

### 見積もり

1時間

### 関連要件

- REQ-004, REQ-032

### 関連設計

- `db-design.md` / `schedule.schedules`、`schedule.routines`（`needs_notification`）
- `design.md` / バックエンド設計 / モジュール構成（`sql/`）

### 実装パス

- `src/features/schedule/backend/sql/`

### 内容

`schedules` と `routines` に `needs_notification`（boolean、NOT NULL、既定 false）を足す。既存行は false。`CREATE TABLE IF NOT EXISTS` では列は増えないため、`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` とする。`public` の表は変えない。適用手順は既存の SQL 適用に合わせる。

### 完了条件

- [ ] `schedules.needs_notification` と `routines.needs_notification` がある
- [ ] 既存行は false
- [ ] `tstuser` で tstdb に適用できる
- [ ] `public` に業務表を増やしていない

---

## タスク 25

### タイトル

スケジュールとルーチンの API に `needs_notification` を載せる

### 見積もり

3時間

### 関連要件

- REQ-004, REQ-007, REQ-008, REQ-027, REQ-032, REQ-033, REQ-036, REQ-040

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `/schedules`、`/routines`、適用 API
- `db-design.md` / `needs_notification`

### 実装パス

- `src/features/schedule/backend/app/repos.py`
- `src/features/schedule/backend/app/services/schedule_service.py`
- `src/features/schedule/backend/app/services/routine_service.py`
- `src/features/schedule/backend/app/routers/schedules.py`
- `src/features/schedule/backend/app/routers/routines.py`
- `src/features/schedule/tests/`

### 内容

GET/POST/PATCH `/schedules` と GET/POST/PATCH `/routines` に `needs_notification` を載せる。必須。真偽でないときは 400。適用で作るスケジュールにはルーチンの値を入れる。手入力追加でも受け付ける。更新で変えられる。ルーチン識別は変えない。操作ログに入力値を残す。

### 完了条件

- [ ] スケジュールの応答に `needs_notification` がある
- [ ] POST/PATCH `/schedules` で要／不要を保存・更新できる。欠落または真偽でないときは 400
- [ ] ルーチンの応答に `needs_notification` がある
- [ ] POST/PATCH `/routines` で要／不要を保存・更新できる。欠落または真偽でないときは 400
- [ ] 適用で作ったスケジュールの `needs_notification` はルーチンの値である
- [ ] 成功は INF、想定内の失敗は WRN。入力に `needs_notification` が含まれる

---

## タスク 26

### タイトル

スケジュール入力とルーチン入力に「Notify」を実装する

### 見積もり

2時間

### 関連要件

- REQ-004, REQ-007, REQ-008, REQ-032, REQ-033, REQ-040

### 関連設計

- `ui-design.md` / スケジュール入力、ルーチン入力
- `api-design.md` / `needs_notification`

### 実装パス

- `src/features/schedule/frontend/src/api.ts`
- `src/features/schedule/frontend/src/views/CalendarView.vue`

### 内容

スケジュール入力の種別の下に「Notify」チェックを置く。オンは要、オフは不要。追加時はオフ。編集時は対象の値。保存時に送る。ルーチン入力も同じ。カレンダーの日セルと詳細には出さない。

### 完了条件

- [ ] スケジュールの追加・編集で Notify を切替でき、保存できる
- [ ] ルーチンの追加・編集で Notify を切替でき、保存できる
- [ ] 追加時の初期値はオフ
- [ ] カレンダーの日セルと詳細に Notify は出ない

---

## テスト

### 単体テスト

- [ ] `src/features/schedule/tests/` に配置する
- [ ] 開始終了の前後、日単位／時間単位、種別と実施状態、カテゴリ名称重複、ユーザ休日の年月日重複、並び順、期間重なりを確認する
- [ ] 祝日算出が外部通信しないこと、振替休日を含むことを確認する
- [ ] ルーチンの適用日タイプ、基準日、除外調整のずらし、指定年月の同一 `routine_id` では登録しないことを確認する
- [ ] スケジュールとルーチンの `needs_notification`、適用時の転記を確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、409、settings、期間取得、ルーチンの追加・更新・削除・適用）
- [ ] 操作ログ（入力・判断・失敗理由、セッション ID 非出力）

### 受け入れテスト

- [ ] requirements.md の受け入れ条件を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-27 22:00 | 未承認 | 初版 |
| 2026-08-27 22:03 | 承認済み | 初版を承認 |
| 2026-08-29 09:37 | 未承認 | Today ボタン削除に合わせて完了条件を更新 |
| 2026-08-29 11:25 | 承認済み | Today ボタン削除に合わせた完了条件の更新を承認 |
| 2026-08-29 19:12 | 未承認 | 公開パスの基点を `/portal_schedule/` にする |
| 2026-08-29 19:19 | 承認済み | 公開パス `/portal_schedule/` の改訂を承認 |
| 2026-08-29 20:17 | 未承認 | 日セルの丸角背景・省略、残件のクリック表示、カレンダー下ステータス |
| 2026-08-29 21:20 | 未承認 | 高さに入りきらないスケジュールは日セルに出さず残件へ |
| 2026-08-29 21:32 | 未承認 | その月の日が無い週は出さない |
| 2026-08-29 22:42 | 未承認 | ユーザ休日は日の右クリックで追加・削除。設定ダイアログから祝日登録を外す |
| 2026-08-29 22:52 | 承認済み | ユーザ休日の日右クリック追加・削除、設定ダイアログから祝日登録を外す変更を承認 |
| 2026-08-29 23:46 | 未承認 | ルーチンの DDL・API・適用算出・設定ダイアログ（タスク 16〜21） |
| 2026-08-29 23:50 | 承認済み | ルーチンのタスク 16〜21 を承認 |
| 2026-08-30 00:17 | 未承認 | ルーチン更新 API と、編集・適用年月ダイアログ・横スクロール解消（タスク 22〜23） |
| 2026-08-30 00:23 | 承認済み | タスク 22〜23 を承認 |
| 2026-08-30 08:02 | 未承認 | 通知要不要（タスク 24〜26）。DDL・API・入力の Notify |
| 2026-08-30 08:04 | 承認済み | タスク 24〜26 を承認 |
