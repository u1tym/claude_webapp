# タスク: expense-management（家計の予算・支出管理）

## 概要

対象機能: `expense-management`

ソース配置:

- フロントエンド: `src/features/expense-management/frontend`
- バックエンド: `src/features/expense-management/backend`
- テスト: `src/features/expense-management/tests`

関連要件:

- REQ-001 〜 REQ-013

`portal` の Python は import しない。`public` の表（ユーザ・セッション・機能マスタ・メニュー割当）は読むだけで複製しない。業務表はスキーマ `expense_management`。本機能の機能マスタ登録と利用者への割当は `portal` の運用コマンドで行う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- 認証の要否（横断）

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`）
- `rules/16-logging.md`

### 実装パス

- `src/features/expense-management/backend/app/main.py`
- `src/features/expense-management/backend/app/config.py`
- `src/features/expense-management/backend/app/logger.py`
- `src/features/expense-management/backend/.env`（ひな型: `specs/templates/backend.env.example`）
- `src/features/expense-management/backend/requirements.txt`

### 内容

venv を `backend` 配下に作成し、uvicorn で起動できるようにする。`.env` から DB 接続情報、CORS、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジンのみ許可し、資格情報付きを許可する。起動時に `log/` へサイズローテーションするロガーを初期化する。`portal` を import しない。秘密情報をソースに直書きしない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload` が起動できる
- [ ] `LOG_MAX_BYTES` と `LOG_BACKUP_COUNT` を `.env` から読む
- [ ] 秘密情報をソースに直書きしていない

---

## タスク 2

### タイトル

Cookie セッション検証と機能利用可否判定を実装する

### 見積もり

3時間

### 関連要件

- 認証の要否（横断）

### 関連設計

- `design.md` / バックエンド設計 / モジュール構成（`app/db.py`, `app/deps.py`, `app/access.py`）
- `design.md` / 認証・認可
- `db-design.md` / `public.users` / `public.sessions` / `public.features` / `public.menu_assignments`
- `api-design.md` / 共通事項 / 認証

### 実装パス

- `src/features/expense-management/backend/app/db.py`
- `src/features/expense-management/backend/app/deps.py`
- `src/features/expense-management/backend/app/access.py`

### 内容

`public.sessions` / `public.users` を参照し、Cookie の `session_id` からログイン中ユーザを特定する依存関数を作る。期限切れ・行が無い・対象ユーザが論理削除済みは未ログイン（401）として扱う。`public.features` / `public.menu_assignments` を参照し、ログイン中ユーザに識別子 `expense-management` の機能が割り当てられ、かつ未削除であることを判定する（不許可は 403）。`DEBUG_USER` 指定時は認証をスキップし、指定ユーザとして判定する。`portal` の API は呼ばない。

### 完了条件

- [ ] Cookie が無い、期限切れ、対象ユーザ論理削除済みのいずれも 401 になる
- [ ] `expense-management` が未割当、または本機能が論理削除済みのとき 403 になる
- [ ] `DEBUG_USER` 設定時は Cookie なしで指定ユーザとして処理される
- [ ] `portal` の Python モジュールを import していない

---

## タスク 3

### タイトル

スキーマ `expense_management` の DDL を作成する

### 見積もり

2時間

### 関連要件

- REQ-001 〜 REQ-013（全体の基盤）

### 関連設計

- `db-design.md` / ER図 / テーブル設計（全表）

### 実装パス

- `src/features/expense-management/backend/sql/`

### 内容

`db-design.md` のテーブル設計どおりに `expense_management` スキーマと、`budget_periods` / `budget_items` / `payment_methods` / `payment_method_exclusions` / `expenses` の DDL を作成する。主キー・外部キー・検査制約・インデックスを `db-design.md` のとおりに定義する。`public` 側のテーブルは作らない（`portal` が作成済み）。

### 完了条件

- [ ] `expense_management` スキーマと5表が作成できる
- [ ] `db-design.md` に記載の検査制約（`closing_day` の範囲、`closing_day = 0` のときの固定値、`amount >= 0` 等）が入っている
- [ ] `db-design.md` に記載のインデックスが入っている

---

## タスク 4

### タイトル

予算期間の一覧・新規作成 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-004

### 関連設計

- `design.md` / バックエンド設計 / `app/routers/budget_periods.py`, `app/services/budget_service.py`
- `api-design.md` / GET `/budget-periods`, POST `/budget-periods`

### 実装パス

- `src/features/expense-management/backend/app/routers/budget_periods.py`
- `src/features/expense-management/backend/app/services/budget_service.py`

### 内容

`GET /budget-periods` は本人の予算期間を `start_date` の新しい順で返す。`POST /budget-periods` は開始日・終了日を受け付け、`end_date < start_date` を 400、本人の既存の予算期間と期間が重なる場合を 409 とする。重複チェックはアプリケーション側（`budget_service`）で行う。

### 完了条件

- [ ] 一覧が `start_date` の新しい順で返る
- [ ] 終了日が開始日より前のとき 400 になる
- [ ] 期間が重なるとき 409 になる
- [ ] 他人の予算期間が一覧に出ない

---

## タスク 5

### タイトル

予算期間の複製作成 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-002

### 関連設計

- `design.md` / バックエンド設計 / `app/services/budget_service.py`
- `api-design.md` / POST `/budget-periods/{budget_period_id}/duplicate`

### 実装パス

- `src/features/expense-management/backend/app/routers/budget_periods.py`
- `src/features/expense-management/backend/app/services/budget_service.py`

### 内容

指定した予算期間（本人所有）を複製元として新しい予算期間を作成し、複製元の未削除の予算項目（項目名・金額・表示順）を新しい `id` でコピーする。複製元が本人の予算期間でないとき 404、期間重複は 409。

### 完了条件

- [ ] 複製元の予算項目が新しい予算期間へコピーされる（新しい `id` を持つ）
- [ ] コピー後の予算項目は複製元と独立して編集できる
- [ ] 複製元が他人の予算期間のとき 404 になる

---

## タスク 6

### タイトル

予算項目の一覧・登録・編集・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-003, REQ-004

### 関連設計

- `design.md` / バックエンド設計 / `app/routers/budget_items.py`
- `db-design.md` / `expense_management.budget_items`
- `api-design.md` / GET/POST `/budget-items`, PATCH/DELETE `/budget-items/{budget_item_id}`

### 実装パス

- `src/features/expense-management/backend/app/routers/budget_items.py`
- `src/features/expense-management/backend/app/services/budget_service.py`

### 内容

指定した予算期間（本人所有）に属する未削除の予算項目を `display_order` 昇順で返す。登録・編集は項目名（空不可）・金額（0以上）・表示順を検査する。削除は論理削除とし、既存の支出記録が参照する `budget_item_id` は変えない。

### 完了条件

- [ ] 一覧が `display_order` 昇順で返る。削除済みは含まない
- [ ] 項目名が空、金額が負のとき 400 になる
- [ ] 削除は論理削除であり、既存の支出記録の `budget_item_id` に影響しない
- [ ] 他人の予算項目を操作しようとすると 404 になる

---

## タスク 7

### タイトル

実際の締め日・実際の支払日を算出するロジックを実装する

### 見積もり

3時間

### 関連要件

- REQ-013

### 関連設計

- `design.md` / バックエンド設計 / `app/services/closing_date_service.py`
- `db-design.md` / `expense_management.payment_methods`, `expense_management.payment_method_exclusions`

### 実装パス

- `src/features/expense-management/backend/app/services/closing_date_service.py`

### 内容

対象の基準値（締め日または支払日）と、対応する除外条件一覧・ずらし方向を受け取り、実際の日を算出する共通関数を実装する。除外条件（特定の曜日、または当月に存在しない日）のいずれかに一致する間、ずらし方向に従って1日ずつずらし、いずれにも一致しなくなった日を返す。締め日が0のときはこのロジックを使わず、即時支払として扱う。年月をまたぐ月末境界（例: 1月31日締めで2月）も正しく算出できること。

### 完了条件

- [ ] 除外条件に一致しない基準日はそのまま返る
- [ ] 曜日除外・過去方向・未来方向の組み合わせで正しくずれる
- [ ] 「当月に存在しない日」除外で、該当月に存在しない日付が正しくずれる
- [ ] 締め日0のときはこの関数を呼ばない、または即時支払として扱われる

---

## タスク 8

### タイトル

支出方法の一覧・登録・編集・削除 API を実装する

### 見積もり

4時間

### 関連要件

- REQ-005, REQ-006, REQ-007

### 関連設計

- `design.md` / バックエンド設計 / `app/routers/payment_methods.py`, `app/services/payment_method_service.py`
- `db-design.md` / `expense_management.payment_methods`, `expense_management.payment_method_exclusions`
- `api-design.md` / GET/POST `/payment-methods`, PATCH/DELETE `/payment-methods/{payment_method_id}`

### 実装パス

- `src/features/expense-management/backend/app/routers/payment_methods.py`
- `src/features/expense-management/backend/app/services/payment_method_service.py`

### 内容

登録・編集時、`closing_day` が0のときは支払月オフセット・支払日・両ずらし方向を固定値（0, 0, NULL, NULL）にし、除外条件をすべて削除する。`closing_day` が1以上のときは、両ずらし方向の指定を必須とし、除外条件（`target` ごとに0件以上）を登録できる。一覧は `display_order` 昇順、未削除のみ。削除は論理削除とし、既存の支出記録が参照する `payment_method_id` は変えない。

### 完了条件

- [ ] `closing_day = 0` で登録すると、支払月オフセット・支払日・両ずらし方向が固定値になり、除外条件が保存されない
- [ ] `closing_day` が1以上で、ずらし方向未指定、または `payment_day` が範囲外のとき 400 になる
- [ ] 除外条件が `target`（`closing_day`/`payment_day`）ごとに登録・編集・削除できる
- [ ] 一覧が `display_order` 昇順で返る。削除済みは含まない
- [ ] 削除は論理削除であり、既存の支出記録の `payment_method_id` に影響しない

---

## タスク 9

### タイトル

支払日算出プレビュー API を実装する

### 見積もり

1時間

### 関連要件

- REQ-013

### 関連設計

- `design.md` / バックエンド設計 / `app/services/expense_service.py`, `app/services/closing_date_service.py`
- `api-design.md` / GET `/payment-methods/{payment_method_id}/estimated-payment-date`

### 実装パス

- `src/features/expense-management/backend/app/routers/payment_methods.py`

### 内容

指定した支出方法と利用日から、`closing_date_service` を用いて実際の締め日・支払月オフセット・実際の支払日を組み合わせ、支払日を算出して返す。締め日0の支出方法は利用日をそのまま返す。

### 完了条件

- [ ] 締め日が1以上の支出方法で、利用日に応じた支払日が正しく算出される
- [ ] 締め日0の支出方法では利用日がそのまま返る
- [ ] 本人の未削除の支出方法でないとき 404 になる

---

## タスク 10

### タイトル

支出記録の一覧・登録・編集・削除 API を実装する

### 見積もり

4時間

### 関連要件

- REQ-008, REQ-009, REQ-010

### 関連設計

- `design.md` / バックエンド設計 / `app/routers/expenses.py`, `app/services/expense_service.py`
- `db-design.md` / `expense_management.expenses`
- `api-design.md` / GET/POST `/expenses`, PATCH/DELETE `/expenses/{expense_id}`

### 実装パス

- `src/features/expense-management/backend/app/routers/expenses.py`
- `src/features/expense-management/backend/app/services/expense_service.py`

### 内容

利用日の範囲で一覧を返す（削除フラグが立っていないもののみ、利用日の新しい順）。登録・編集は `budget_item_id` が本人の未削除の予算項目、`payment_method_id` が本人の未削除の支出方法であることを検査する。`created_at` は登録時にシステムが設定し、以後変えない。`payment_date` は要求で受け取った値をそのまま保存する（算出はフロントがタスク9の API を用いて行う）。削除は削除フラグを立てる論理削除とする。

### 完了条件

- [ ] 利用日の範囲指定で一覧が取得でき、削除済みは含まれない
- [ ] `budget_item_id` / `payment_method_id` が本人の未削除のものでないとき 400 になる
- [ ] `created_at` は登録時のみ設定され、更新では変わらない
- [ ] 削除は論理削除であり、一覧に出なくなる

---

## タスク 11

### タイトル

予算対実績の集計 API（利用日基準・支払発生月基準）を実装する

### 見積もり

3時間

### 関連要件

- REQ-011, REQ-012

### 関連設計

- `design.md` / バックエンド設計 / `app/routers/reports.py`, `app/services/report_service.py`
- `api-design.md` / GET `/reports/usage-date`, GET `/reports/payment-month`

### 実装パス

- `src/features/expense-management/backend/app/routers/reports.py`
- `src/features/expense-management/backend/app/services/report_service.py`

### 内容

利用日基準は、指定した予算期間に属する予算項目ごとに、その予算期間内の利用日を持つ削除されていない支出記録を合計し、予算金額・支出合計・差額を返す。支払発生月基準は、指定した年月と支払日の年月が一致する削除されていない支出記録を `budget_item_id` ごとに合計して返す。

### 完了条件

- [ ] 利用日基準で、予算項目ごとの予算金額・支出合計・差額が正しく算出される
- [ ] 支払発生月基準で、指定年月に支払日が属する支出記録だけが集計される
- [ ] いずれも削除フラグが立っている支出記録を含まない
- [ ] 本人以外の予算期間・支出記録を含まない

---

## タスク 12

### タイトル

フロントエンドの起動口・ルータ・共通レイアウト・API クライアントを用意する

### 見積もり

3時間

### 関連要件

- 認証の要否（横断）

### 関連設計

- `design.md` / フロントエンド設計
- `rules/15-ui-style.md`
- `rules/17-nginx-deploy.md`

### 実装パス

- `src/features/expense-management/frontend/`

### 内容

`npm run dev` で起動できるようにする。Vite `base` は `/portal_expense_management/`。Vue Router に `/`（支出記録）・`/budgets`（予算管理）・`/payment-methods`（支出方法管理）・`/reports`（集計）を登録する。`rules/15-ui-style.md` のトークンと殻（ヘッダ、PCは左ナビ、スマートフォンは下ナビ）を実装する。`--color-primary` は機能ごとのパレットから1色選ぶ。ナビは4画面。API クライアントは `VITE_API_EXPENSE_MANAGEMENT_URL` を基点にし、Cookie を含めて通信する。セッション ID はフロントに保持しない。他機能の Vue / CSS は import しない。

### 完了条件

- [ ] `npm run dev` で起動し、4画面へルーティングできる
- [ ] ヘッダ / ナビの殻が `rules/15-ui-style.md` どおりに表示される
- [ ] API クライアントが `VITE_API_EXPENSE_MANAGEMENT_URL` を使い、Cookie を送信する
- [ ] 他機能の Vue / CSS / コンポーネントを import していない

---

## タスク 13

### タイトル

支出記録画面（SCR-001）を実装する

### 見積もり

4時間

### 関連要件

- REQ-008, REQ-009, REQ-010, REQ-013

### 関連設計

- `ui-design.md` / SCR-001: 支出記録
- `api-design.md` / GET/POST `/expenses`, PATCH/DELETE `/expenses/{expense_id}`, GET `/payment-methods/{id}/estimated-payment-date`

### 実装パス

- `src/features/expense-management/frontend/`

### 内容

予算期間選択、支出記録一覧（利用日の新しい順）、新規登録・編集フォームを実装する。フォームで利用日または支出方法を変更するたびに支払日算出プレビュー API を呼び、支払日欄を更新する。ユーザは支払日を手入力で修正できる。削除は確認のうえ実行する。読込中・空・エラーの表示は `ui-design.md` の状態別表示に従う。

### 完了条件

- [ ] 支出記録の登録・編集・削除ができる
- [ ] 利用日・支出方法の変更で支払日欄が自動更新され、手入力でも修正できる
- [ ] 削除確認後、一覧から対象が消える
- [ ] 読込中・空・エラーの表示が `ui-design.md` のとおり

---

## タスク 14

### タイトル

予算管理画面（SCR-002）を実装する

### 見積もり

4時間

### 関連要件

- REQ-001, REQ-002, REQ-003, REQ-004

### 関連設計

- `ui-design.md` / SCR-002: 予算管理
- `api-design.md` / `/budget-periods`, `/budget-periods/{id}/duplicate`, `/budget-items`

### 実装パス

- `src/features/expense-management/frontend/`

### 内容

予算期間一覧、新規作成フォーム、複製作成フォーム、選択中の予算期間に属する予算項目一覧（表示順）と登録・編集・削除フォームを実装する。期間重複時のエラー表示を行う。

### 完了条件

- [ ] 予算期間の新規作成・複製作成ができる
- [ ] 予算項目の登録・編集・削除ができ、表示順に並ぶ
- [ ] 期間重複時にフォーム先頭へエラーメッセージが表示される
- [ ] 読込中・空・エラーの表示が `ui-design.md` のとおり

---

## タスク 15

### タイトル

支出方法管理画面（SCR-003）を実装する

### 見積もり

4時間

### 関連要件

- REQ-005, REQ-006, REQ-007

### 関連設計

- `ui-design.md` / SCR-003: 支出方法管理
- `api-design.md` / `/payment-methods`

### 実装パス

- `src/features/expense-management/frontend/`

### 内容

支出方法一覧（表示順）、登録・編集フォームを実装する。締め日に0を指定すると、支払月オフセット・支払日・ずらし方向・除外条件の入力欄を非表示にする。締め日が1以上のとき、締め日用・支払日用それぞれのずらし方向と、除外条件（特定の曜日／当月に存在しない日）の追加・削除 UI を実装する。

### 完了条件

- [ ] 締め日0で以降の項目が非表示になり、登録できる
- [ ] 締め日1以上で、ずらし方向・除外条件を含めて登録・編集・削除できる
- [ ] 除外条件を追加・削除できる
- [ ] 一覧が表示順で表示される

---

## タスク 16

### タイトル

集計画面（SCR-004）を実装する

### 見積もり

3時間

### 関連要件

- REQ-011, REQ-012

### 関連設計

- `ui-design.md` / SCR-004: 集計
- `api-design.md` / GET `/reports/usage-date`, GET `/reports/payment-month`

### 実装パス

- `src/features/expense-management/frontend/`

### 内容

利用日基準・支払発生月基準の切替、予算期間選択（利用日基準）・年月選択（支払発生月基準）、予算項目ごとの集計一覧を実装する。

### 完了条件

- [ ] 利用日基準で予算金額・支出合計・差額が表示される
- [ ] 支払発生月基準で支出合計が表示される
- [ ] 基準の切替ができる
- [ ] 読込中・空・エラーの表示が `ui-design.md` のとおり

---

## タスク 17

### タイトル

予算期間の更新 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-014

### 関連設計

- `design.md` / バックエンド設計 / `app/routers/budget_periods.py`, `app/services/budget_service.py`
- `api-design.md` / PATCH `/budget-periods/{budget_period_id}`
- `db-design.md` / `expense_management.budget_periods`

### 実装パス

- `src/features/expense-management/backend/app/repos.py`
- `src/features/expense-management/backend/app/routers/budget_periods.py`
- `src/features/expense-management/backend/app/services/budget_service.py`
- `src/features/expense-management/tests/`

### 内容

`PATCH /budget-periods/{budget_period_id}` を追加する。タイトル・開始日・終了日を受け付けて更新する。`title` が空、または `end_date` が `start_date` より前なら 400。対象が本人の予算期間でない、または存在しないなら 404。期間重複チェックは行わない。`id`・`user_id` は変えない。

### 完了条件

- [ ] PATCH でタイトル・開始日・終了日を更新できる
- [ ] 終了日が開始日より前のとき 400 になる
- [ ] 他人の予算期間、または存在しない ID のとき 404 になる
- [ ] 更新後の期間が既存の予算期間と重なっていても保存できる

---

## タスク 18

### タイトル

予算管理画面（SCR-002）を一覧表示／詳細表示の構成に変更する

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-002, REQ-003, REQ-004, REQ-014

### 関連設計

- `ui-design.md` / SCR-002: 予算管理
- `api-design.md` / `/budget-periods`, `/budget-periods/{id}/duplicate`, PATCH `/budget-periods/{id}`, `/budget-items`

### 実装パス

- `src/features/expense-management/frontend/src/views/BudgetsView.vue`
- `src/features/expense-management/frontend/src/api.ts`

### 内容

予算管理画面を、既存の2カラム同時表示（予算期間一覧＋予算項目一覧）から、「一覧表示」（予算期間一覧を画面幅いっぱいに表示。新規作成・複製作成ボタン）と「詳細表示」（戻るボタン、予算期間編集フォーム［タイトル・開始日・終了日、保存/キャンセル］、予算項目一覧と追加・編集・削除）の2状態へ再構成する。予算期間を選ぶと詳細表示に切り替わり、詳細表示の保存は詳細表示のまま内容を更新する（一覧表示には戻らない）。「戻る」で一覧表示に戻る。パスは変えない。

### 完了条件

- [ ] 一覧表示で予算期間一覧が画面幅いっぱいに表示される
- [ ] 予算期間を選ぶと詳細表示に切り替わる
- [ ] 詳細表示でタイトル・開始日・終了日を編集して保存できる。保存後も詳細表示のまま
- [ ] 詳細表示で予算項目の追加・編集・削除ができる
- [ ] 「戻る」で一覧表示に戻る
- [ ] ブラウザで一連の操作を確認できる

---

## テスト

### 単体テスト

- [ ] `src/features/expense-management/tests/` に配置する
- [ ] 実際の締め日・実際の支払日の算出（曜日除外、当月に存在しない日除外、過去/未来のずらし方向、月末境界）を確認する
- [ ] 予算期間の重複判定を確認する
- [ ] 予算期間の更新（タイトル・開始日・終了日、400・404）を確認する
- [ ] 締め日0の支出方法で固定値が設定されることを確認する
- [ ] 予算項目・支出方法の論理削除後も、既存の支出記録の参照が変わらないことを確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、404、409、予算期間・予算項目・支出方法・支出記録の CRUD、集計2種）
- [ ] 予算期間の複製作成で予算項目がコピーされることを確認する

### 受け入れテスト

- [ ] `requirements.md` の受け入れ条件（REQ-001〜REQ-014）を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-18 | 未承認 | 初版 |
| 2026-09-18 | 承認済み | 初版を承認 |
| 2026-09-18 | 未承認 | 予算期間の更新（タスク17〜18）。API・画面 |
| 2026-09-18 | 承認済み | タスク17〜18を承認 |
