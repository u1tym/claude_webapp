# タスク: server-start（PC起動）

## 概要

対象機能: `server-start`

ソース配置:

- フロントエンド: `src/features/server-start/frontend`
- バックエンド: `src/features/server-start/backend`
- テスト: `src/features/server-start/tests`

関連要件:

- REQ-001 〜 REQ-007

`portal` の Python は import しない。表は `public` の既存を読むだけ。本機能の固有 DDL は作らない。本機能の機能マスタ登録と利用者への割当は、`portal` の運用コマンドで行う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-007

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`）
- `.cursor/rules/16-logging.mdc`

### 実装パス

- `src/features/server-start/backend/app/main.py`
- `src/features/server-start/backend/app/config.py`
- `src/features/server-start/backend/app/logger.py`
- `src/features/server-start/backend/.env`（ひな型: `docs/specs/templates/backend.env.example`）
- `src/features/server-start/backend/requirements.txt`
- `src/features/14_run_back_server_start.ps1`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB、CORS、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`、`PING_HOST`、`PING_TIMEOUT_SECONDS`、`WOL_MAC` を読む。値は ping 先 `192.168.2.178`、待ち時間 `2`、MAC `D8:43:AE:82:D0:F1`。CORS は具体オリジン、資格情報付き。起動時に `log/` へサイズローテーションするロガーを初期化する。`portal` を import しない。秘密情報と MAC・IP をソースに直書きしない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8003` が起動できる
- [ ] `PING_HOST`、`PING_TIMEOUT_SECONDS`、`WOL_MAC`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を `.env` から読む
- [ ] 秘密情報をソースに直書きしていない

---

## タスク 2

### タイトル

DB 接続と `public` への参照を実装する

### 見積もり

2時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / バックエンド設計 / データアクセス
- `db-design.md` / テーブル設計

### 実装パス

- `src/features/server-start/backend/app/db.py`
- `src/features/server-start/backend/app/` 配下のデータアクセス

### 内容

PostgreSQL へ接続する。ユーザ、セッション、システム設定、機能マスタ、メニュー割当の取得を、設計の役割どおりに実装する（参照のみ。追加・更新・論理削除はしない）。DDL は置かない。型ヒントを付ける。

### 完了条件

- [ ] `.env` の接続情報（tstdb / tstuser）で接続できる
- [ ] 各表への参照関数がある（型ヒント付き）
- [ ] SQL ファイルを追加していない
- [ ] 接続情報をソースに直書きしていない

---

## タスク 3

### タイトル

セッション検証、本機能の割当判定、設定取得 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-007

### 関連設計

- `design.md` / バックエンド設計 / 認証 / 認可
- `design.md` / バックエンド設計 / モジュール構成（`deps`, `access_service`, `settings`）
- `api-design.md` / 共通 / 認証
- `api-design.md` / GET `/settings`

### 実装パス

- `src/features/server-start/backend/app/security.py`
- `src/features/server-start/backend/app/deps.py`
- `src/features/server-start/backend/app/services/access_service.py`
- `src/features/server-start/backend/app/routers/settings.py`

### 内容

Cookie `session_id` でログイン中ユーザを特定する。未ログイン・期限切れは 401。識別子 `server-start` の割当が無ければ 403。`DEBUG_USER` でも割当を判定する。セッション ID を本文に出さない。GET `/settings` は認証不要で login_url、menu_url、icon_system、icon_back を返す。アイコンは data URL。認証が必要な要求のたびにセッション期限を延ばす。

運用として、`portal` の運用コマンドで機能 `server-start`（タイトル「PC起動」、遷移先は公開 URL `/portal_server_start/`）を追加し、利用ユーザへ割り当てる。

### 完了条件

- [ ] 未ログインの操作 API が 401「未ログイン」
- [ ] 割当なしの操作 API が 403「権限がありません」
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 本文にセッション ID を含まない
- [ ] 機能マスタに `server-start` があり、利用ユーザへ割り当てられている

---

## タスク 4

### タイトル

状態参照 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-002, REQ-007

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（ping）
- `design.md` / バックエンド設計 / モジュール構成（`status_service`, `power`）
- `api-design.md` / GET `/status`

### 実装パス

- `src/features/server-start/backend/app/services/status_service.py`
- `src/features/server-start/backend/app/routers/power.py`
- `src/features/server-start/tests/`

### 内容

GET `/status` はログインかつ割当必須。OS の ping を 1 回実行し、待ち時間内の応答があれば `is_up: true`、無ければ `false`。ping コマンド自体の失敗も `false` とし、内部理由をログに残す。ping 先と待ち時間は `.env`。入力（ユーザ名、ping 先、待ち時間）と判断（起動済み／未起動）をログへ出す。パスワードとセッション ID は出さない。

### 完了条件

- [ ] 未ログインは 401、割当なしは 403
- [ ] 応答に `is_up` がある
- [ ] ping 先と待ち時間をコードに直書きしていない
- [ ] 状態参照の要求と判断がログに残る

---

## タスク 5

### タイトル

起動処理と起動指示 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-003, REQ-004, REQ-005, REQ-006, REQ-007

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（起動処理）
- `design.md` / バックエンド設計 / モジュール構成（`start_service`, `scripts/wol.py`）
- `api-design.md` / POST `/start`

### 実装パス

- `src/features/server-start/backend/scripts/wol.py`
- `src/features/server-start/backend/app/services/start_service.py`
- `src/features/server-start/backend/app/routers/power.py`
- `src/features/server-start/tests/`

### 内容

`sample/wol.py` 相当を `scripts/wol.py` に置く。MAC は引数で受け取る。POST `/start` は同一 venv の Python でこれを実行する。`confirmed` は必須の真偽値。無い／真偽値でないときは 400。起動済みかどうかでは起動処理を拒否しない。終了コード 0 なら 204。失敗と実行中は 409「実行できませんでした」。起動処理は同時に 1 つ。成功判定に ping は使わない。入力（ユーザ名、MAC、confirmed）と判断（開始、成功、失敗、実行中拒否）と失敗理由をログへ出す。パスワードとセッション ID は出さない。

### 完了条件

- [ ] `confirmed` 無しは 400
- [ ] 正常終了は 204。本文なし
- [ ] 実行中の再指示は 409
- [ ] 起動処理失敗は 409。内部理由は本文に無い
- [ ] MAC をコードに直書きしていない
- [ ] 起動指示の入力・判断・失敗理由がログに残る

---

## タスク 6

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
- `.cursor/rules/15-ui-style.mdc`
- `.cursor/rules/17-nginx-deploy.mdc`

### 実装パス

- `src/features/server-start/frontend/`
- `src/features/server-start/frontend/.env`（ひな型: `docs/specs/templates/frontend.env.example`。変数名は `VITE_API_SERVER_START_URL`）
- `src/features/24_run_front_server_start.ps1`

### 内容

`npm run dev` で起動する。トークンと殻（ヘッダ / ナビ / コンテンツ。PC は左ナビ、スマートフォンは下ナビ）を `15-ui-style.mdc` どおりに置く。`--color-primary` は `#FF9A4A`。ナビは「PC起動」のみ。ヘッダに戻るとシステムアイコン。Vite `base` は `/portal_server_start/`。パスは `/portal_server_start/`。未ログインは GET `/settings` の login_url へ。割当なしは「この機能を使えません」。API は `VITE_API_SERVER_START_URL` と credentials のみ。セッション ID をフロントに持たない。他機能の Vue は import しない。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_SERVER_START_URL` で API を呼び、ホストを直書きしていない
- [ ] 未ログインでログイン画面 URL へ進む
- [ ] セッション ID を `localStorage` や URL に置いていない

---

## タスク 7

### タイトル

PC起動画面を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-006

### 関連設計

- `ui-design.md` / SCR-001 PC起動
- `api-design.md` / GET `/status`、POST `/start`

### 実装パス

- `src/features/server-start/frontend/` の PC起動画面

### 内容

開いた直後に状態を取得し、「起動済み」または「未起動」を示す。副ボタン「確認」で再取得。主ボタン「起動」。未起動なら `confirmed: false` で起動指示。起動済みなら確認ダイアログ（「起動済みです。続けて起動しますか？」）。続行は `confirmed: true`、キャンセルは送らない。成功は「起動を指示しました」（数秒で消す。実機が起きたことは書かない）。失敗は定型文のみ。読込中は「読み込み中…」、起動実行中は「起動を実行中…」で操作無効。状態未取得では起動ボタンを出さない。

### 完了条件

- [ ] 画面を開くと状態が出る。「確認」で再取得できる
- [ ] 未起動なら確認なしで起動を指示する
- [ ] 起動済みならダイアログのあとだけ起動を指示する。キャンセルでは送らない
- [ ] 成功メッセージが「起動を指示しました」である
- [ ] 実行中はボタンが無効で、重ねて送れない
- [ ] ブラウザで状態表示と起動指示を確認できる

---

## タスク 8

### タイトル

nginx の配置例を置く

### 見積もり

1時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / 構成
- `ui-design.md` / 画面一覧（パス `/portal_server_start/`）
- `.cursor/rules/17-nginx-deploy.mdc`

### 実装パス

- `src/features/server-start/frontend/nginx.example.conf`

### 内容

公開 URL `/portal_server_start/`、ディスクは `features/server-start/`。スラッシュなしは 301 で付ける。`rewrite` は `last`。`features/server-start/` は `internal`。API を同一オリジンにする場合の `proxy_pass` 例をコメントで置く。

### 完了条件

- [ ] 公開 URL とディスク配置が規則どおりである
- [ ] `rewrite` が `last` である
- [ ] スラッシュなしの location がある

---

## テスト

### 単体テスト

- [ ] `src/features/server-start/tests/` に配置する
- [ ] ping 応答あり／なし、起動処理の成功／失敗、実行中の再指示拒否を確認する
- [ ] `confirmed` 不正は 400、本文に内部理由が無いことを確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、409、settings、status、start）
- [ ] 操作ログ（入力・判断・失敗理由、パスワードとセッション ID の非出力）

### 受け入れテスト

- [ ] requirements.md の受け入れ条件を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-10 21:07 | 未承認 | 初版 |
| 2026-09-10 21:23 | 承認済み | 初版を承認 |
