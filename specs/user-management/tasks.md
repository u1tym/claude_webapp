# タスク: user-management（ユーザ管理）

## 概要

対象機能: `user-management`

ソース配置:

- フロントエンド: `src/features/user-management/frontend`
- バックエンド: `src/features/user-management/backend`
- テスト: `src/features/user-management/tests`

関連要件:

- REQ-001 〜 REQ-013

`portal` の Python は import しない。表は `public` の既存を使う。本機能の固有 DDL は作らない。`public.users.email` の列追加は `portal` の DDL で行う（タスク 11）。本機能の機能マスタ登録と最初の運用者への割当は、`portal` の運用コマンドで行う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-013

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`）
- `.cursor/rules/16-logging.mdc`

### 実装パス

- `src/features/user-management/backend/app/main.py`
- `src/features/user-management/backend/app/config.py`
- `src/features/user-management/backend/app/logger.py`
- `src/features/user-management/backend/.env`（ひな型: `docs/specs/templates/backend.env.example`）
- `src/features/user-management/backend/requirements.txt`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB、CORS、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジン、資格情報付き。起動時に `log/` へサイズローテーションするロガーを初期化する。`portal` を import しない。秘密情報をソースに直書きしない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8001` が起動できる
- [ ] `LOG_MAX_BYTES` と `LOG_BACKUP_COUNT` を `.env` から読む
- [ ] 秘密情報をソースに直書きしていない

---

## タスク 2

### タイトル

DB 接続と `public` へのデータアクセスを実装する

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-002, REQ-006, REQ-010

### 関連設計

- `design.md` / バックエンド設計 / データアクセス
- `db-design.md` / テーブル設計

### 実装パス

- `src/features/user-management/backend/app/db.py`
- `src/features/user-management/backend/app/` 配下のデータアクセス

### 内容

PostgreSQL へ接続する。ユーザ、セッション、システム設定、機能マスタ、メニュー割当の取得・追加・更新・論理削除・行削除を、設計の役割どおりに実装する。DDL は置かない。パスワードハッシュは一覧では返さない。型ヒントを付ける。

### 完了条件

- [ ] `.env` の接続情報（tstdb / tstuser）で接続できる
- [ ] 各表へのアクセス関数がある（型ヒント付き）
- [ ] SQL ファイルを追加していない
- [ ] 接続情報をソースに直書きしていない

---

## タスク 3

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

- `src/features/user-management/backend/app/security.py`
- `src/features/user-management/backend/app/deps.py`
- `src/features/user-management/backend/app/services/access_service.py`
- `src/features/user-management/backend/app/routers/settings.py`

### 内容

Cookie `session_id` でログイン中ユーザを特定する。未ログイン・期限切れは 401。識別子 `user-management` の割当が無ければ 403。`DEBUG_USER` でも割当を判定する。セッション ID を本文に出さない。GET `/settings` は認証不要で login_url、menu_url、icon_system、icon_back を返す。アイコンは data URL。

運用として、`portal` の運用コマンドで機能 `user-management` を追加し、運用ユーザへ割り当てる。

### 完了条件

- [ ] 未ログインの操作 API が 401「未ログイン」
- [ ] 割当なしの操作 API が 403「権限がありません」
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 本文にセッション ID を含まない
- [ ] 機能マスタに `user-management` があり、運用ユーザへ割り当てられている

---

## タスク 4

### タイトル

ユーザ API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-013

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（ユーザ）
- `api-design.md` / GET POST `/users`、PATCH DELETE `/users/{user_id}`

### 実装パス

- `src/features/user-management/backend/app/services/user_service.py`
- `src/features/user-management/backend/app/routers/users.py`
- `src/features/user-management/tests/`

### 内容

未削除ユーザの一覧（パスワードなし、`is_self`）。追加はユーザ名とパスワード（ハッシュ化）。更新はユーザ名と任意のパスワード。削除は論理削除しセッション行を消す。自分自身の削除は 409。重複ユーザ名は 409。存在しない／既削除は 404。操作の入力・判断・失敗理由をログへ出す。パスワードはログに出さない。

### 完了条件

- [ ] GET `/users` が未削除のみ、パスワードなし
- [ ] POST で追加でき、重複は 409
- [ ] PATCH でユーザ名とパスワードを更新できる。空パスワードは変えない
- [ ] DELETE で論理削除。自分自身は 409
- [ ] 成功は INF、想定内の失敗は WRN。パスワードがログに無い

---

## タスク 5

### タイトル

機能 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-006, REQ-007, REQ-008, REQ-009, REQ-013

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（機能）
- `api-design.md` / GET POST `/features`、PATCH DELETE `/features/{feature_id}`

### 実装パス

- `src/features/user-management/backend/app/services/feature_service.py`
- `src/features/user-management/backend/app/routers/features.py`
- `src/features/user-management/tests/`

### 内容

未削除機能の一覧（アイコンは data URL、`is_protected`）。追加は識別子・タイトル・遷移先・アイコン。更新はタイトル・遷移先・任意のアイコン。識別子は変えない。削除は論理削除。`user-management` の削除は 409。重複識別子は 409。配信用画像ファイルは置かない。操作をログへ出す。

### 完了条件

- [ ] GET `/features` が未削除のみ。アイコンが data URL
- [ ] POST で追加でき、重複は 409
- [ ] PATCH でタイトル・遷移先・アイコンを更新でき、識別子は変わらない
- [ ] DELETE で論理削除。本機能自身は 409
- [ ] 配信用の画像ファイルをリポジトリに置いていない
- [ ] 操作がログに残る

---

## タスク 6

### タイトル

割当 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-010, REQ-011, REQ-012, REQ-013

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（割当）
- `api-design.md` / GET POST `/assignments`、DELETE `/assignments/{user_id}/{feature_id}`

### 実装パス

- `src/features/user-management/backend/app/services/assignment_service.py`
- `src/features/user-management/backend/app/routers/assignments.py`
- `src/features/user-management/tests/`

### 内容

未削除同士の割当一覧（`can_unassign`）。追加はユーザ・機能・表示順。重複と論理削除済み対象は失敗。解除は行削除。自分自身から本機能を外すことは 409。操作をログへ出す。

### 完了条件

- [ ] GET `/assignments` が未削除同士のみ
- [ ] POST で割り当てられ、重複は 409、対象なしは 404
- [ ] DELETE で解除できる。自分自身かつ本機能は 409
- [ ] 操作がログに残る

---

## タスク 7

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

- `src/features/user-management/frontend/`
- `src/features/user-management/frontend/.env`（ひな型: `docs/specs/templates/frontend.env.example`。変数名は `VITE_API_USER_MANAGEMENT_URL`）

### 内容

`npm run dev` で起動する。トークンと殻（ヘッダ / ナビ / コンテンツ。PC は左ナビ、スマートフォンは下ナビ）を `15-ui-style.mdc` どおりに置く。`--color-primary` は `#8B7CFF`。ナビはユーザ・機能・割当。ヘッダに戻るとシステムアイコン。Vite `base` は `/portal_user_management/`。`/portal_user_management/` は `/portal_user_management/users` へ。未ログインは GET `/settings` の login_url へ。割当なしは「この機能を使えません」。API は `VITE_API_USER_MANAGEMENT_URL` と credentials のみ。セッション ID をフロントに持たない。他機能の Vue は import しない。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_USER_MANAGEMENT_URL` で API を呼び、ホストを直書きしていない
- [ ] `/portal_user_management/` が `/portal_user_management/users` へ進む
- [ ] 未ログインでログイン画面 URL へ進む
- [ ] セッション ID を `localStorage` や URL に置いていない

---

## タスク 8

### タイトル

ユーザ画面を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005

### 関連設計

- `ui-design.md` / SCR-001 ユーザ
- `api-design.md` / `/users`

### 実装パス

- `src/features/user-management/frontend/` のユーザ画面

### 内容

未削除ユーザを一覧する。パスワードは出さない。新規・保存・キャンセル・削除。更新時パスワード空は変えない。自分自身は削除ボタンを出さない。PC は一覧と入力を同時表示。スマートフォンは切り替える。失敗は定型文のみ。確認ダイアログのあと削除する。

### 完了条件

- [ ] ユーザ名が一覧に出る。パスワードは出ない
- [ ] 追加・更新・削除ができる
- [ ] 自分自身の削除ボタンが出ない
- [ ] 空入力は送信しない

---

## タスク 9

### タイトル

機能画面を実装する

### 見積もり

3時間

### 関連要件

- REQ-006, REQ-007, REQ-008, REQ-009

### 関連設計

- `ui-design.md` / SCR-002 機能
- `api-design.md` / `/features`

### 実装パス

- `src/features/user-management/frontend/` の機能画面

### 内容

未削除機能を一覧する。アイコンはデータとして示す。新規・保存・キャンセル・削除。識別子は追加時のみ入力。更新でアイコン未選択なら既存を維持。本機能の行は削除ボタンを出さない。配信用ファイルは置かない。PC は同時表示、スマートフォンは切り替え。

### 完了条件

- [ ] 識別子・タイトル・遷移先・アイコンが一覧に出る
- [ ] 追加・更新・削除ができる
- [ ] 本機能の削除ボタンが出ない
- [ ] 配信用の画像ファイルをリポジトリに置いていない

---

## タスク 10

### タイトル

割当画面を実装する

### 見積もり

3時間

### 関連要件

- REQ-010, REQ-011, REQ-012

### 関連設計

- `ui-design.md` / SCR-003 割当
- `api-design.md` / `/assignments`

### 実装パス

- `src/features/user-management/frontend/` の割当画面

### 内容

未削除同士の割当を一覧する。新規でユーザ・機能・表示順を選んで保存する。解除は確認ダイアログのあと。自分自身かつ本機能の行は解除ボタンを出さない。PC は同時表示、スマートフォンは切り替え。

### 完了条件

- [ ] ユーザ名・機能タイトル・表示順が一覧に出る
- [ ] 割当の追加と解除ができる
- [ ] 自分自身かつ本機能の解除ボタンが出ない
- [ ] 必須が空なら送信しない

---

## タスク 11

### タイトル

`public.users` に `email` の DDL を追加し、適用する

### 見積もり

1時間

### 関連要件

- REQ-002, REQ-003, REQ-004

### 関連設計

- `db-design.md` / `public.users`（`email`）
- `design.md` / 構成（DDL は portal）

### 実装パス

- `src/features/portal/backend/sql/01_public.sql`
- `src/features/portal/backend/sql/`（既存 DB 向けの ALTER）

### 内容

`public.users` に `email`（varchar(255)、NOT NULL、既定 `''`）を足す。一意制約は付けない。形式の検査制約は置かない。既存行は空文字。`CREATE TABLE IF NOT EXISTS` では列は増えないため、既存 DB には `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` を適用する。本機能の `sql/` には置かない。

### 完了条件

- [ ] `public.users.email` がある
- [ ] 既存行は空文字
- [ ] 一意制約が無い
- [ ] `tstuser` で tstdb に適用できる
- [ ] 本機能の `sql/` を増やしていない

---

## タスク 12

### タイトル

ユーザ API に `email` を載せる

### 見積もり

2時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-013

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（ユーザ）
- `api-design.md` / GET POST `/users`、PATCH `/users/{user_id}`
- `db-design.md` / `public.users.email`

### 実装パス

- `src/features/user-management/backend/app/repos.py`
- `src/features/user-management/backend/app/services/user_service.py`
- `src/features/user-management/backend/app/routers/users.py`
- `src/features/user-management/tests/`

### 内容

GET/POST `/users` と PATCH `/users/{user_id}` に `email` を載せる。一覧・追加・更新の応答に含める。パスワードは出さない。POST と PATCH で必須。空、または `@` の前後に文字が無いときは 400。一意は要求しない。ログインには使わない。操作ログにメールアドレスの入力を残す。パスワードはログに出さない。

### 完了条件

- [ ] GET `/users` の各件に `email` がある。パスワードは無い
- [ ] POST で `email` を保存できる。無い／空・形式不正は 400
- [ ] PATCH で `email` を更新できる。無い／空・形式不正は 400
- [ ] 同じメールアドレスのユーザを複数登録できる
- [ ] 成功は INF、想定内の失敗は WRN。入力に `email` が含まれる。パスワードがログに無い

---

## タスク 13

### タイトル

ユーザ画面にメールアドレスの表示と入力を付ける

### 見積もり

2時間

### 関連要件

- REQ-002, REQ-003, REQ-004

### 関連設計

- `ui-design.md` / SCR-001 ユーザ
- `api-design.md` / `/users`

### 実装パス

- `src/features/user-management/frontend/src/views/UsersView.vue`
- `src/features/user-management/frontend/src/api.ts`

### 内容

一覧にメールアドレス列を出す。入力はユーザ名の下、パスワードの上。プレースホルダ「メールアドレス」。追加時は必須。編集時は行の値を入れる。空、または `@` の前後に文字が無ければ送信しない。Enter でも保存する。パスワードは一覧に出さない。

### 完了条件

- [ ] 一覧にユーザ名とメールアドレスが出る。パスワードは出ない
- [ ] 追加・更新でメールアドレスを入力できる
- [ ] 空または形式不正では送信しない
- [ ] ブラウザで追加・更新を確認できる

---

## テスト

### 単体テスト

- [ ] `src/features/user-management/tests/` に配置する
- [ ] 自己削除禁止、本機能削除禁止、自己からの本機能割当解除禁止、重複、論理削除済み対象、パスワード非出力を確認する
- [ ] メールアドレスの必須、空、形式不正、一覧への出力を確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、409、settings）
- [ ] 操作ログ（入力・判断・失敗理由、パスワード非出力、メールアドレスの入力）

### 受け入れテスト

- [ ] requirements.md の受け入れ条件を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-26 23:03 | 未承認 | 初版 |
| 2026-08-26 23:11 | 承認済み | 初版を承認 |
| 2026-08-29 18:21 | 未承認 | 公開パスの基点を `/portal_user_management/` にする |
| 2026-08-29 18:29 | 未承認 | dist の配置先を `features/user-management/` にする |
| 2026-08-29 19:19 | 承認済み | 公開パス `/portal_user_management/` と dist 配置の改訂を承認 |
| 2026-08-30 08:26 | 未承認 | メールアドレス（タスク 11〜13）。DDL・API・画面 |
| 2026-08-30 08:27 | 承認済み | タスク 11〜13 を承認 |
