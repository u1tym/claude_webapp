# api-key-management（APIキー管理）タスク分解

> `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後に作成する。
> タスクは 1〜4 時間程度で完了できる粒度にする。

## 概要

対象機能: `api-key-management`（本機能）と、API キー認証を追加する対象機能 `goods-management`、`expense-management`、`knowhow-management`、`schedule`。

対象機能の改修は、各対象機能の改訂済み SPEC（`requirements.md` / `design.md` / `db-design.md` / `api-design.md`。2026-09-26 承認）に従う。対象機能の `tasks.md` は改訂せず、改修のタスクは本書に置く。

ソース配置:

- フロントエンド: `src/features/api-key-management/frontend`（開発ポート 5184、`base` は `/portal_api_key_management/`）
- バックエンド: `src/features/api-key-management/backend`（`uvicorn app.main:app --reload --port 8010`）
- テスト: `src/features/api-key-management/tests`
- 対象機能: `src/features/<対象機能>/backend`、`src/features/<対象機能>/tests`

守ること:

- `portal`・対象機能・本機能は、互いの Python を import しない。対象機能の API キーの判定は、各対象機能に同じ方式でコードを置く。
- `public.api_keys` 以外の `public` の表は読むだけ（列を変えない）。
- API キー全体とそのハッシュ、セッション ID、パスワード、Cookie はログ・URL・`localStorage` に置かない。
- `--color-primary` は Amber `#F2C94C`。

## タスク一覧

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-001 | バックエンドの起動口・設定・DB 接続・ログ | REQ-001、REQ-008 / design.md §バックエンド設計（起動・モジュール構成） | `src/features/api-key-management/backend/` | 2h | 下記 T-001 |
| T-002 | `public.api_keys` の DDL と適用スクリプト | REQ-003〜REQ-007 / db-design.md §`public.api_keys` | `src/features/api-key-management/backend/sql/` | 1h | 下記 T-002 |
| T-003 | Cookie 認証・割当判定・GET `/settings` | REQ-001 / design.md §認証 / 認可（本機能）、api-design.md §共通事項（認証）・GET `/settings` | `src/features/api-key-management/backend/app/` | 2h | 下記 T-003 |
| T-004 | API キーの発行・一覧・失効の API | REQ-002〜REQ-005、REQ-008 / design.md §業務ロジック、db-design.md §本機能の扱い、api-design.md §GET・POST `/api-keys`、POST `/api-keys/{api_key_id}/revoke` | `src/features/api-key-management/backend/app/` | 4h | 下記 T-004 |
| T-005 | 本機能のバックエンドのテスト | REQ-001〜REQ-005、REQ-008 / api-design.md 全体 | `src/features/api-key-management/tests/` | 3h | 下記 T-005 |
| T-006 | フロントの土台（殻・API クライアント・設定取得・未ログイン誘導） | REQ-001 / design.md §フロントエンド設計、ui-design.md §SCR-001（ヘッダ・ナビ・状態） | `src/features/api-key-management/frontend/` | 3h | 下記 T-006 |
| T-007 | API キー一覧画面（SCR-001） | REQ-004 / ui-design.md §SCR-001 | `src/features/api-key-management/frontend/src/` | 3h | 下記 T-007 |
| T-008 | 発行・発行結果・失効の確認のダイアログ（DLG-001〜003） | REQ-003、REQ-005 / ui-design.md §DLG-001〜DLG-003、画面遷移 | `src/features/api-key-management/frontend/src/` | 3h | 下記 T-008 |
| T-009 | nginx 配置例と機能マスタへの登録 | REQ-001 / design.md §デプロイ上の考慮 | `src/features/api-key-management/frontend/nginx.example.conf` | 1h | 下記 T-009 |
| T-010 | goods-management の API キー認証 | REQ-006〜REQ-008 / api-design.md §対象機能の API キー認証、goods-management の design.md §認証 / 認可・api-design.md §認証 | `src/features/goods-management/backend/`、`src/features/goods-management/tests/` | 3h | 下記 T-010〜T-013 |
| T-011 | expense-management の API キー認証 | 同上（expense-management の改訂 SPEC） | `src/features/expense-management/backend/`、`src/features/expense-management/tests/` | 3h | 下記 T-010〜T-013 |
| T-012 | knowhow-management の API キー認証 | 同上（knowhow-management の改訂 SPEC） | `src/features/knowhow-management/backend/`、`src/features/knowhow-management/tests/` | 3h | 下記 T-010〜T-013 |
| T-013 | schedule の API キー認証 | 同上（schedule の改訂 SPEC） | `src/features/schedule/backend/`、`src/features/schedule/tests/` | 3h | 下記 T-010〜T-013 |
| T-014 | 通しの確認（画面で発行 → 他システム相当から利用 → 失効） | REQ-003〜REQ-007 | なし（確認のみ。不具合は該当タスクのパスで直す） | 2h | 下記 T-014 |

---

## T-001: バックエンドの起動口・設定・DB 接続・ログ

**実装パス**

- `src/features/api-key-management/backend/app/main.py`、`config.py`、`logger.py`、`db.py`、`errors.py`
- `src/features/api-key-management/backend/requirements.txt`
- `src/features/api-key-management/backend/.env`（ひな型: `specs/templates/backend.env.example`）

**内容**

backend 配下に venv を作り、uvicorn で起動できるようにする。`.env` から DB 接続情報、`CORS_ORIGINS`、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジン・資格情報付き。`log/` へサイズでローテーションするロガーを初期化する。要求検証の失敗を 400 `{"detail":"入力が不正です"}`、未処理例外を 500 `{"detail":"サーバエラーです"}` にする例外ハンドラを置く。

**完了条件**

- [ ] `backend/venv` があり、`uvicorn app.main:app --reload --port 8010` で起動できる
- [ ] `.env` の接続情報（tstdb / tstuser）で DB に接続できる
- [ ] ログが `log/` に「タイムスタンプ 区分 メッセージ」で出て、`LOG_MAX_BYTES`・`LOG_BACKUP_COUNT` でローテーションする
- [ ] 秘密情報をソースに直書きしていない。`log/`・`.env`・`venv/` はリポジトリに含めない

## T-002: `public.api_keys` の DDL と適用スクリプト

**実装パス**

- `src/features/api-key-management/backend/sql/01_api_keys.sql`
- `src/features/api-key-management/backend/sql/apply.py`

**内容**

`db-design.md` のとおり、`public.api_keys`（列、主キー、`key_hash` の一意制約、`user_id` の外部キー ON DELETE RESTRICT、検査制約 3 つ、`api_keys_user_created_idx`）を `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` で作る。`apply.py` は `.env` の接続で SQL を適用する。`portal` の DDL が適用済みであることを前提とする。

**完了条件**

- [ ] `apply.py` の実行で `public.api_keys` が作られ、再実行してもエラーにならない
- [ ] 列・型・NULL・既定値・制約・インデックスが `db-design.md` と一致する
- [ ] 名前が空白だけ、`expires_at <= created_at` の行は DB が拒否する

## T-003: Cookie 認証・割当判定・GET `/settings`

**実装パス**

- `src/features/api-key-management/backend/app/security.py`（Cookie 名、セッション期限の計算）
- `src/features/api-key-management/backend/app/deps.py`
- `src/features/api-key-management/backend/app/repos.py`（ユーザ・セッション・システム設定・機能・割当の読み取り）
- `src/features/api-key-management/backend/app/services/access_service.py`
- `src/features/api-key-management/backend/app/routers/settings.py`

**内容**

Cookie `session_id` でログイン中ユーザを特定し、セッションの期限を延ばす。未ログイン・期限切れ・ユーザ削除済みは 401、識別子 `api-key-management` の割当なし・機能削除済みは 403。`DEBUG_USER` でも割当を判定する。`Authorization` ヘッダは参照しない（API キーでは利用させない）。GET `/settings` は認証不要で `login_url`、`menu_url`、`icon_system`、`icon_back`（data URL）を返し、欠けていれば 500。

**完了条件**

- [ ] 未ログインの操作 API が 401「未ログイン」、割当なしが 403「権限がありません」
- [ ] `Authorization: Bearer <有効なキー>` だけを添えた要求も 401 になる
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 認証の失敗がログに理由付きで出る（セッション ID は出ない）

## T-004: API キーの発行・一覧・失効の API

**実装パス**

- `src/features/api-key-management/backend/app/security.py`（キーの生成・SHA-256・先頭 12 文字）
- `src/features/api-key-management/backend/app/repos.py`（`public.api_keys` の挿入・一覧・失効）
- `src/features/api-key-management/backend/app/services/api_key_service.py`
- `src/features/api-key-management/backend/app/routers/api_keys.py`

**内容**

- キー全体は `wak_` + `secrets.token_urlsafe(32)`（43 文字）。保存は SHA-256（16 進小文字）と先頭 12 文字だけ。
- POST `/api-keys`: 名前は前後の空白を除いて 1〜100 文字。`expires_at` はタイムゾーン付き ISO 8601 で、現在より後。省略・null は無期限。`key_hash` の一意制約違反なら生成し直す。201 でキー全体を含めて返す。
- GET `/api-keys`: 本人の全件を `created_at` 降順。`status`（`active` / `expired` / `revoked`）を判定して返す。`key` とハッシュは返さない。
- POST `/api-keys/{api_key_id}/revoke`: 本人の未失効の行だけ `revoked_at = now()`。他人・存在しないは 404、失効済みは 409「既に失効しています」。期限切れは失効できる。200 で失効後の 1 件を返す。
- 応答の日時は UTC（`Z`）。
- ログ: 発行・一覧・失効の入力（ユーザ名、名前、有効期限、ID、先頭部分）、結果、失敗の理由。キー全体・ハッシュは出さない。

**完了条件**

- [ ] `api-design.md` の要求・応答・エラーと一致する
- [ ] DB にキー全体が保存されていない（`key_hash` と `key_prefix` のみ）
- [ ] 発行の応答以外にキー全体が現れない
- [ ] 他人の API キーは一覧に出ず、失効は 404 になる
- [ ] ログにキー全体・ハッシュが出ない

## T-005: 本機能のバックエンドのテスト

**実装パス**

- `src/features/api-key-management/tests/conftest.py`
- `src/features/api-key-management/tests/test_auth.py`
- `src/features/api-key-management/tests/test_api_keys.py`

**内容**

pytest と FastAPI の TestClient で、開発用 DB（tstdb）に対して API を検証する。テスト用のユーザ・機能・割当・セッションを用意し、後始末する。

**完了条件**

- [ ] 認証: 未ログイン 401、割当なし 403、ユーザ削除済み 401、API キーだけの要求 401、GET `/settings` 200
- [ ] 発行: 正常（無期限・期限付き）、名前が空・101 文字、期限が過去・タイムゾーンなしで 400
- [ ] 一覧: 本人分のみ、降順、状態（有効・期限切れ・失効済み）、`key` を含まない
- [ ] 失効: 正常、期限切れの失効、失効済み 409、他人・存在しない 404
- [ ] ログにキー全体が出ていないことを検証する
- [ ] `backend/venv` の pytest で全件成功する

## T-006: フロントの土台（殻・API クライアント・設定取得・未ログイン誘導）

**実装パス**

- `src/features/api-key-management/frontend/package.json`、`vite.config.ts`（`base: "/portal_api_key_management/"`、port 5184）、`tsconfig.json`、`index.html`
- `src/features/api-key-management/frontend/.env`（`VITE_API_API_KEY_MANAGEMENT_URL=http://localhost:8010`）
- `src/features/api-key-management/frontend/src/main.ts`、`App.vue`、`router.ts`、`styles.css`
- `src/features/api-key-management/frontend/src/api/`
- `src/features/api-key-management/frontend/src/components/`（ヘッダ、ナビ、`Icon.vue`）

**内容**

`rules/15-ui-style.md` のトークン（`--color-primary: #F2C94C`）と殻（PC は左ナビ、768px 未満は下端ナビ）を実装する。`Icon.vue` は `icons/` の `back`、`config`、`new`、`check`、`close`、`stop` を `fill="currentColor"` にして複製する。API クライアントは Cookie を送り（credentials）、401 ならログイン URL へ遷移、403 なら権限なしの状態にする。`/settings` を取得して保持する。

**完了条件**

- [ ] `npm run dev` で起動し、`/portal_api_key_management/` で殻が表示される
- [ ] 未ログインでログイン URL へ遷移する。戻るでメニュー URL へ遷移する
- [ ] PC とスマートフォン幅でナビの位置が切り替わる
- [ ] 他機能の Vue・CSS・コンポーネントを import していない

## T-007: API キー一覧画面（SCR-001）

**実装パス**

- `src/features/api-key-management/frontend/src/views/ApiKeyListView.vue`
- `src/features/api-key-management/frontend/src/components/`（一覧の行・カード、状態ラベル）

**内容**

`ui-design.md` の SCR-001 のとおり、見出し・説明文・新規ボタン・メッセージ領域・一覧を置く。PC は表（名前 / 状態 / 先頭部分 / 有効期限 / 最終利用 / 発行日時 / 操作）、スマートフォンはカード。日時はローカル時刻 `YYYY-MM-DD HH:mm`、無期限・未使用の表示、失効日時の表示、状態は文字で示す。失効ボタンは有効・期限切れの行だけ。読込中・空・エラー・権限なし・成功の表示。

**完了条件**

- [ ] 一覧の項目・並び・状態別の表示が `ui-design.md` と一致する
- [ ] 失効済みの行に失効ボタンが出ない
- [ ] ヘッダ行固定・本体だけスクロール。ページ全体はスクロールしない
- [ ] ボタンに `aria-label` があり、キーボードで操作できる

## T-008: 発行・発行結果・失効の確認のダイアログ（DLG-001〜003）

**実装パス**

- `src/features/api-key-management/frontend/src/components/IssueDialog.vue`
- `src/features/api-key-management/frontend/src/components/IssuedKeyDialog.vue`
- `src/features/api-key-management/frontend/src/components/RevokeConfirmDialog.vue`

**内容**

- DLG-001: 名前（必須）と有効期限（日付と時刻、任意）。送信前の検証（空・過去）。有効期限はタイムゾーン付き ISO 8601 に変換して送る。
- DLG-002: 注意書き、名前、キー全体（押すと全選択）、「コピー」ボタン（クリップボード、成功・失敗の表示）、`Authorization: Bearer <キー>` の説明、閉じる。閉じたらキーを状態から破棄し、一覧を取得し直す。
- DLG-003: 対象（名前・先頭部分）と確認文、キャンセル・失効。成功で一覧を取得し直し、成功メッセージ。
- 共通: 背景のクリックで閉じない。送信中はボタンを無効にする。スマートフォンでは画面下からのシート。

**完了条件**

- [ ] 画面遷移が `ui-design.md` の表と一致する
- [ ] 発行したキー全体が、DLG-002 を閉じた後に画面・`localStorage`・URL に残らない
- [ ] コピーボタンでクリップボードにキー全体が入る
- [ ] 検証エラー・送信失敗の文言が `ui-design.md` と一致する

## T-009: nginx 配置例と機能マスタへの登録

**実装パス**

- `src/features/api-key-management/frontend/nginx.example.conf`

**内容**

`rules/17-nginx-deploy.md` に従い、`/portal_api_key_management/` → `features/api-key-management/` の配置例を書く。運用として、ユーザ管理の画面で機能マスタに `api-key-management`（タイトル「API キー管理」、遷移先は公開 URL）を追加し、利用ユーザへ割り当てる。

**完了条件**

- [ ] 配置例が `rules/17-nginx-deploy.md` の形（スラッシュなしの 301、`rewrite ... last`、`internal` と `try_files`）になっている
- [ ] 開発環境の機能マスタに `api-key-management` があり、利用ユーザのメニューから開ける

## T-010〜T-013: 対象機能の API キー認証

4 つの対象機能それぞれに、同じ内容を実装する（1 機能 = 1 タスク）。

| No | 対象機能 | 実装パス |
|----|----------|----------|
| T-010 | `goods-management` | `backend/app/deps.py`、`backend/app/security.py`、`backend/app/repos.py`、`tests/test_api_key_auth.py` |
| T-011 | `expense-management` | `backend/app/deps.py`、`backend/app/security.py`、`backend/app/repos_shared.py`、`tests/test_api_key_auth.py` |
| T-012 | `knowhow-management` | `backend/app/deps.py`、`backend/app/security.py`、`backend/app/repos.py`、`tests/test_api_key_auth.py` |
| T-013 | `schedule` | `backend/app/deps.py`、`backend/app/security.py`、`backend/app/repos.py`、`tests/test_api_key_auth.py` |

（パスは `src/features/<対象機能>/` からの相対）

**内容**

- `security.py`: キーの SHA-256（16 進小文字）を求める関数を足す（本機能と同じ方式。コードは複製する）。
- `repos`: `key_hash` で `public.api_keys` と持ち主の `public.users` を読む関数と、`last_used_at = now()` にする関数を足す。
- `deps.py` の `get_current_user`:
  - `Authorization` ヘッダがあれば API キーで判定する。`Bearer` でない・空・該当なし・失効済み・期限切れ・持ち主削除済みは 401（`WWW-Authenticate: Bearer` を付ける）。割当なし・機能削除済みは 403（既存の `is_feature_allowed` を使う）。許可したら `last_used_at` を更新し、持ち主で `AuthContext` を返す（`session_id` は None、セッション期限は延ばさない）。
  - ヘッダが無ければ従来の処理（`DEBUG_USER`・Cookie）のまま。ヘッダがあるときは従来の処理へ戻らない。
- ログ: 許可は INF（ユーザ名、API キーの ID、先頭部分）、拒否は WRN（理由。該当なしは添えられた値の先頭 12 文字だけ）。キー全体・ハッシュは出さない。
- GET `/settings` と業務の API のコードは変えない。

**完了条件（各対象機能）**

- [ ] 有効なキーで、Cookie なしに業務の API が 200 になり、持ち主本人のデータだけが返る
- [ ] 該当なし・失効済み・期限切れ・持ち主削除済み・`Bearer` 以外のヘッダで 401 と `WWW-Authenticate: Bearer`
- [ ] 持ち主に当該機能の割当がないとき 403
- [ ] 無効なキーと有効な Cookie を同時に送っても 401（Cookie に戻らない）
- [ ] 許可時に `last_used_at` が更新され、拒否時は変わらない
- [ ] Cookie だけの従来の利用と、既存のテストがすべて成功する
- [ ] ログにキー全体・ハッシュが出ない
- [ ] 本機能・他の対象機能の Python を import していない

## T-014: 通しの確認

**内容**

開発環境で、本機能と 4 つの対象機能のバックエンドを起動し、次を確認する。他システムの代わりに `curl` 等で要求を送る。

**完了条件**

- [ ] 画面で API キーを発行し、発行結果のダイアログからコピーしたキーで、4 機能それぞれの一覧系 API が 200 になる
- [ ] 画面の一覧で、そのキーの最終利用日時が更新されている
- [ ] 画面で失効させた直後から、4 機能とも 401 になる
- [ ] 有効期限を短く設定したキーが、期限後に 401 になり、一覧で「期限切れ」になる
- [ ] 持ち主から 1 機能の割当を外すと、その機能だけ 403 になる
- [ ] 対象外の機能（例: `note-management`）にキーだけを送ると 401 になる
- [ ] 各機能の `log/` にキー全体が出ていない

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-26 00:46 | 未承認 | 初版 |
| 2026-09-26 00:46 | 承認済み | 初版を承認 |
