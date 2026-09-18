# タスク: portal（ログインとメニュー）

## 概要

対象機能: `portal`

ソース配置:

- フロントエンド: `src/features/portal/frontend`
- バックエンド: `src/features/portal/backend`
- テスト: `src/features/portal/tests`

関連要件:

- REQ-001 〜 REQ-020

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口を用意する

### 見積もり

2時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`）

### 実装パス

- `src/features/portal/backend/app/main.py`
- `src/features/portal/backend/app/config.py`
- `src/features/portal/backend/.env`（ひな型: `docs/specs/templates/backend.env.example`）
- `src/features/portal/backend/requirements.txt`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB、CORS、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER` を読む。CORS は具体オリジン、資格情報付き。秘密情報をソースに直書きしない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8000` が起動できる
- [ ] 秘密情報をソースに直書きしていない

---

## タスク 2

### タイトル

開発用 DB を用意し、`public` の DDL とシステム設定の初期データを入れる

### 見積もり

4時間

### 関連要件

- REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-010, REQ-011

### 関連設計

- `db-design.md` / テーブル設計
- `db-design.md` / `public.system_settings` の初期データ
- `design.md` / バックエンド設計 / モジュール構成（`sql/`）
- `.cursor/rules/13-db.mdc` / 開発用 DB

### 実装パス

- `src/features/portal/backend/sql/`

### 内容

管理者 `postgres`（localhost:5432、パスワード `postgres`）で、データベース `tstdb` とユーザ `tstuser`（パスワード `TSTPASS`）を作る。無ければ作成し、あれば使う。続けて `users`、`sessions`、`system_settings`、`features`、`menu_assignments` を `public` に作る SQL を置く。システム設定 5 キーを初期登録する。アイコンは小さな PNG のバイト列と `image/png` を入れる。リポジトリに配信用画像ファイルは置かない。アプリからの接続は `tstuser` / `tstdb`（`.env` のひな型どおり）。

### 完了条件

- [ ] `tstdb` と `tstuser` がある
- [ ] `db-design.md` の表・制約・初期キーが SQL にある
- [ ] `tstuser` で tstdb に適用できる
- [ ] 配信用の画像ファイルをディスクに置いていない

---

## タスク 3

### タイトル

DB 接続とデータアクセスを実装する

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-002, REQ-003, REQ-004, REQ-010, REQ-011

### 関連設計

- `design.md` / バックエンド設計 / データアクセス
- `db-design.md` / テーブル設計

### 実装パス

- `src/features/portal/backend/app/db.py`
- `src/features/portal/backend/app/` 配下のデータアクセス

### 内容

PostgreSQL へ接続する。ユーザ、セッション、システム設定、機能マスタ、メニュー割当の取得・追加・更新・論理削除・行削除を、設計の役割どおりに実装する。パスワードはハッシュ列のみ扱う。

### 完了条件

- [ ] `.env` の接続情報（tstdb / tstuser）で接続できる
- [ ] 各表へのアクセス関数がある（型ヒント付き）
- [ ] 接続情報をソースに直書きしていない

---

## タスク 4

### タイトル

認証（ログイン・ログアウト・セッション確認）の API を実装する

### 見積もり

4時間

### 関連要件

- REQ-001, REQ-002, REQ-003, REQ-006, REQ-007, REQ-008, REQ-009

### 関連設計

- `design.md` / バックエンド設計 / 認証 / 認可
- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / POST `/auth/login`、POST `/auth/logout`、GET `/auth/session`
- `api-design.md` / 共通 / 認証

### 実装パス

- `src/features/portal/backend/app/security.py`
- `src/features/portal/backend/app/deps.py`
- `src/features/portal/backend/app/services/auth_service.py`
- `src/features/portal/backend/app/routers/auth.py`

### 内容

パスワードのハッシュ化と比較、セッション Cookie（`session_id`、HttpOnly、SameSite=Lax、本番 Secure）を実装する。ログイン成功で既存セッションを消して新規作成。失敗は詳細を分けない。未ログイン・期限切れは 401。`DEBUG_USER` を実装する。セッション ID を本文に出さない。

### 完了条件

- [ ] POST `/auth/login` が 204 + Cookie、失敗は 401「ログインできませんでした」
- [ ] POST `/auth/logout` がセッション行と Cookie を消す
- [ ] GET `/auth/session` がユーザ名のみ返す
- [ ] 論理削除ユーザではログインできない

---

## タスク 5

### タイトル

システム設定取得 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-004, REQ-005

### 関連設計

- `api-design.md` / GET `/settings`
- `api-design.md` / 共通 / アイコンの載せ方
- `design.md` / バックエンド設計 / モジュール構成（`app/routers/settings.py`）

### 実装パス

- `src/features/portal/backend/app/routers/settings.py`

### 内容

必須キー 5 件を返す。アイコンは data URL にする。認証不要。キー欠けは 500。

### 完了条件

- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] `icon_*` が data URL である
- [ ] 本文にセッション ID を含まない

---

## タスク 6

### タイトル

メニュー取得 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-005, REQ-012, REQ-013, REQ-014

### 関連設計

- `api-design.md` / GET `/menu`
- `design.md` / バックエンド設計 / 業務ロジック
- `design.md` / バックエンド設計 / モジュール構成（`menu_service`, `access_service`）
- `db-design.md` / `public.menu_assignments`

### 実装パス

- `src/features/portal/backend/app/services/menu_service.py`
- `src/features/portal/backend/app/services/access_service.py`
- `src/features/portal/backend/app/routers/menu.py`

### 内容

ログイン中ユーザの、未削除機能の割当だけを表示順で返す。アイコンは data URL。空なら `items` は `[]`。他ユーザ分は返さない。`access_service` でユーザと機能の有効な割当を判定する（本機能内。他機能向け API にはしない）。

### 完了条件

- [ ] GET `/menu` がログイン必須（401）
- [ ] 自分の未削除機能だけが、表示順で返る
- [ ] 割当なしは空配列
- [ ] 他機能向けの判定 API を公開していない

---

## タスク 7

### タイトル

運用コマンド（ユーザ）を実装する

### 見積もり

2時間

### 関連要件

- REQ-015, REQ-016, REQ-017

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（運用コマンド）
- `design.md` / バックエンド設計 / モジュール構成（`app/cli.py`）
- `db-design.md` / `public.users`

### 実装パス

- `src/features/portal/backend/app/cli.py`

### 内容

同じ venv で、ユーザ一覧（未削除）、ユーザ追加（ユーザ名とパスワード、ハッシュ化）、ユーザ論理削除をコマンドで行う。存在しない／既削除の削除は失敗にする。

### 完了条件

- [ ] 未削除ユーザの一覧が出る
- [ ] 追加したユーザでログインできる
- [ ] 論理削除後は一覧とログインの対象外になる
- [ ] 既削除・不存在の削除は失敗する

---

## タスク 8

### タイトル

運用コマンド（機能と割当）を実装する

### 見積もり

3時間

### 関連要件

- REQ-010, REQ-011, REQ-018, REQ-019

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（運用コマンド）
- `db-design.md` / `public.features`、`public.menu_assignments`

### 実装パス

- `src/features/portal/backend/app/cli.py`

### 内容

機能の追加・更新・論理削除（識別子、タイトル、遷移先 URL、任意のアイコンファイルからバイト列とメディアタイプ）。アイコンを省略したときはなしで登録する。ユーザへ機能を表示順付きで割り当て、外す。重複割当、未削除でない対象、未割当の解除は失敗にする。アイコンは DB に格納し、配信用ファイルはリポジトリに置かない。

### 完了条件

- [ ] 機能の追加・更新・論理削除ができる
- [ ] アイコンなしで機能を追加できる
- [ ] 割当の追加・削除ができる
- [ ] 失敗条件（重複、不存在、既削除、未割当の解除）で失敗する
- [ ] 配信用の画像ファイルをリポジトリに置いていない

---

## タスク 9

### タイトル

フロントエンドの Vue 起動、外枠、ルーティングを用意する

### 見積もり

3時間

### 関連要件

- REQ-004, REQ-009

### 関連設計

- `design.md` / フロントエンド設計 / API クライアント
- `ui-design.md` / 共通UI
- `ui-design.md` / 画面遷移
- `api-design.md` / GET `/settings`、GET `/auth/session`

### 実装パス

- `src/features/portal/frontend/`
- `src/features/portal/frontend/.env`（ひな型: `docs/specs/templates/frontend.env.example`。変数名は `VITE_API_PORTAL_URL`）

### 内容

`npm run dev` で起動する。トークンと外枠（ヘッダ / ナビ / コンテンツ。PC は左ナビ、スマートフォンは下ナビ）を `15-ui-style.mdc` どおりに置く。`--color-primary` は `#8FB4FF`。Vite `base` は `/portal/`。`/portal/` はセッション確認で `/portal/login` または `/portal/menu` へ進む。API は `VITE_API_PORTAL_URL` と credentials のみ。セッション ID をフロントに持たない。ヘッダにシステムアイコンを出す。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_PORTAL_URL` で API を呼び、ホストを直書きしていない
- [ ] `/portal/` がログイン状態に応じて誘導する
- [ ] セッション ID を `localStorage` や URL に置いていない

---

## タスク 10

### タイトル

ログイン画面を実装する

### 見積もり

2時間

### 関連要件

- REQ-006, REQ-007

### 関連設計

- `ui-design.md` / SCR-001 ログイン
- `api-design.md` / POST `/auth/login`

### 実装パス

- `src/features/portal/frontend/` のログイン画面

### 内容

ユーザ名とパスワード、主ボタン「ログイン」。入力欄の上にポータルのロゴ（`src/assets/Mugi2.png`）を置く。空なら送らない。読込中は「読み込み中…」で操作無効。失敗は「ログインできませんでした」のみ。成功は `/portal/menu` へ。ナビは「ログイン」のみ。

### 完了条件

- [ ] 正しい資格情報でメニューへ進める
- [ ] 失敗時は詳細を出さず、入力は残る
- [ ] 空入力は送信しない
- [ ] ログイン画面にポータルのロゴが出る

---

## タスク 11

### タイトル

メニュー画面とログアウトを実装する

### 見積もり

3時間

### 関連要件

- REQ-005, REQ-008, REQ-009, REQ-012, REQ-013

### 関連設計

- `ui-design.md` / SCR-002 メニュー
- `api-design.md` / GET `/menu`、POST `/auth/logout`

### 実装パス

- `src/features/portal/frontend/` のメニュー画面

### 内容

割当機能をカード（アイコンとタイトル）で表示順に出す。押すと遷移先 URL へ進む。空は「データがありません」。未ログインは内容を見せず `/portal/login` へ。ログアウトはヘッダのテキストボタンで、実行後 `/portal/login`。PC はカード複数列、スマートフォンは単一列。ナビは「メニュー」のみ。

### 完了条件

- [ ] 自分の未削除機能だけが並ぶ
- [ ] カードから遷移先へ進める
- [ ] ログアウト後はログイン画面へ進む
- [ ] 未ログインでメニューを開くとログイン画面へ進む

---

## タスク 12

### タイトル

ログイン試行のファイルログを実装する

### 見積もり

2時間

### 関連要件

- REQ-007, REQ-020

### 関連設計

- `design.md` / バックエンド設計 / モジュール構成（`app/logger.py`, `log/`）
- `design.md` / バックエンド設計 / 業務ロジック（ログインのログ）
- `.cursor/rules/16-logging.mdc`

### 実装パス

- `src/features/portal/backend/app/logger.py`
- `src/features/portal/backend/app/config.py`
- `src/features/portal/backend/app/main.py`
- `src/features/portal/backend/app/services/auth_service.py`
- `src/features/portal/backend/app/routers/auth.py`
- `src/features/portal/backend/.env`（ひな型: `docs/specs/templates/backend.env.example`）
- `src/features/portal/tests/`

### 内容

`backend/log/` へファイルログを出す。1 行はタイムスタンプ、区分（INF / WRN / ERR / DBG）、メッセージ。ログインが試みられたとき、ユーザ名（入力）、判断結果、失敗時の内部理由を出す。パスワードとセッション ID は出さない。画面へ返す失敗文言は従来どおり詳細を出さない。`.env` の `LOG_MAX_BYTES` と `LOG_BACKUP_COUNT` でサイズローテーションする。開発用初期値は 10485760 と 5。起動時にロガーを初期化する。

### 完了条件

- [ ] ログイン成功で INF が残り、ユーザ名と判断結果が含まれる
- [ ] ログイン失敗で WRN が残り、画面へ出さない内部理由が含まれる
- [ ] パスワードとセッション ID がログに含まれない
- [ ] `LOG_MAX_BYTES` と `LOG_BACKUP_COUNT` を `.env` から読む
- [ ] ログファイルをリポジトリに含めていない

---

## テスト

### 単体テスト

- [ ] `src/features/portal/tests/` に配置する
- [ ] パスワードハッシュ、論理削除ユーザの認証拒否、メニューが自ユーザ・未削除のみ、data URL 化を確認する
- [ ] ログイン成功・失敗のログ（ユーザ名・判断・失敗理由、パスワード非出力）を確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（ログイン Cookie、設定、メニュー、401）
- [ ] 運用コマンドのユーザ・機能・割当の成功と失敗

### 受け入れテスト

- [ ] requirements.md の受け入れ条件を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-26 08:54 | 未承認 | 初版 |
| 2026-08-26 09:16 | 未承認 | 開発用 DB を TSTDB / TSTUSER に変更。作成手順をタスク 2 に追加 |
| 2026-08-26 09:21 | 未承認 | 開発用 DB 名とユーザ名を小文字（tstdb / tstuser）に変更 |
| 2026-08-26 09:44 | 承認済み | タスクを承認 |
| 2026-08-26 22:14 | 未承認 | タスク 12（ログイン試行のファイルログ）を追加 |
| 2026-08-26 22:16 | 承認済み | タスク 12（ログイン試行のファイルログ）を承認 |
| 2026-08-26 23:40 | 未承認 | 機能追加のアイコンを省略可能にする |
| 2026-08-26 23:45 | 承認済み | 機能追加のアイコン省略を承認 |
| 2026-08-27 19:40 | 未承認 | ログイン画面にポータルのロゴを置く |
| 2026-08-27 20:39 | 承認済み | ログイン画面にポータルのロゴを置く改訂を承認 |
| 2026-08-29 17:15 | 未承認 | 公開パスの基点を `/portal/` にする |
| 2026-08-29 19:19 | 承認済み | 公開パス `/portal/` の改訂を承認 |
