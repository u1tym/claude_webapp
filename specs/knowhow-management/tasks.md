# タスク: knowhow-management（ノウハウ管理）

## 概要

対象機能: `knowhow-management`

ソース配置:

- フロントエンド: `src/features/knowhow-management/frontend`
- バックエンド: `src/features/knowhow-management/backend`
- テスト: `src/features/knowhow-management/tests`

関連要件:

- REQ-001 〜 REQ-016

`portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当は `public` の既存を読むだけ（複製しない）。本機能固有の業務テーブルはスキーマ `knowhow_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能で行う。`--color-primary` は、rules/15-ui-style.mdのパレットに新規追加した `#F2C94C`（Amber）を使う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、DB接続、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-016

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`, `app/db.py`）

### 実装パス

- `src/features/knowhow-management/backend/app/main.py`
- `src/features/knowhow-management/backend/app/config.py`
- `src/features/knowhow-management/backend/app/logger.py`
- `src/features/knowhow-management/backend/app/db.py`
- `src/features/knowhow-management/backend/.env`（ひな型: `specs/templates/backend.env.example`）
- `src/features/knowhow-management/backend/requirements.txt`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB 接続情報、`CORS_ORIGINS`、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジン、資格情報付き。起動時に `log/` へサイズローテーションするロガーを初期化する。PostgreSQL へ接続する。`portal` を import しない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8005` が起動できる
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

- REQ-001, REQ-016

### 関連設計

- `design.md` / バックエンド設計 / 認証 / 認可
- `design.md` / バックエンド設計 / モジュール構成（`security`, `deps`, `access_service`, `routers/settings.py`）
- `api-design.md` / 共通 / 認証
- `api-design.md` / GET `/settings`

### 実装パス

- `src/features/knowhow-management/backend/app/security.py`
- `src/features/knowhow-management/backend/app/deps.py`
- `src/features/knowhow-management/backend/app/services/access_service.py`
- `src/features/knowhow-management/backend/app/routers/settings.py`

### 内容

Cookie `session_id` でログイン中ユーザを特定する。未ログイン・期限切れは 401。識別子 `knowhow-management` の割当が無ければ 403。`DEBUG_USER` でも割当を判定する。セッション ID を本文に出さない。GET `/settings` は認証不要で `login_url`、`menu_url`、`icon_system`、`icon_back` を返す。

運用として、機能マスタに `knowhow-management`（タイトル「ノウハウ管理」、遷移先は公開 URL `/portal_knowhow_management/`）を追加し、利用ユーザへ割り当てる。

### 完了条件

- [ ] 未ログインの操作 API が 401「未ログイン」
- [ ] 割当なしの操作 API が 403「権限がありません」
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 本文にセッション ID を含まない
- [ ] 機能マスタに `knowhow-management` があり、利用ユーザへ割り当てられている

---

## タスク 3

### タイトル

DB スキーマ・テーブル（大項目・中項目・ノウハウ）を作成する

### 見積もり

2時間

### 関連要件

- REQ-003〜REQ-014

### 関連設計

- `db-design.md` / テーブル設計

### 実装パス

- `src/features/knowhow-management/backend/sql/01_knowhow_management.sql`

### 内容

スキーマ `knowhow_management` と、テーブル `major_categories`・`middle_categories`・`knowhows` を `db-design.md` のカラム定義どおりに作成する。`major_categories` は `(user_id, name)`、`middle_categories` は `(major_category_id, name)` に、それぞれ `is_deleted = false` の部分一意インデックスを作る。`knowhows` に `(user_id, middle_category_id)` と `(user_id)` の索引（いずれも `is_deleted = false`）を作る。外部キーはすべて `ON DELETE RESTRICT`。

### 完了条件

- [ ] スキーマ・3テーブルが `db-design.md` のカラム定義どおりに作成される
- [ ] 大項目・中項目それぞれの部分一意インデックスが、未削除行だけを対象にしている
- [ ] 同一ユーザ・同一名称で、片方が削除済みなら重複登録できることを確認する
- [ ] DDL が冪等（`IF NOT EXISTS` 等）である

---

## タスク 4

### タイトル

大項目の一覧・登録・名称変更・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-016

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `design.md` / バックエンド設計 / モジュール構成（`repos`, `category_service`, `routers/major_categories.py`, `errors`）
- `api-design.md` / `/major-categories`

### 実装パス

- `src/features/knowhow-management/backend/app/errors.py`
- `src/features/knowhow-management/backend/app/repos.py`
- `src/features/knowhow-management/backend/app/services/category_service.py`
- `src/features/knowhow-management/backend/app/routers/major_categories.py`

### 内容

`repos.py` に `major_categories` への挿入・名称更新・論理削除・一覧・名称重複確認（`user_id` と `is_deleted = false` で絞り込み）を実装する。`category_service.py` で、名称の空白のみ拒否（トリムして判定・保存）、名称重複判定（更新時は自身を除外）を行う。削除時は、配下の未削除の `middle_categories` と、そのさらに配下の未削除の `knowhows` を、同一トランザクションで論理削除する。`routers/major_categories.py` に GET・POST・PATCH・DELETE を実装する。すべて `user_id` で本人の行だけを対象にし、他人の行・存在しない ID は 404 とする。

### 完了条件

- [ ] 一覧・登録・名称変更・削除が本人の行だけを対象にする（他人の ID は 404）
- [ ] 名称の空白のみが 400 になる
- [ ] 名称重複（新規・更新とも、本人の未削除行内）が 409 になる
- [ ] 大項目の削除で、配下の中項目・ノウハウも論理削除される
- [ ] 削除後、同じ名称で新規登録できる

---

## タスク 5

### タイトル

中項目の一覧・登録・名称変更・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-006, REQ-007, REQ-008, REQ-016

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `/major-categories/{id}/middle-categories`、`/middle-categories/{id}`

### 実装パス

- `src/features/knowhow-management/backend/app/repos.py`
- `src/features/knowhow-management/backend/app/services/category_service.py`
- `src/features/knowhow-management/backend/app/routers/middle_categories.py`

### 内容

`repos.py` に `middle_categories` への挿入・名称更新・論理削除・一覧・名称重複確認（`major_category_id` と `is_deleted = false` で絞り込み）を実装する。登録・一覧は、親の大項目が本人の削除されていない大項目であることを確認する（無ければ 404）。削除時は、配下の未削除の `knowhows` を論理削除する。`routers/middle_categories.py` に GET・POST・PATCH・DELETE を実装する。

### 完了条件

- [ ] 一覧・登録・名称変更・削除が本人の行だけを対象にする
- [ ] 親大項目が無効なときの一覧・登録が 404 になる
- [ ] 名称重複（同一大項目内、新規・更新とも）が 409 になる
- [ ] 中項目の削除で、配下のノウハウも論理削除される
- [ ] 削除後、同じ名称で同一大項目内に新規登録できる

---

## タスク 6

### タイトル

ノウハウの登録・更新・削除・単件取得・一覧 API を実装する

### 見積もり

4時間

### 関連要件

- REQ-002, REQ-009, REQ-010, REQ-011, REQ-012, REQ-013, REQ-016

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（表示順の採番）
- `api-design.md` / `/middle-categories/{id}/knowhows`、`/knowhows`、`/knowhows/{id}`

### 実装パス

- `src/features/knowhow-management/backend/app/repos.py`
- `src/features/knowhow-management/backend/app/services/knowhow_service.py`
- `src/features/knowhow-management/backend/app/routers/knowhows.py`

### 内容

`repos.py` に `knowhows` への挿入・更新・論理削除・一覧（`middle_category_id` 一致）・単件取得を実装する。`knowhow_service.py` で、タイトル・本文の空白のみ拒否（トリムして判定・保存）、`middle_category_id` 指定時は本人の削除されていない中項目であることの確認、登録時・所属先変更時の `display_order` 採番（同一ユーザ・同一所属先の未削除ノウハウの最大値+1）を行う。一覧応答には `content` を含めない。`routers/knowhows.py` に GET（一覧・単件）・POST・PATCH・DELETE を実装する。

### 完了条件

- [ ] 登録・更新・削除・単件取得・一覧が本人の行だけを対象にする
- [ ] タイトル・本文の空白のみが 400 になる
- [ ] 存在しない、または他人の `middle_category_id` を指定すると 404 になる
- [ ] 一覧応答に `content` が含まれない
- [ ] 新規登録時、および所属先変更時に `display_order` が正しく採番される
- [ ] `middle_category_id` を指定しない（`null`）登録・更新ができる

---

## タスク 7

### タイトル

ノウハウのキーワード検索・並び替え API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-014, REQ-015, REQ-016

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（検索・並び替え）
- `api-design.md` / GET `/knowhows/search`、POST `/knowhows/swap-display-order`

### 実装パス

- `src/features/knowhow-management/backend/app/repos.py`
- `src/features/knowhow-management/backend/app/services/knowhow_service.py`
- `src/features/knowhow-management/backend/app/routers/knowhows.py`

### 内容

検索は、指定された全キーワードについて、それぞれ `title`/`keywords`/`content` のいずれかに `ILIKE` で部分一致することを条件に、本人の削除されていないノウハウ全体（中項目・大項目を問わない）から抽出する。結果には `middle_categories`・`major_categories` を結合し、所属する大項目・中項目の名称を付ける（未分類は両方 `null`）。並び替えは、指定された2件がいずれも本人の削除されていない行で、`middle_category_id` が一致することを確認したうえで `display_order` を交換する。

### 完了条件

- [ ] `keyword` を複数指定すると、全て一致する行だけが返る（AND）
- [ ] 検索は大文字小文字を区別しない
- [ ] 検索結果に、未分類も含め所属の大項目・中項目名（または `null`）が付く
- [ ] `keyword` が無い検索要求は 400 になる
- [ ] 所属先が異なる2件の並び替え要求は 400 になる
- [ ] 並び替え成功で、2件の `display_order` が入れ替わる

---

## タスク 8

### タイトル

フロントエンドの Vue 起動、殻、アイコン、API クライアント基盤を用意する

### 見積もり

3時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / フロントエンド設計 / API クライアント
- `ui-design.md` / 共通UI
- `api-design.md` / GET `/settings`
- `rules/15-ui-style.md`
- `rules/17-nginx-deploy.md`

### 実装パス

- `src/features/knowhow-management/frontend/`
- `src/features/knowhow-management/frontend/.env`（ひな型: `specs/templates/frontend.env.example`。変数名は `VITE_API_KNOWHOW_MANAGEMENT_URL`）
- `src/features/knowhow-management/frontend/src/styles.css`
- `src/features/knowhow-management/frontend/src/components/Icon.vue`

### 内容

`npm run dev` で起動する。`rules/15-ui-style.md` の殻とトークンを、他機能と同じ値で置く。`--color-primary` は `#F2C94C`（Amber。rules/15-ui-style.mdのパレットに新規追加）。ナビは「ノウハウ管理」のみ。Vite `base` は `/portal_knowhow_management/`。未ログインは GET `/settings` の `login_url` へ。API は `VITE_API_KNOWHOW_MANAGEMENT_URL` と credentials のみ。他機能のコードは import しない。`Icon.vue` は `icons/` から必要な分（`plus`, `edit`, `delete`, `check`, `close`, `back`, `config`）を複製する。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_KNOWHOW_MANAGEMENT_URL` で API を呼び、ホストを直書きしていない
- [ ] 未ログインでログイン画面 URL へ進む
- [ ] 他機能のコードを import していない

---

## タスク 9

### タイトル

大項目・中項目の選択・登録・名称変更・削除を実装する

### 見積もり

4時間

### 関連要件

- REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008

### 関連設計

- `ui-design.md` / SCR-001（大項目・中項目の選択、追加、名称変更、削除）
- `api-design.md` / `/major-categories`、`/middle-categories`

### 実装パス

- `src/features/knowhow-management/frontend/src/api.ts`
- `src/features/knowhow-management/frontend/src/views/KnowhowView.vue`（または相当のビュー）

### 内容

画面を開いたら大項目一覧を取得する。大項目選択で中項目一覧を、中項目選択でノウハウ一覧（タスク10）を取得する。大項目・中項目それぞれに、追加・名称変更・削除のボタンを置く（削除・名称変更は選択中のときだけ有効）。追加・名称変更は共通のフォームを使う。削除は確認ダイアログのあと実行し、成功したら選択を解除して一覧を更新する。

### 完了条件

- [ ] 大項目を選ぶと、その配下の中項目一覧が表示される
- [ ] 大項目・中項目それぞれで、追加・名称変更・削除ができる
- [ ] 名称重複時にエラーメッセージが表示される
- [ ] 大項目・中項目の削除後、配下のノウハウも見えなくなることを確認できる
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 10

### タイトル

ノウハウの一覧・新規登録を実装する

### 見積もり

3時間

### 関連要件

- REQ-009, REQ-011

### 関連設計

- `ui-design.md` / SCR-001（ノウハウ一覧、新規登録ボタン）
- `api-design.md` / GET・POST `/knowhows`

### 実装パス

- `src/features/knowhow-management/frontend/src/api.ts`
- `src/features/knowhow-management/frontend/src/views/`

### 内容

中項目を選ぶと、その配下のノウハウ一覧（タイトルのみ）を取得して表示する。新規登録ボタンは、中項目を選んでいるときだけ有効。登録フォームはタイトル・キーワード（任意）・本文・所属中項目（既定は選択中の中項目。「未分類」も選べる）を持つ。保存後は一覧を更新する。

### 完了条件

- [ ] 中項目を選ぶとノウハウ一覧が表示される
- [ ] 新規登録フォームで登録でき、一覧に反映される
- [ ] 必須項目が空・空白のみだと送信されない
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 11

### タイトル

ノウハウの詳細表示・編集を実装する

### 見積もり

3時間

### 関連要件

- REQ-010, REQ-012

### 関連設計

- `ui-design.md` / SCR-001（詳細表示、編集フォーム）
- `api-design.md` / GET・PATCH `/knowhows/{id}`

### 実装パス

- `src/features/knowhow-management/frontend/src/api.ts`
- `src/features/knowhow-management/frontend/src/views/`

### 内容

一覧の行を選ぶと詳細（タイトル・所属する大項目名・中項目名・キーワード・本文）を取得して表示する。詳細表示中は、並び替えモード切替ボタンが編集ボタンとして働き、押すと編集フォームを開く（現在の内容を初期値にする）。編集フォームは所属する中項目の変更（「未分類」を含む）に対応する。保存後は詳細表示を更新する。戻るボタンで一覧に戻る。

### 完了条件

- [ ] 行選択で詳細（本文を含む）が表示される
- [ ] 詳細表示中の設定ボタンで編集フォームが開く
- [ ] 編集で所属中項目を変更でき、「未分類」にもできる
- [ ] 保存後、詳細表示の内容が更新される
- [ ] 戻るボタンで一覧に戻る
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 12

### タイトル

ノウハウの並び替え・削除を実装する

### 見積もり

2時間

### 関連要件

- REQ-013, REQ-014

### 関連設計

- `ui-design.md` / SCR-001（並び替えモード、上へ・下へ・削除）
- `api-design.md` / DELETE `/knowhows/{id}`、POST `/knowhows/swap-display-order`

### 実装パス

- `src/features/knowhow-management/frontend/src/api.ts`
- `src/features/knowhow-management/frontend/src/views/`

### 内容

並び替えモード切替ボタン（`config` アイコン）で、一覧表示中に並び替えモードの入/切を切り替える（中項目を選んでいて、検索確定中でないときだけ有効）。並び替えモード中は各行に上へ・下へ・削除のボタンを表示する。上へ・下へは隣接する行と `swap-display-order` を呼び、一覧を再取得する。先頭行の上へ、末尾行の下へは無効にする。削除は確認ダイアログのあと `DELETE` を呼び、一覧を再取得する。

### 完了条件

- [ ] 並び替えモードで各行に上へ・下へ・削除が表示される
- [ ] 上へ・下へで隣接行と順序が入れ替わる
- [ ] 先頭行の上へ、末尾行の下へが無効になっている
- [ ] 削除確認のあと、一覧からその行が消える
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 13

### タイトル

キーワード検索を実装する

### 見積もり

2時間

### 関連要件

- REQ-015

### 関連設計

- `ui-design.md` / SCR-001（キーワード検索欄、検索結果一覧）
- `api-design.md` / GET `/knowhows/search`

### 実装パス

- `src/features/knowhow-management/frontend/src/api.ts`
- `src/features/knowhow-management/frontend/src/views/`

### 内容

検索欄にカンマ区切りでキーワードを入力し、検索ボタンで確定する。確定すると、大項目・中項目選択の代わりに検索結果一覧（タイトルと、所属する大項目・中項目名。未分類は「未分類」）を表示する。結果の行を選ぶと詳細表示を開く。クリアボタンでキーワードと検索結果を消し、大項目・中項目選択の表示に戻る。検索確定中は、新規登録ボタンと並び替えモード切替ボタンを無効にする。

### 完了条件

- [ ] カンマ区切りの複数キーワードで検索でき、全キーワードに一致する結果だけが出る
- [ ] 検索結果に大項目・中項目名（または「未分類」）が表示される
- [ ] 検索結果の行選択で詳細表示が開く
- [ ] クリアで大項目・中項目選択の表示に戻る
- [ ] 検索確定中は新規登録・並び替えモードが無効になる
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 14

### タイトル

nginx の配置例を置く

### 見積もり

1時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / 構成
- `ui-design.md` / 画面一覧（パス `/portal_knowhow_management/`）
- `rules/17-nginx-deploy.md`

### 実装パス

- `src/features/knowhow-management/frontend/nginx.example.conf`

### 内容

公開 URL `/portal_knowhow_management/`、ディスクは `features/knowhow-management/`。スラッシュなしは 301 で付ける。`rewrite` は `last`。`features/knowhow-management/` は `internal`。API を同一オリジンにする場合の `proxy_pass` 例をコメントで置く。

### 完了条件

- [ ] 公開 URL とディスク配置が規則どおりである
- [ ] `rewrite` が `last` である
- [ ] スラッシュなしの location がある

---

## タスク 15

### タイトル

別サーバ版（`sample/knowhow`）からのデータ移行スクリプトを作成する

### 見積もり

3時間

### 関連要件

- （`requirements.md` の対象外。運用作業として実施）

### 関連設計

- `db-design.md` / テーブル設計（移行先）

### 実装パス

- `src/features/knowhow-management/backend/scripts/export_from_knowhow.py`（新規）
- `src/features/knowhow-management/backend/scripts/import_to_knowhow_management.py`（新規）
- `src/features/knowhow-management/backend/scripts/README.md`（新規。実行手順）

### 内容

**エクスポート**（別サーバ側で実行する）: 接続情報を引数・環境変数で受け取り、`public.accounts`（`id`・`username`）、`public.major_categories`・`public.middle_categories`・`public.knowhows`（いずれも `is_deleted = false` の行）を読み、JSON ファイルへ出力する。

**インポート**（本プロジェクトの DB に対して実行する）: `backend/.env` の接続情報を使う。旧 `accounts.username` と、本プロジェクトの `public.users.username` を突合し、一致するユーザのぶんだけ移行する。一致しないユーザ名は対象外として一覧表示する。大項目→中項目→ノウハウの順で、旧 ID と新 ID の対応表を保ちながら挿入する（中項目は親大項目の新 ID を、ノウハウは所属中項目の新 ID を使う）。移行先で名称が重複する大項目・中項目はスキップして一覧表示する（`display_order` は移行元の値を引き継ぐ）。処理件数（テーブルごとの成功・スキップ・対象外）を最後にまとめて表示する。

### 完了条件

- [ ] エクスポートスクリプトが、3テーブルの未削除行とアカウント一覧を JSON へ出力する
- [ ] インポートスクリプトが、username で新旧ユーザを突合し、一致しないものを対象外として一覧表示する
- [ ] インポートスクリプトが、大項目→中項目→ノウハウの親子関係を新 ID で正しく張り直す
- [ ] 移行先で名称が重複する大項目・中項目をスキップし、一覧表示する
- [ ] 成功・スキップ・対象外の件数がテーブルごとに表示される
- [ ] `scripts/README.md` に実行手順が書かれている

---

## テスト

### 単体テスト

- [ ] `src/features/knowhow-management/tests/` に配置する
- [ ] 大項目・中項目の名称の空白のみ拒否、名称重複（新規・更新、自身除外）を確認する
- [ ] 大項目・中項目の論理削除で、配下が連鎖して論理削除されることを確認する
- [ ] ノウハウのタイトル・本文の空白のみ拒否、`display_order` の採番・再採番を確認する
- [ ] キーワード検索の AND 一致、大文字小文字を区別しないことを確認する
- [ ] 並び替えで所属先が一致しない2件を指定すると失敗することを確認する
- [ ] 他ユーザの行が一覧・単件取得・更新・削除・並び替えの対象にならないことを確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、404、409、settings、大項目・中項目・ノウハウの CRUD、検索、並び替え）
- [ ] 操作ログ（入力・判断・失敗理由、セッション ID の非出力）

### 受け入れテスト

- [ ] `requirements.md` の受け入れ条件（REQ-001〜REQ-016）を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 10:45 | 未承認 | 初版 |
| 2026-09-20 10:46 | 承認済み | 初版を承認 |
