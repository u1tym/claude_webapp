# タスク: password-management（パスワード管理）

## 概要

対象機能: `password-management`

ソース配置:

- フロントエンド: `src/features/password-management/frontend`
- バックエンド: `src/features/password-management/backend`
- テスト: `src/features/password-management/tests`

関連要件:

- REQ-001 〜 REQ-008

`portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当は `public` の既存を読むだけ（複製しない）。本機能固有の業務テーブルはスキーマ `password_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能（またはportalの運用コマンド）で行う。`--color-primary` は未使用のパレット値 `#e58fe0`（マゼンタ）を使う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、DB接続、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-008

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`, `app/db.py`）
- `rules/16-logging.md`

### 実装パス

- `src/features/password-management/backend/app/main.py`
- `src/features/password-management/backend/app/config.py`
- `src/features/password-management/backend/app/logger.py`
- `src/features/password-management/backend/app/db.py`
- `src/features/password-management/backend/.env`（ひな型: `specs/templates/backend.env.example`）
- `src/features/password-management/backend/requirements.txt`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB 接続情報、`CORS_ORIGINS`、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジン、資格情報付き。起動時に `log/` へサイズローテーションするロガーを初期化する。PostgreSQL へ接続する（`app/db.py`）。`portal` を import しない。秘密情報をソースに直書きしない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8004` が起動できる
- [ ] `.env` の接続情報（tstdb / tstuser）で DB に接続できる
- [ ] `LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を `.env` から読む
- [ ] 秘密情報をソースに直書きしていない

---

## タスク 2

### タイトル

セッション検証、本機能の割当判定、設定取得 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-008

### 関連設計

- `design.md` / バックエンド設計 / 認証 / 認可
- `design.md` / バックエンド設計 / モジュール構成（`security`, `deps`, `access_service`, `routers/settings.py`）
- `api-design.md` / 共通 / 認証
- `api-design.md` / GET `/settings`

### 実装パス

- `src/features/password-management/backend/app/security.py`
- `src/features/password-management/backend/app/deps.py`
- `src/features/password-management/backend/app/services/access_service.py`
- `src/features/password-management/backend/app/routers/settings.py`

### 内容

Cookie `session_id` でログイン中ユーザを特定する。未ログイン・期限切れは 401。識別子 `password-management` の割当が無ければ 403。`DEBUG_USER` でも割当を判定する。セッション ID を本文に出さない。認証が必要な要求のたびにセッション期限を延ばす。GET `/settings` は認証不要で `login_url`、`menu_url`、`icon_system`、`icon_back` を返す（アイコンは data URL）。

運用として、機能マスタに `password-management`（タイトル「パスワード管理」、遷移先は公開 URL `/portal_password_management/`）を追加し、利用ユーザへ割り当てる。

### 完了条件

- [ ] 未ログインの操作 API が 401「未ログイン」
- [ ] 割当なしの操作 API が 403「権限がありません」
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 本文にセッション ID を含まない
- [ ] 機能マスタに `password-management` があり、利用ユーザへ割り当てられている

---

## タスク 3

### タイトル

DB スキーマ・テーブル（`password_management.entries`）を作成する

### 見積もり

1時間

### 関連要件

- REQ-003, REQ-004, REQ-005, REQ-006

### 関連設計

- `db-design.md` / テーブル設計

### 実装パス

- `src/features/password-management/backend/sql/01_password_management.sql`

### 内容

スキーマ `password_management` と、テーブル `entries`（`id`, `user_id`, `title`, `userword`, `psword`, `site`, `memo`, `is_deleted`）を作成する。`user_id` は `public.users.id` への外部キー（ON DELETE RESTRICT）。`title` / `userword` / `psword` は空文字不可の検査制約。`(user_id, title)` に `is_deleted = false` の部分一意インデックスを作る（`schedule.categories` と同じ方式）。`(user_id)` に `is_deleted = false` の索引も作る。

### 完了条件

- [ ] スキーマ・テーブルが `db-design.md` のカラム定義どおりに作成される
- [ ] `(user_id, title)` の部分一意インデックスが、未削除行だけを対象にしている
- [ ] 同一ユーザ・同一タイトルで、片方が削除済みなら重複登録できることを確認する
- [ ] DDL が冪等（`IF NOT EXISTS` 等）である

---

## タスク 4

### タイトル

パスワードエントリの登録・更新・削除・単件取得 API を実装する

### 見積もり

4時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-007, REQ-008

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `design.md` / バックエンド設計 / モジュール構成（`repos`, `password_service`, `routers/passwords.py`, `errors`）
- `api-design.md` / POST・PATCH・DELETE `/passwords`、GET `/passwords/{id}`

### 実装パス

- `src/features/password-management/backend/app/errors.py`
- `src/features/password-management/backend/app/repos.py`
- `src/features/password-management/backend/app/services/password_service.py`
- `src/features/password-management/backend/app/routers/passwords.py`

### 内容

`repos.py` に `password_management.entries` への挿入・更新・論理削除・単件取得・タイトル重複確認（`user_id` と `is_deleted = false` で絞り込み）を実装する。`password_service.py` で、タイトル・ユーザ名の空白のみ拒否（トリムして判定・保存）、パスワードの空文字拒否、タイトル重複判定（更新時は自エントリを除外）を行う。`routers/passwords.py` に POST・PATCH・DELETE・GET `/passwords/{id}` を実装する。すべて `user_id` で本人の行だけを対象にし、他人の行・存在しない ID は 404 とする。要求・判断・失敗理由をログへ出す。パスワード（`psword`）の値はログに出さない。

### 完了条件

- [ ] 登録・更新・削除・単件取得が本人の行だけを対象にする（他人の ID は 404）
- [ ] タイトル・ユーザ名の空白のみ、パスワードの空文字が 400 になる
- [ ] タイトル重複（新規・更新とも）が 409 になる
- [ ] 削除後、同じタイトルで新規登録できる
- [ ] ログにタイトルや操作結果は残るが、`psword` の値は残らない

---

## タスク 5

### タイトル

一覧・検索 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-002, REQ-006, REQ-008

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（検索）
- `api-design.md` / GET `/passwords`

### 実装パス

- `src/features/password-management/backend/app/repos.py`
- `src/features/password-management/backend/app/services/password_service.py`
- `src/features/password-management/backend/app/routers/passwords.py`

### 内容

`keyword` クエリが無い、または空・空白のみのときは、本人の未削除エントリを ID 昇順で全件返す。`keyword` があるときは、タイトル・ユーザ名・サイトURL・メモのいずれかに `ILIKE` で部分一致するものだけを返す。一覧の応答には `psword` を含めない。

### 完了条件

- [ ] `keyword` 無しで本人の未削除エントリが登録順に全件返る
- [ ] `keyword` 指定で、タイトル・ユーザ名・サイトURL・メモのいずれかに部分一致するものだけ返る（大文字小文字を区別しない）
- [ ] 一覧の応答に `psword` が含まれない
- [ ] 空・空白のみの `keyword` が全件取得と同じ結果になる

---

## タスク 6

### タイトル

フロントエンドの Vue 起動、殻、アイコン、API クライアント基盤を用意する

### 見積もり

3時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / フロントエンド設計 / API クライアント
- `ui-design.md` / 共通UI
- `ui-design.md` / 画面遷移
- `api-design.md` / GET `/settings`
- `rules/15-ui-style.md`
- `rules/17-nginx-deploy.md`

### 実装パス

- `src/features/password-management/frontend/`
- `src/features/password-management/frontend/.env`（ひな型: `specs/templates/frontend.env.example`。変数名は `VITE_API_PASSWORD_MANAGEMENT_URL`）
- `src/features/password-management/frontend/src/styles.css`
- `src/features/password-management/frontend/src/components/Icon.vue`

### 内容

`npm run dev` で起動する。`rules/15-ui-style.md` の殻（ヘッダ / ナビ / コンテンツ。PC は左ナビ、スマートフォンは下ナビ）とトークンを、他機能と同じ値で置く。`--color-primary` は `#e58fe0`。ナビは「パスワード管理」のみ。Vite `base` は `/portal_password_management/`。パスは `/portal_password_management/`。未ログインは GET `/settings` の `login_url` へ。割当なしは「この機能を使えません」。API は `VITE_API_PASSWORD_MANAGEMENT_URL` と credentials のみ。セッション ID をフロントに持たない。他機能の Vue・CSS・コンポーネントは import しない。`Icon.vue` は `icons/` から必要な分（`plus`, `edit`, `delete`, `check`, `close`, `back`）を複製する。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_PASSWORD_MANAGEMENT_URL` で API を呼び、ホストを直書きしていない
- [ ] 未ログインでログイン画面 URL へ進む
- [ ] セッション ID を `localStorage` や URL に置いていない
- [ ] 他機能のコードを import していない

---

## タスク 7

### タイトル

一覧・検索・新規登録ボタンを実装する

### 見積もり

3時間

### 関連要件

- REQ-006

### 関連設計

- `ui-design.md` / SCR-001 パスワード管理（検索欄・新規登録ボタン・一覧）
- `api-design.md` / GET `/passwords`

### 実装パス

- `src/features/password-management/frontend/src/api.ts`
- `src/features/password-management/frontend/src/views/PasswordsView.vue`（または相当のビュー）

### 内容

画面を開いたら一覧を取得する。検索欄の入力のたびに `keyword` 付きで再取得する（パスワードは一覧に含まれないため、そのまま表示に使える）。一覧はタイトル・ユーザ名の列を持ち、行を選ぶと詳細表示（タスク8）を開く。0件時は「データがありません」、検索で0件時は「該当するデータがありません」。新規登録ボタンは登録フォーム（タスク9）を開く。

### 完了条件

- [ ] 画面を開くと一覧が表示される
- [ ] 検索欄への入力で一覧が絞り込まれる（タイトル・ユーザ名・サイトURL・メモが対象）
- [ ] 0件・検索0件それぞれで適切な空表示になる
- [ ] 行を選ぶと詳細表示が開く
- [ ] ブラウザで一覧・検索を確認できる

---

## タスク 8

### タイトル

詳細表示（マスク・表示切替・コピー）を実装する

### 見積もり

3時間

### 関連要件

- REQ-007

### 関連設計

- `ui-design.md` / SCR-001 パスワード管理（詳細表示）
- `api-design.md` / GET `/passwords/{id}`

### 実装パス

- `src/features/password-management/frontend/src/api.ts`
- `src/features/password-management/frontend/src/views/`（詳細表示のモーダル部品）

### 内容

一覧の行選択で GET `/passwords/{id}` を呼び、タイトル・ユーザ名・パスワード・サイトURL・メモを取得して詳細表示（モーダル）を開く。パスワードは既定でマスク（`••••••••` 相当）にし、「表示」ボタンでマスクと平文表示を切り替える（ラベルは表示中「隠す」）。ユーザ名・パスワードにそれぞれ「コピー」ボタンを置き、`navigator.clipboard.writeText` でコピーする（成功時は「コピー済」を数秒表示）。サイトURLが設定されていれば新しいタブで開けるリンクにする。メモは設定されていれば改行を保って表示する。編集・削除・閉じるボタンを持つ。

### 完了条件

- [ ] 行選択で詳細（パスワードを含む）が取得され、パスワードは既定でマスクされる
- [ ] 表示切替でマスク・平文表示が切り替わる
- [ ] ユーザ名・パスワードのコピーができる（マスク中でも実際の値がコピーされる）
- [ ] サイトURLがリンクとして開ける。未設定時は表示されない
- [ ] 編集・削除ボタンからそれぞれのフォーム・確認へ進める
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 9

### タイトル

登録・編集フォームを実装する

### 見積もり

3時間

### 関連要件

- REQ-003, REQ-004

### 関連設計

- `ui-design.md` / SCR-001 パスワード管理（登録・編集フォーム）
- `api-design.md` / POST・PATCH `/passwords`

### 実装パス

- `src/features/password-management/frontend/src/api.ts`
- `src/features/password-management/frontend/src/views/`（登録・編集フォームのモーダル部品）

### 内容

新規登録ボタン、または詳細表示の編集ボタンからフォームを開く。入力項目はタイトル・ユーザ名・パスワード（複数行可、表示切替ボタン付き）・サイトURL・メモ。タイトル・ユーザ名・パスワードが未入力のときは送信せず、対象欄にエラーを示す。保存は新規なら POST、編集なら PATCH を呼ぶ。成功したら一覧を再取得してフォームを閉じ、成功メッセージを数秒表示する。タイトル重複（409）はエラーメッセージで示す。キャンセルは入力を捨てて閉じる。

### 完了条件

- [ ] 新規登録・編集の両方でフォームが正しい初期値で開く
- [ ] 必須項目が空・空白のみだと送信されず、対象欄にエラーが出る
- [ ] タイトル重複時にエラーメッセージが出る（画面には内部理由を出さない）
- [ ] 保存成功で一覧に反映され、フォームが閉じる
- [ ] キャンセルで入力を捨てて閉じる
- [ ] ブラウザで新規登録・編集それぞれを確認できる

---

## タスク 10

### タイトル

削除確認ダイアログを実装する

### 見積もり

1時間

### 関連要件

- REQ-005

### 関連設計

- `ui-design.md` / SCR-001 パスワード管理（削除確認ダイアログ）
- `api-design.md` / DELETE `/passwords/{id}`

### 実装パス

- `src/features/password-management/frontend/src/api.ts`
- `src/features/password-management/frontend/src/views/`（削除確認ダイアログ）

### 内容

詳細表示の削除ボタンから、対象のタイトルを示す確認ダイアログを開く。「削除」で DELETE を呼び、成功したら一覧を再取得してダイアログを閉じ、成功メッセージを表示する。失敗はエラーメッセージを示す。「キャンセル」は何もせず閉じる。

### 完了条件

- [ ] 削除確認ダイアログに対象のタイトルが表示される
- [ ] 削除成功で一覧から消え、ダイアログが閉じる
- [ ] キャンセルで何も削除されない
- [ ] ブラウザで削除操作を確認できる

---

## タスク 11

### タイトル

nginx の配置例を置く

### 見積もり

1時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / 構成
- `ui-design.md` / 画面一覧（パス `/portal_password_management/`）
- `rules/17-nginx-deploy.md`

### 実装パス

- `src/features/password-management/frontend/nginx.example.conf`

### 内容

公開 URL `/portal_password_management/`、ディスクは `features/password-management/`。スラッシュなしは 301 で付ける。`rewrite` は `last`。`features/password-management/` は `internal`。API を同一オリジンにする場合の `proxy_pass` 例をコメントで置く。

### 完了条件

- [ ] 公開 URL とディスク配置が規則どおりである
- [ ] `rewrite` が `last` である
- [ ] スラッシュなしの location がある

---

## タスク 12

### タイトル

別サーバ版（`sample/psinfo`）からのデータ移行スクリプトを作成する

### 見積もり

3時間

### 関連要件

- （`requirements.md` の対象外。運用作業として実施）

### 関連設計

- `db-design.md` / テーブル設計（移行先）
- `sample/psinfo/backend/for_human_memo/db.sql`（移行元のテーブル定義）

### 実装パス

- `src/features/password-management/backend/scripts/export_from_psinfo.py`（新規）
- `src/features/password-management/backend/scripts/import_to_password_management.py`（新規）
- `src/features/password-management/backend/scripts/README.md`（新規。実行手順）

### 内容

**エクスポート**（別サーバ側で実行する。この作業環境からは旧DBへ接続できないため、利用者が接続可能な環境で実行する）: 接続情報（ホスト・ポート・DB名・ユーザ名・パスワード）を引数または環境変数で受け取り、`psinfo.master`（`deleted_count = 0` の行だけ）と `public.accounts`（`id`, `username`）を読み、`{ "accounts": [...], "entries": [...] }` 形式の JSON ファイルへ出力する。パスワードの値を標準出力やログに出さない。

**インポート**（本プロジェクトの DB に対して実行する）: エクスポートした JSON ファイルと、本プロジェクトの DB 接続情報（`backend/.env` を利用）を受け取る。JSON 内の `accounts` の `username` を、本プロジェクトの `public.users.username` と突合し、一致するものだけを移行対象にする。一致しないユーザ名のエントリは移行せず、対象外の一覧（旧 `aid`・`username`・件数）を標準出力に一覧表示する。移行対象のエントリは `password_management.entries` へ、`user_id`（突合結果）・`title`・`userword`・`psword`・`site`・`memo` を `is_deleted = false` で挿入する。同一ユーザ内でタイトルが重複する行があれば挿入せずスキップし、一覧表示する（部分一意インデックスに違反させない）。処理件数（成功・スキップ・対象外）を最後にまとめて表示する。パスワードの値を標準出力やログに出さない。

### 完了条件

- [ ] エクスポートスクリプトが、接続情報を引数/環境変数で受け取り、未削除エントリのみを JSON へ出力する
- [ ] インポートスクリプトが、username で新旧ユーザを突合し、一致しないものを対象外として一覧表示する
- [ ] インポートスクリプトが、移行先で重複するタイトルをスキップし、一覧表示する
- [ ] 成功・スキップ・対象外の件数が最後に表示される
- [ ] パスワードの値がスクリプトの標準出力・ログのいずれにも出力されない
- [ ] `scripts/README.md` に実行手順（エクスポートは旧サーバ側、インポートは新サーバ側）が書かれている

---

## テスト

### 単体テスト

- [ ] `src/features/password-management/tests/` に配置する
- [ ] タイトル・ユーザ名の空白のみ拒否、パスワードの空文字拒否を確認する
- [ ] タイトル重複（新規・更新、自エントリ除外）を確認する
- [ ] 論理削除後、同一タイトルで再登録できることを確認する
- [ ] 検索（大文字小文字を区別しない部分一致、対象4項目）を確認する
- [ ] 他ユーザの行が一覧・単件取得・更新・削除の対象にならないことを確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、404、409、settings、passwords の CRUD・検索）
- [ ] 操作ログ（入力・判断・失敗理由、`psword` とセッション ID の非出力）

### 受け入れテスト

- [ ] `requirements.md` の受け入れ条件（REQ-001〜REQ-008）を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 01:16 | 未承認 | 初版 |
| 2026-09-20 01:17 | 承認済み | 初版を承認 |
