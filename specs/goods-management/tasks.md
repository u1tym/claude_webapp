# タスク: goods-management（グッズ管理）

## 概要

対象機能: `goods-management`

ソース配置:

- フロントエンド: `src/features/goods-management/frontend`
- バックエンド: `src/features/goods-management/backend`
- テスト: `src/features/goods-management/tests`

関連要件:

- REQ-001 〜 REQ-024

`portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当は `public` の既存を読むだけ（複製しない）。本機能固有の業務テーブルはスキーマ `goods_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能で行う。`--color-primary` は、`rules/15-ui-style.md` のパレットに新規追加する8色目（本機能専用の新色）を使う。バックエンドは `uvicorn app.main:app --reload --port 8006`、フロント開発サーバは `5180` を使う。

---

## タスク 1

### タイトル

バックエンドの venv と FastAPI 起動口、DB接続、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-024

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/config.py`, `app/logger.py`, `app/db.py`）

### 実装パス

- `src/features/goods-management/backend/app/main.py`
- `src/features/goods-management/backend/app/config.py`
- `src/features/goods-management/backend/app/logger.py`
- `src/features/goods-management/backend/app/db.py`
- `src/features/goods-management/backend/.env`（ひな型: `specs/templates/backend.env.example`）
- `src/features/goods-management/backend/requirements.txt`

### 内容

venv を backend 配下に作成し、uvicorn で起動できるようにする。`.env` から DB 接続情報、`CORS_ORIGINS`、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` を読む。CORS は具体オリジン、資格情報付き。起動時に `log/` へサイズローテーションするロガーを初期化する。PostgreSQL へ接続する。`portal` を import しない。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `uvicorn app.main:app --reload --port 8006` が起動できる
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

- REQ-001, REQ-024

### 関連設計

- `design.md` / バックエンド設計 / 認証 / 認可
- `design.md` / バックエンド設計 / モジュール構成（`security`, `deps`, `access_service`, `routers/settings.py`）
- `api-design.md` / 共通 / 認証
- `api-design.md` / GET `/settings`

### 実装パス

- `src/features/goods-management/backend/app/security.py`
- `src/features/goods-management/backend/app/deps.py`
- `src/features/goods-management/backend/app/services/access_service.py`
- `src/features/goods-management/backend/app/routers/settings.py`

### 内容

Cookie `session_id` でログイン中ユーザを特定する。未ログイン・期限切れは 401。識別子 `goods-management` の割当が無ければ 403。`DEBUG_USER` でも割当を判定する。セッション ID を本文に出さない。GET `/settings` は認証不要で `login_url`、`menu_url`、`icon_system`、`icon_back` を返す。

運用として、機能マスタに `goods-management`（タイトル「グッズ管理」、遷移先は公開 URL `/portal_goods_management/`）を追加し、利用ユーザへ割り当てる。

### 完了条件

- [ ] 未ログインの操作 API が 401「未ログイン」
- [ ] 割当なしの操作 API が 403「権限がありません」
- [ ] GET `/settings` が未ログインで 200 を返す
- [ ] 本文にセッション ID を含まない
- [ ] 機能マスタに `goods-management` があり、利用ユーザへ割り当てられている

---

## タスク 3

### タイトル

DB スキーマ・テーブル（人物・アーティスト・媒体・商品・商品画像・関連）を作成する

### 見積もり

2時間

### 関連要件

- REQ-003〜REQ-023

### 関連設計

- `db-design.md` / テーブル設計

### 実装パス

- `src/features/goods-management/backend/sql/01_goods_management.sql`

### 内容

スキーマ `goods_management` と、テーブル `persons`・`artists`・`artist_persons`・`media`・`goods`・`goods_images` を `db-design.md` のカラム定義どおりに作成する。`artist_persons` に `(artist_id, person_id)` の一意制約を作る。`goods` に `(user_id, artist_id)`・`(user_id, media_id)`（いずれも `is_deleted = false`）の索引を作る。外部キーはすべて `ON DELETE RESTRICT`。

### 完了条件

- [ ] スキーマ・6テーブルが `db-design.md` のカラム定義どおりに作成される
- [ ] `artist_persons` の一意制約が機能する（同じ組み合わせを二重登録できない）
- [ ] DDL が冪等（`IF NOT EXISTS` 等）である

---

## タスク 4

### タイトル

人物の一覧・登録・名称変更・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-006

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `design.md` / バックエンド設計 / モジュール構成（`repos`, `master_service`, `routers/persons.py`, `errors`）
- `api-design.md` / `/persons`

### 実装パス

- `src/features/goods-management/backend/app/errors.py`
- `src/features/goods-management/backend/app/repos.py`
- `src/features/goods-management/backend/app/services/master_service.py`
- `src/features/goods-management/backend/app/routers/persons.py`

### 内容

`repos.py` に `persons` への挿入・名称更新・論理削除・一覧（`user_id` と `is_deleted = false` で絞り込み）を実装する。`master_service.py` で、名称の空白のみ拒否（トリムして判定・保存）を行う。削除時は、`artist_persons` にその人物を参照する未削除の行が無いことを確認し、あれば 409 で失敗させる。`routers/persons.py` に GET・POST・PATCH・DELETE を実装する。すべて `user_id` で本人の行だけを対象にし、他人の行・存在しない ID は 404 とする。

### 完了条件

- [ ] 一覧・登録・名称変更・削除が本人の行だけを対象にする（他人の ID は 404）
- [ ] 名称の空白のみが 400 になる
- [ ] いずれかのアーティストに紐付く人物の削除が 409 になる
- [ ] 紐付きが無くなれば削除できる

---

## タスク 5

### タイトル

アーティストの一覧・詳細・登録・変更・削除 API を実装する

### 見積もり

4時間

### 関連要件

- REQ-002, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `/artists`

### 実装パス

- `src/features/goods-management/backend/app/repos.py`
- `src/features/goods-management/backend/app/services/master_service.py`
- `src/features/goods-management/backend/app/routers/artists.py`

### 内容

`repos.py` に `artists` への挿入・名称更新・論理削除・一覧・単件取得、`artist_persons` への追加・削除・一覧を実装する。登録・変更時、指定した `person_ids` が本人の削除されていない人物であることを確認する（無ければ 404）。変更時は、現在の関連と `person_ids` の差分を追加・削除する。削除時は、`goods.artist_id` にその未削除の商品が無いことを確認し、あれば 409 で失敗させる（削除できても `artist_persons` は残す）。`routers/artists.py` に GET（一覧・単件）・POST・PATCH・DELETE を実装する。

### 完了条件

- [ ] 一覧・詳細・登録・変更・削除が本人の行だけを対象にする
- [ ] 登録・変更で、存在しない・他人の `person_ids` を指定すると 404 になる
- [ ] 変更で所属人物の追加・削除が反映される
- [ ] いずれかの商品から参照されているアーティストの削除が 409 になる
- [ ] 削除できても `artist_persons` の行は残る

---

## タスク 6

### タイトル

媒体の一覧・登録・名称変更・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-012, REQ-013, REQ-014, REQ-015

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `/media`

### 実装パス

- `src/features/goods-management/backend/app/repos.py`
- `src/features/goods-management/backend/app/services/master_service.py`
- `src/features/goods-management/backend/app/routers/media.py`

### 内容

`repos.py` に `media` への挿入・名称更新・論理削除・一覧を実装する。削除時は、`goods.media_id` にその未削除の商品が無いことを確認し、あれば 409 で失敗させる。`routers/media.py` に GET・POST・PATCH・DELETE を実装する。

### 完了条件

- [ ] 一覧・登録・名称変更・削除が本人の行だけを対象にする
- [ ] 名称の空白のみが 400 になる
- [ ] いずれかの商品から参照されている媒体の削除が 409 になる

---

## タスク 7

### タイトル

人物選択に連動する関連アーティスト・関連媒体取得、商品一覧 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-016, REQ-017

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `/persons/{id}/related-artists`、`/persons/{id}/related-media`、`GET /goods`

### 実装パス

- `src/features/goods-management/backend/app/repos.py`
- `src/features/goods-management/backend/app/services/goods_service.py`
- `src/features/goods-management/backend/app/routers/goods.py`

### 内容

指定した人物に `artist_persons` で紐づく未削除のアーティスト一覧を返す。指定した人物に紐づくアーティストの未削除の商品が属する媒体を、重複を除いて返す。`GET /goods` は `person_id` 必須、`artist_id`・`media_id` は省略可（省略時は「すべて」）とし、条件に合う未削除の商品を、各商品の最初の画像（`display_order` 最小）をサムネイルとして付けて返す。指定した `person_id`・`artist_id`・`media_id` が本人の削除されていない行でなければ 404。

### 完了条件

- [ ] 指定人物に紐づく未削除のアーティスト・媒体だけが返る
- [ ] `artist_id`・`media_id` を省略すると、それぞれ「すべて」として動作する
- [ ] 商品一覧の各行にサムネイル（無ければ `null`）が付く
- [ ] 存在しない・他人の `person_id`/`artist_id`/`media_id` を指定すると 404 になる

---

## タスク 8

### タイトル

商品の詳細取得・登録・更新・削除 API を実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-019, REQ-020, REQ-021, REQ-023

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `GET/POST /goods`、`GET/PATCH/DELETE /goods/{id}`

### 実装パス

- `src/features/goods-management/backend/app/repos.py`
- `src/features/goods-management/backend/app/services/goods_service.py`
- `src/features/goods-management/backend/app/routers/goods.py`

### 内容

`repos.py` に `goods` への挿入・更新・論理削除・単件取得（`goods_images` を `display_order` 昇順で結合）を実装する。登録・更新時、`media_id`・`artist_id` が本人の削除されていない行であることを確認する（無ければ 404）。登録でタイトルの空白のみを拒否する。登録で `release_date` 省略時は登録日を設定し、更新で省略時は既存値を保持する。削除は論理削除とし、`goods_images` の行は削除しない。

### 完了条件

- [ ] 詳細取得・登録・更新・削除が本人の行だけを対象にする
- [ ] タイトルの空白のみが 400 になる
- [ ] 存在しない・他人の `media_id`/`artist_id` を指定すると 404 になる
- [ ] 登録時に `release_date` 省略で登録日が設定される
- [ ] 更新時に `release_date` 省略で既存値が保持される
- [ ] 商品削除後も画像行が残る

---

## タスク 9

### タイトル

商品画像の追加・削除 API を実装する

### 見積もり

2時間

### 関連要件

- REQ-022

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `api-design.md` / `POST /goods/{id}/images`、`DELETE /goods/{id}/images/{image_id}`

### 実装パス

- `src/features/goods-management/backend/app/repos.py`
- `src/features/goods-management/backend/app/services/goods_service.py`
- `src/features/goods-management/backend/app/routers/goods.py`

### 内容

指定した商品が本人の削除されていない商品であることを確認したうえで、画像を追加する（`image_type` は `image/png`/`image/jpeg` のみ許可、`image_data` は Base64 デコードして保存、`display_order` はその商品内の最大値+1）。削除は、画像がその商品に属し、商品が本人のものであることを確認して行う。上限枚数は設けない。

### 完了条件

- [ ] 画像を追加でき、`display_order` が採番順に増える
- [ ] 許可されない `image_type`、不正な Base64 が 400 になる
- [ ] 本人以外の商品・存在しない商品・存在しない画像への操作が 404 になる
- [ ] 個別の画像を削除でき、他の画像は残る

---

## タスク 10

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

- `src/features/goods-management/frontend/`
- `src/features/goods-management/frontend/.env`（ひな型: `specs/templates/frontend.env.example`。変数名は `VITE_API_GOODS_MANAGEMENT_URL`）
- `src/features/goods-management/frontend/src/styles.css`
- `src/features/goods-management/frontend/src/components/Icon.vue`

### 内容

`npm run dev` で起動する（開発ポート 5180）。`rules/15-ui-style.md` の殻とトークンを、他機能と同じ値で置く。`--color-primary` は本機能専用に `rules/15-ui-style.md` のパレットへ新規追加した8色目。ナビは「グッズ管理」のみ。Vite `base` は `/portal_goods_management/`。未ログインは GET `/settings` の `login_url` へ。API は `VITE_API_GOODS_MANAGEMENT_URL` と credentials のみ。他機能のコードは import しない。`Icon.vue` は `icons/` から必要な分（`plus`, `edit`, `delete`, `check`, `close`, `back`, `config`）を複製する。

### 完了条件

- [ ] `npm run dev` で起動できる
- [ ] `VITE_API_GOODS_MANAGEMENT_URL` で API を呼び、ホストを直書きしていない
- [ ] 未ログインでログイン画面 URL へ進む
- [ ] 他機能のコードを import していない

---

## タスク 11

### タイトル

商品一覧画面（人物・アーティスト・媒体の選択、商品一覧、タイトル絞り込み）を実装する

### 見積もり

4時間

### 関連要件

- REQ-004, REQ-008, REQ-013, REQ-016, REQ-017, REQ-018

### 関連設計

- `ui-design.md` / SCR-001（人物・アーティスト・媒体選択、商品一覧、タイトル絞り込み）
- `api-design.md` / `/persons`、`/artists`、`/media`、`/persons/{id}/related-artists`、`/persons/{id}/related-media`、`GET /goods`

### 実装パス

- `src/features/goods-management/frontend/src/api.ts`
- `src/features/goods-management/frontend/src/views/GoodsListView.vue`（または相当のビュー）

### 内容

画面を開いたら人物一覧を取得する。人物選択で関連アーティスト一覧・関連媒体一覧を取得する。アーティスト選択・媒体選択（「すべて」を含む）が変わるたびに商品一覧を再取得する。商品一覧はサムネイル・タイトル・媒体名・リリース日・所持バッジを表示する。取得済みの一覧に対し、タイトル絞り込み入力で画面内フィルタする（大文字小文字を区別しない）。行選択で SCR-002（編集）へ遷移する。新規追加ボタンで SCR-002（新規登録）へ遷移する（選択中のアーティスト・媒体があれば引き継ぐ）。

### 完了条件

- [ ] 人物選択でアーティスト・媒体の選択肢が絞り込まれる
- [ ] アーティスト・媒体（「すべて」を含む）の選択で商品一覧が更新される
- [ ] タイトル絞り込みが画面内で機能する
- [ ] 行選択・新規追加ボタンでそれぞれ SCR-002 へ遷移する
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 12

### タイトル

人物・アーティスト・媒体の管理パネル（追加・改名・削除）を実装する

### 見積もり

4時間

### 関連要件

- REQ-003, REQ-005, REQ-006, REQ-007, REQ-009, REQ-010, REQ-011, REQ-012, REQ-014, REQ-015

### 関連設計

- `ui-design.md` / SCR-001（人物・アーティスト・媒体の管理パネル）
- `api-design.md` / `/persons`、`/artists`、`/media`

### 実装パス

- `src/features/goods-management/frontend/src/api.ts`
- `src/features/goods-management/frontend/src/views/GoodsListView.vue`（または相当のビュー）

### 内容

設定ボタンで管理パネル（モーダル）を開く。種別タブ（人物／アーティスト／媒体）を切り替え、それぞれの一覧・追加・名称変更・削除を行う。アーティストの追加・名称変更フォームには、所属する人物のチェックボックス選択を含める。削除は確認ダイアログのあと実行し、参照制約違反（409）はエラーメッセージで示す。パネルを閉じると、商品一覧の絞り込み状態を保ったまま SCR-001 の表示に戻る。

### 完了条件

- [ ] 人物・アーティスト・媒体それぞれで、追加・名称変更・削除ができる
- [ ] アーティストの追加・変更で、所属人物のチェックボックスが反映される
- [ ] 参照制約違反での削除失敗がエラーメッセージで示される
- [ ] パネルを閉じても商品一覧の絞り込み状態が保たれる
- [ ] ブラウザで一連の操作を確認できる

---

## タスク 13

### タイトル

商品登録・編集画面（画像の追加・削除、削除確認を含む）を実装する

### 見積もり

4時間

### 関連要件

- REQ-019, REQ-020, REQ-021, REQ-022, REQ-023

### 関連設計

- `ui-design.md` / SCR-002
- `api-design.md` / `GET/POST /goods`、`PATCH/DELETE /goods/{id}`、`POST /goods/{id}/images`、`DELETE /goods/{id}/images/{image_id}`

### 実装パス

- `src/features/goods-management/frontend/src/api.ts`
- `src/features/goods-management/frontend/src/views/GoodsFormView.vue`（または相当のビュー）

### 内容

新規登録では空のフォームを表示し、一覧画面で選択中のアーティスト・媒体があれば初期値にする。編集では対象商品の値と画像一覧を取得して表示する。画像追加ボタンでファイルを選び、画像一覧に加える（PNG/JPEG のみ）。各画像に削除ボタンを持つ。保存時、新規登録なら商品登録後に画像を1枚ずつ追加し、編集なら商品更新に加えて、新たに選んだ画像の追加・削除された画像の削除をそれぞれ呼び出す。削除ボタン（編集時のみ表示）は確認ダイアログのあと商品を削除する。保存・削除の成功後は SCR-001 へ戻る。

### 完了条件

- [ ] 新規登録で、媒体・アーティスト・タイトル必須の入力チェックが働く
- [ ] 編集で既存の値・画像一覧が初期表示される
- [ ] 画像の追加・削除が保存時に反映される
- [ ] 削除ボタン（編集時のみ）で商品を削除できる
- [ ] 保存・削除成功後、SCR-001 へ戻る
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
- `ui-design.md` / 画面一覧（パス `/portal_goods_management/`）
- `rules/17-nginx-deploy.md`

### 実装パス

- `src/features/goods-management/frontend/nginx.example.conf`

### 内容

公開 URL `/portal_goods_management/`、ディスクは `features/goods-management/`。スラッシュなしは 301 で付ける。`rewrite` は `last`。`features/goods-management/` は `internal`。API を同一オリジンにする場合の `proxy_pass`（`8006`）例をコメントで置く。

### 完了条件

- [ ] 公開 URL とディスク配置が規則どおりである
- [ ] `rewrite` が `last` である
- [ ] スラッシュなしの location がある

---

## タスク 15

### タイトル

別サーバ版（`sample/goods`）からのデータ移行スクリプトを作成する

### 見積もり

4時間

### 関連要件

- （`requirements.md` の対象外。運用作業として実施）

### 関連設計

- `db-design.md` / テーブル設計（移行先）
- `design.md` / 外部連携

### 実装パス

- `src/features/goods-management/backend/scripts/export_from_goods.py`（新規）
- `src/features/goods-management/backend/scripts/import_to_goods_management.py`（新規）
- `src/features/goods-management/backend/scripts/README.md`（新規。実行手順）

### 内容

**エクスポート**（別サーバ側で実行する）: 接続情報を引数・環境変数で受け取り、`persons`・`artists`・`artist_persons`・`media`（未削除の概念が無いためそのまま全件）・`goods`（`is_deleted = false` の行）・`goods_images` を読み、JSON ファイルへ出力する。旧アプリにはユーザの区別が無いため、アカウント一覧の出力は行わない。

**インポート**（本プロジェクトの DB に対して実行する）: `backend/.env` の接続情報を使う。旧アプリにユーザの区別が無いため、移行先のユーザ名を実行時の引数で1件指定し、全データをそのユーザの所有として取り込む。`persons`→`artists`→`artist_persons`→`media`→`goods`→`goods_images` の順で、旧 ID と新 ID の対応表を保ちながら挿入する（`goods` は新しい `media_id`・`artist_id` を使う。`goods_images` は新しい `goods_id` を使い、`display_order` は移行元の値を引き継ぐ）。旧アプリの `goods.is_owned`・`code_number` 等の値もそのまま引き継ぐ。処理件数（テーブルごとの成功件数）を最後にまとめて表示する。

### 完了条件

- [ ] エクスポートスクリプトが、6テーブル相当のデータ（`goods` は未削除のみ）を JSON へ出力する
- [ ] インポートスクリプトが、指定した1ユーザの所有として全データを取り込む
- [ ] インポートスクリプトが、人物→アーティスト→関連→媒体→商品→画像の順で新 ID の対応関係を正しく張り直す
- [ ] 画像データ（バイナリ）が壊れずに移行される
- [ ] 成功件数がテーブルごとに表示される
- [ ] `scripts/README.md` に実行手順が書かれている

---

## テスト

### 単体テスト

- [ ] `src/features/goods-management/tests/` に配置する
- [ ] 人物・アーティスト・媒体の名称の空白のみ拒否を確認する
- [ ] 人物・アーティスト・媒体の削除で、参照されている場合に失敗（409）することを確認する
- [ ] アーティストの所属人物の追加・削除（差分反映）を確認する
- [ ] 商品登録・更新で、`media_id`/`artist_id` が本人の行でない場合に失敗（404）することを確認する
- [ ] 商品登録で `release_date` 省略時に登録日が設定されることを確認する
- [ ] 商品画像の追加で `display_order` が正しく採番されることを確認する
- [ ] 商品削除後も画像行が残ることを確認する
- [ ] 他ユーザの行が一覧・単件取得・更新・削除の対象にならないことを確認する

### 結合テスト

- [ ] 当該機能の uvicorn に対する API テスト（Cookie、401、403、404、409、settings、人物・アーティスト・媒体・商品・商品画像の CRUD）
- [ ] 操作ログ（入力・判断・失敗理由、セッション ID・画像データの非出力）

### 受け入れテスト

- [ ] `requirements.md` の受け入れ条件（REQ-001〜REQ-024）を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 | 未承認 | 初版 |
| 2026-09-20 | 承認済み | 初版を承認 |
