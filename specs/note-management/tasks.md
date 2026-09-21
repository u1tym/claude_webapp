# note-management タスク分解

> `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後に作成する。
> タスクは 1〜4 時間程度で完了できる粒度にする。

## 概要

対象機能: `note-management`

ソース配置:

- フロントエンド: `src/features/note-management/frontend`
- バックエンド: `src/features/note-management/backend`（移行プログラムは `backend/scripts/`）
- テスト: `src/features/note-management/tests`

関連要件: REQ-001 〜 REQ-018

前提:

- `portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当は `public` の既存を読むだけ（複製しない）。本機能固有の業務テーブルはスキーマ `note_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能で行う（本タスクの対象外）。
- 他機能の Vue・CSS・コンポーネントを import しない。`icons/` の SVG から使う分だけ `frontend/src/components/Icon.vue` に複製する（`rules/15-ui-style.md`）。
- 実装の参考は `sample/note`（フォルダ・ファイル・パーツ、行動予定・画像のマーカー・チェックリスト・過去世代・PDF 出力の動作）。ただしソースをそのまま複製せず、本プロジェクトの方式（psycopg2 の同期接続、Cookie セッション、Vue Router の `createWebHistory`、REST の HTTP ステータス）と、承認済みの設計（利用者ごとのデータ、削除フラグ、削除解除の画面、画像・バイナリの中身の別取得）に合わせる。表のパーツ（およびその計算・移行）は作らない。
- 土台の実装（設定ファイルの読み込み、接続プール、認証、ログ、例外ハンドラ、移行プログラムの骨格、フロントの殻・API クライアント・確認ダイアログ・アイコン）は、`recipe-management` の実装を参考にし、次の点を最初から取り入れる: 設定ファイルの変数名は `DB_SERVER` 形式と `Server` 形式の両方を受け付ける、設定ファイルの場所を環境変数（`NOTE_MANAGEMENT_ENV_FILE`）で切り替えられる、接続に失敗したときに接続プールの枠を返す、DB の失敗の原因（先頭の 1 行）をログに出す。
- ポート: バックエンド 8009、フロントエンド 5183。`--color-primary` は Blue `#6C9BFF`。
- 追加の設定: `PARTS_MAX_REVISIONS`（既定 3）、`PART_MAX_BYTES`（既定 10485760）。
- 各タスクは、実装前に `requirements.md` と 4 つの設計書を確認する。設計にない機能は加えない。
- 実施の順序は、下の「実施順」に従う。

## タスク一覧

### A. バックエンド（基盤・認証）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-001 | バックエンドの土台: `venv`、`requirements.txt`（fastapi、uvicorn、psycopg2-binary、python-dotenv、pytest、httpx）、`.env`（ひな型 `specs/templates/backend.env.example`。CORS は `http://localhost:5183`。`PARTS_MAX_REVISIONS`、`PART_MAX_BYTES` を含む）、`.gitignore`、`app/config.py`（変数名の両形式、`NOTE_MANAGEMENT_ENV_FILE`）、`app/logger.py`、`app/db.py`（接続プール、専用接続、接続失敗時に枠を返す）、`app/main.py`（FastAPI 生成、CORS、例外ハンドラ、ログの初期化） | REQ-001、REQ-014 / design.md 起動・モジュール構成 | `src/features/note-management/backend/` | 2.5h | `uvicorn app.main:app --port 8009` が起動する／`.env` の値を読める（両形式の変数名、追加の設定の既定値）／ログが `log/note-management.log` に出て、サイズでローテーションする／未処理例外は 500 の一文だけを返し、内部情報を含めない |
| T-002 | DDL: `sql/01_note_management.sql`（スキーマ、7 テーブル、制約、部分一意・一意インデックス（ルートと子を分ける）、検査）と `sql/apply.py`。再実行できること（`IF NOT EXISTS` 等） | REQ-003〜REQ-012 / db-design.md 全テーブル | `src/features/note-management/backend/sql/` | 3h | 開発用 DB に適用でき、2 回目の適用も成功する／db-design.md の制約・インデックスが作られている（同名の削除されていない行の重複、並び順の重複、種別の値、ファイル名の必須、倍率の範囲、マーカーの型が DB で拒否される）／削除済み同士の同名は入る |
| T-003 | セッション検証と機能割当判定、共通部品: `app/security.py`、`app/deps.py`（Cookie `session_id`、期限切れ・論理削除は 401、割当なしは 403、`DEBUG_USER`、期限の延長）、`app/services/access_service.py`、`app/repos/public.py`、`app/routers/settings.py`（`GET /settings`）、`app/errors.py`（入力不正・対象なし・競合・大きさ超過）、`app/common.py`（前後の空白を除いた必須の文字列など） | REQ-001 / design.md 認証 / api-design.md 認証・`GET /settings` | `src/features/note-management/backend/app/` | 3h | 未ログイン・期限切れ・論理削除済みユーザは 401、割当なしは 403（本文は api-design.md の文言）／`DEBUG_USER` で Cookie なしでも動く／`GET /settings` が認証不要で 4 つの値を返す／業務エラーが 400・404・409・413 と一文の本文に変換される |

### B. バックエンド（業務 API）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-004 | ツリーとフォルダ API: `GET /items`、`POST /folders`、`PATCH /folders/{id}`、`POST /folders/{id}/move`、`POST /folders/swap-order`、`DELETE /folders/{id}`、`POST /folders/{id}/undelete`（`repos/folder.py`、`services/folder_service.py`、`routers/items.py`、`routers/folders.py`。祖先をたどる削除済みの判定（再帰の問い合わせ）、末尾への採番と、親の行ロック、-1 を経由する入れ替え、自分自身・子孫への移動の拒否、削除解除の並び順の付け直し） | REQ-002〜REQ-004、REQ-006 / design.md ツリーの一覧・フォルダ・ファイル、api-design.md `GET /items`・フォルダ | `src/features/note-management/backend/app/` | 4h | 直下のフォルダ・ファイルが並び順で返り、`is_deleted`・`ancestor_deleted` が正しい（`include_deleted` の切り替え）／作成・名前変更・移動（同名・自分の中・現在地・削除済み）・入れ替え・削除・削除解除が api-design.md のステータス・文言どおり／他ユーザのフォルダは 404／並び順が重ならない |
| T-005 | ファイル API（パーツを除く）: `POST /files`、`PATCH /files/{id}`、`POST /files/{id}/move`、`POST /files/swap-order`、`DELETE /files/{id}`、`POST /files/{id}/undelete`（`repos/file.py`、`services/file_service.py`、`routers/files.py`）。フォルダと同じ規則（ルートの直下には作れない） | REQ-002、REQ-005、REQ-006 / api-design.md ファイル | `src/features/note-management/backend/app/` | 3h | 作成・タイトル変更・移動・入れ替え・削除・削除解除が api-design.md のとおり（同じタイトル、削除済み、現在地、所属フォルダが違う入れ替え）／削除済みのフォルダの中のファイルは `ancestor_deleted` になる／他ユーザは 404 |
| T-006 | パーツの検証部品と、追加・取得・削除・削除解除・入れ替え: `app/action_plan.py`（検証・正規化）、`app/image_markers.py`（マーカー・倍率の検証）、画像の形式（先頭のバイト列）・Base64・大きさの検証、`repos/part.py`、`services/part_service.py`、`routers/parts.py`、`GET /files/{id}`（パーツを、中身を含めずに返す。`include_deleted_parts`）、`POST /files/{id}/parts`、`DELETE /parts/{id}`、`POST /parts/{id}/undelete`、`POST /parts/swap-order`。チェックリストの追加時にチェックリストを同じトランザクションで作る | REQ-002、REQ-006〜REQ-009、REQ-011 / design.md パーツ、api-design.md パーツ・行動予定の本文・Marker | `src/features/note-management/backend/app/` | 4h | 9 種別の追加ができ、種別ごとの検証が api-design.md の文言・ステータスで拒否する（行動予定の正規化、マーカー、倍率、形式、Base64、ファイル名、上限超過は 413）／ファイルの取得で、画像・バイナリの `data` が空、`byte_size`・`checklist_id` が入る／削除済みのファイルへの追加は 409／削除・削除解除・入れ替えが仕様どおり |
| T-007 | パーツの更新と中身の取得: `PATCH /parts/{id}`（省略した項目は現在の値を保つ、種別の変更の規則（組をまたぐときの本文の必須、チェックリストの禁止）、画像以外への変更でタイトル等を初期化、過去世代の保管と古い世代の削除（同じトランザクション）、画像の差し替えでマーカーを空にする）、`GET /parts/{id}/content`、`GET /part-revisions/{id}/content`（`Content-Type`、`Content-Disposition`、日本語のファイル名） | REQ-008〜REQ-011 / design.md パーツ（編集・差し替え・取得）、api-design.md `PATCH /parts/{part_id}`・content | `src/features/note-management/backend/app/` | 4h | api-design.md のとおりに更新できる／中身・種別・ファイル名の変更で世代が増え、タイトル・倍率・マーカーだけの変更では増えない／`PARTS_MAX_REVISIONS` を超えると古い世代が消える／中身の取得が、種別に応じたヘッダで、元のバイト列を返す（削除済みでも取得可、他ユーザは 404） |
| T-008 | チェックリスト API（全エンドポイント）: `repos/checklist.py`、`services/checklist_service.py`、`routers/checklists.py`。変更後の最新の状態を返す、無名カテゴリの自動作成、カテゴリ削除で項目も論理削除、カテゴリの並び替え（無名を除く）、項目の移動（位置の付け直し）、同名のカテゴリの 409（部分一意） | REQ-002、REQ-012 / design.md チェックリスト、api-design.md チェックリスト | `src/features/note-management/backend/app/` | 4h | 取得・タイトル・カテゴリの追加/名前変更/削除/並び替え・項目の追加/更新/削除/移動が api-design.md のとおり／無名カテゴリは先頭に出て、名前は変えられない／削除済みのものが返らない／削除済みのファイル・パーツのチェックリストの変更は 409／他ユーザは 404 |
| T-009 | ログの組み込み: 各サービス・ルータに、入力・判断結果・失敗理由の出力を入れる。パーツの本文・画像・ファイルの中身、パスワード・セッション ID・Cookie を出さない | REQ-014 / design.md ログ | `src/features/note-management/backend/app/` | 1.5h | フォルダ・ファイル・パーツ・チェックリストの作成・変更・移動・削除・削除解除・並び替え、一覧・ファイルの取得の試行と成否が `log/` に出る／失敗の内部理由が出る／画像・本文・Cookie の値が出ない（識別子・種別・大きさだけ） |

### C. バックエンドのテスト

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-010 | テスト基盤と、認証・設定・DDL のテスト（`conftest.py`: テスト用ユーザ・セッション・機能割当の作成と後始末（親子のあるデータを依存の順に消す）、`test_auth.py`、`test_config.py`（変数名の両形式、DB の失敗の原因のログ、接続失敗が続いても枠が尽きない）、`test_ddl.py`（制約・インデックスの確認）） | REQ-001、REQ-014 / api-design.md 認証、db-design.md | `src/features/note-management/tests/` | 3h | 未ログイン・期限切れ・論理削除ユーザ・割当なし・`DEBUG_USER` の各挙動を確認できる／DDL の制約（部分一意、並び順の一意、検査）が DB で効くことを直接確認する／テスト用のデータがテスト後に残らない |
| T-011 | ツリーとフォルダのテスト（`test_folders.py`） | REQ-002〜REQ-004、REQ-006 / api-design.md フォルダ | `src/features/note-management/tests/` | 3h | 一覧（並び順、削除済みの除外と `include_deleted`、`ancestor_deleted`）、作成（末尾、同名、削除済みと同名は可）、名前変更、移動（同名、自分・子孫、現在地、削除済み）、入れ替え、削除（子孫の行が変わらない）、削除解除（同名の 409、並び順の付け直し）、他ユーザの 404 を、DB の値と照合して確認する |
| T-012 | ファイルのテスト（`test_files.py`） | REQ-002、REQ-005、REQ-006 / api-design.md ファイル | `src/features/note-management/tests/` | 2.5h | 作成（ルート直下は不可）、タイトル重複、移動、入れ替え、削除、削除解除、祖先の削除の反映、他ユーザの 404 を確認する |
| T-013 | パーツのテスト（`test_parts.py`、`test_part_revisions.py`） | REQ-002、REQ-006〜REQ-011 / api-design.md パーツ | `src/features/note-management/tests/` | 4h | 9 種別の追加・取得、行動予定の正規化と検証、マーカー・倍率の境界（100 個、0〜1、0.25〜4.0）、画像の形式の不一致、Base64 の不正、上限（413。小さい上限で確認）、更新（省略の維持、種別変更の規則、チェックリストの禁止、初期化）、過去世代（増える・増えない・上限で削除・世代番号）、中身の取得（ヘッダ、バイト列の一致、日本語のファイル名）、削除・削除解除・入れ替え、削除済みのファイルへの操作の 409、他ユーザの 404 を確認する |
| T-014 | チェックリストのテスト（`test_checklists.py`） | REQ-002、REQ-012 / api-design.md チェックリスト | `src/features/note-management/tests/` | 3h | 全操作の応答の状態、無名カテゴリの自動作成と先頭表示、同名の 409、カテゴリ削除で項目も消える、並び替え・移動の位置、削除済みが返らない、削除済みのファイルへの 409、他ユーザの 404 を確認する |

### D. 移行プログラム

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-015 | 移行の骨格: `scripts/migrate_from_note.py`（引数と環境変数、移行元の読み取り専用接続、移行先の接続（`backend/.env`）、接続失敗の表示（どちらの DB か。パスワードを出さない）、`--username`（必須）による移行元のアカウントと移行先の利用者の解決と、存在しない・論理削除済みのときの終了、`--dry-run`、進捗・結果報告の枠、終了コード（正常 0、失敗あり 1、接続失敗・利用者なし 2）） | REQ-015、REQ-016、REQ-018 / design.md 移行プログラム | `src/features/note-management/backend/scripts/` | 3h | 接続情報を引数・環境変数で指定できる／どちらかに接続できないとき、どちらかが表示され、パスワードが出ない／利用者が無いとき何も書かずに終了する／移行元へ書き込めない（読み取り専用） |
| T-016 | 移行（フォルダ・ファイル・パーツ・過去世代・チェックリスト）: フォルダを上位から順に移行（削除済みも。移行済みのスキップ（同じ親・同名・同じ削除状態。同名の削除済みが複数のときは個数で判定）、並び順は移行元の値）、ファイル 1 件 1 トランザクション（ファイル、パーツ（表は対象外として記録、チェックリストの参照の付け替え）、過去世代、チェックリストの削除されていないカテゴリ・項目（削除済みは件数を記録）、想定外の種別は失敗）、移行後の照合（パーツ・過去世代・カテゴリ・項目の件数、画像・バイナリの大きさと MD5）、`--dry-run` の集計 | REQ-016、REQ-017 / design.md 移行プログラム・db-design.md 要件トレーサビリティ | `src/features/note-management/backend/scripts/` | 4h | 移行元のフォルダ階層・名前・タイトル・並び順・削除状態・種別・本文・マーカー・倍率・世代・チェックリストが移行先へ入る／表のパーツが移行されず、一覧に出る／失敗したファイルが移行先に残らず、ほかへ進む／再実行で二重に作られず、続きから移行できる／ドライランで書き込まない |
| T-017 | 移行のテスト: 移行元 DB（サンプルの構造（表を含む）を再現する DDL を `tests/fixtures/` に置き、テスト用の別 DB に作る）と、移行先（開発用 DB）の両方を使うテスト（`test_migration.py`） | REQ-015〜REQ-018 / design.md 移行プログラム | `src/features/note-management/tests/` | 4h | 利用者の指定（移行元・移行先の不在、論理削除、未指定）、階層・削除状態・同名の削除済みの複数、表の除外、チェックリストの参照の付け替えと削除済みの除外、過去世代、画像・バイナリの一致、照合の失敗時のロールバックと続行、再実行の冪等、ドライラン（書き込みなし）、移行元へ書き込まないことを確認する |
| T-018 | 移行の手順書 `scripts/README.md`（前提、事前準備（移行先の DDL 適用・利用者の存在）、接続情報の指定、移行先の切り替え、ドライラン、実行、再実行、結果の読み方、後片付け） | REQ-018 / design.md 移行プログラム | `src/features/note-management/backend/scripts/README.md` | 1h | README の手順どおりに、ドライランと実行ができる／表・チェックリストの削除済みが移行されないことと、終了コードが書かれている |

### E. フロントエンド

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-019 | フロントの土台: `package.json`（vue、vue-router、vite、typescript、vue-tsc、markdown-it、katex）、`vite.config.ts`（`base: "/portal_note_management/"`、port 5183）、`tsconfig`、`.env`（`VITE_API_NOTE_MANAGEMENT_URL`）、`.gitignore`、`index.html`、`main.ts`、`router.ts`（`createWebHistory(import.meta.env.BASE_URL)`、2 画面のルート）、`styles.css`（`rules/15-ui-style.md` のトークン、`--color-primary` は `#6C9BFF`、印刷用のスタイルの枠）、`components/Icon.vue`（`back` `check` `close` `delete` `edit` を含む） | REQ-001 / design.md フロントエンド設計、ui-design.md 共通の構成 | `src/features/note-management/frontend/` | 2h | `npm run dev` が起動する／`npm run build`（型検査を含む）が通る／ルートが 2 画面分あり、画面は仮の見出しでよい／API 基点をコードに直書きしていない |
| T-020 | 殻と共通部品: `App.vue`（ヘッダ・ナビ「ノート」、PC は左ナビ / 768px 未満は下ナビ）、未ログイン時のログイン画面 URL への誘導、権限なしの表示、`api/client.ts`（Cookie 送信、認証エラーの共通処理）、確認ダイアログ、名前の入力ダイアログ（背景で閉じない。ダイアログ内のエラー表示） | REQ-001 / ui-design.md 共通の構成・共通の表示 | `src/features/note-management/frontend/src/` | 3h | ナビが PC・スマートフォンで規定の配置になり、SCR-002 でも「ノート」が現在地になる／ヘッダの戻るがメニュー画面 URL へ進む／401 でログイン画面 URL へ進み、403 でその旨を表示する／ダイアログが背景の押下で閉じない／ページ全体がスクロールしない |
| T-021 | API モジュール・型・補助関数: api-design.md の全エンドポイントの呼び出しと応答の型（`any` を使わない）、`utils/`（ファイルの読み込みと Base64 化・大きさの検証、バイナリのダウンロード、行動予定の型・検証・組み立て、マーカー・倍率の計算（置く位置、ピンの位置、最小の未使用の番号、倍率の範囲）、Markdown の描画（生の HTML を許可しない、リンクは http / https のみ）、TeX の描画（失敗時はソース）、大きさの表示） | REQ-007〜REQ-012 / api-design.md 全エンドポイント | `src/features/note-management/frontend/src/api/`、`src/utils/` | 4h | api-design.md の全エンドポイントに対応する関数がある／型検査が通る／エラー本文の文言で 409 などを判別できる／行動予定の検証が api-design.md の規則と一致する／Markdown に `<script>` や `javascript:` のリンクが出力されない |
| T-022 | ノート一覧 SCR-001 の表示: ルートフォルダの取得、フォルダの開閉と直下の取得（フォルダ・ファイルを並び順に字下げ）、「削除済みを表示」（バッジ、上位が削除済み）、ファイルの行から SCR-002 へ、戻ったときの展開状態・削除済みの表示状態の保持、読込中・空・エラーの表示 | REQ-003、REQ-006 / ui-design.md SCR-001 | `src/features/note-management/frontend/src/views/`、`components/` | 3h | ツリーが並び順に出る／開閉のたびに直下が取得される／削除済みの切り替えで表示が変わり、バッジが出る／SCR-002 から戻ると展開状態が保たれる／読込中・空・エラーの表示がある |
| T-023 | SCR-001 のフォルダ・ファイルの操作: 「フォルダ追加」「ファイル追加」、編集モード（名前変更、移動（移動先の選択ダイアログ。自分・子孫は無効、ルートの可否）、上へ・下へ、削除の確認）、削除解除、同名などのエラー表示、成功メッセージ | REQ-004〜REQ-006 / ui-design.md SCR-001 | `src/features/note-management/frontend/src/views/`、`components/` | 4h | 各操作が成功し、ツリーが更新される／削除済みの行に編集操作が出ず、自身が削除済みの行にだけ「削除解除」が出る／同名・自分の中への移動・削除済みのエラーが、ダイアログまたは領域の先頭に出る／先頭・末尾で「上へ」「下へ」が無効になる |
| T-024 | SCR-001 の PDF 出力モードと印刷用のレイアウト: ファイルの選択（チェックボックス。削除済みには出さない）、出力パネル（順の入れ替え、除外、改ページの選択、「PDF に出力」）、複数ファイルの印刷用のレイアウト（フォルダ名・タイトル・削除されていないパーツ。画像の読み込みの完了待ち）、印刷用のスタイル（殻・操作の非表示、ファイルごとの改ページ）、`window.print()` | REQ-013 / ui-design.md PDF 出力モード・PDF 出力（印刷用のレイアウト） | `src/features/note-management/frontend/src/views/`、`components/`、`styles.css` | 3h | 選んだ順に連結され、順の入れ替え・除外ができる／改ページの有無が印刷のレイアウトに反映される（印刷用のメディアで確認）／印刷の内容に、操作のボタン・殻が含まれない／取得の失敗が出力パネルの先頭に出る |
| T-025 | ファイル SCR-002 の表示と共通の操作: ファイルの取得、見出し・所属フォルダ、削除済みの案内、「削除済みのパーツを表示」、パーツのカード（テキスト・Markdown・TeX・URL の表示）、「上へ」「下へ」、パーツのダイアログ（表示、削除、削除解除、閉じる）、読込中・空・エラー・「ファイルが見つかりません」 | REQ-006〜REQ-008 / ui-design.md SCR-002 | `src/features/note-management/frontend/src/views/`、`components/` | 4h | パーツが並び順に、種別に応じた形で出る（Markdown の整形、TeX の組版、URL のリンク）／カードからダイアログが開く／削除・削除解除・並び替えが動く／削除済みのファイルでは編集系の操作が出ない／存在しないファイルで「ファイルが見つかりません」が出て、一覧へ戻れる |
| T-026 | パーツの追加・編集（テキスト・Markdown・TeX・URL）: 「パーツを追加」ダイアログ（種別の選択、入力欄、プレビュー）、編集（種別の選び直し、組をまたぐときの入力欄の切り替え、チェックリストの種別の固定）、保存前の検証とエラー表示、保存後の再取得 | REQ-008 / ui-design.md SCR-002（種別ごとの入力） | `src/features/note-management/frontend/src/components/` | 4h | 本文が空でも保存できる／Markdown・TeX のプレビューが出る／種別を変えると入力欄が切り替わる／チェックリストの種別は選び直せない／失敗がダイアログの先頭に出て、入力が残る |
| T-027 | 行動予定: 表示（地点・時刻・経由メモ・補足の改行）、入力（地点 1、地点 2 以降の単一時刻・到着出発の切り替え、経由メモ・補足、地点の追加・削除）、保存前の検証（1 件以上の内容、末尾の空地点・空白の扱い） | REQ-011 / ui-design.md SCR-002（行動予定） | `src/features/note-management/frontend/src/components/` | 3h | 追加・編集・表示ができる／内容が空だと、理由が出て保存されない／末尾の空の地点が保存されず、経由メモの数が合う／補足の改行が表示に保たれる |
| T-028 | 画像・バイナリ: ファイルの選択と大きさの検証（10 MB）、画像の表示（倍率どおり）、タイトル・倍率の入力、マーカー（配置、番号の自動付与、ドラッグでの移動、選択、凡例の文字と削除、100 個の上限）、バイナリの表示、ダウンロード、過去の世代の一覧とダウンロード、差し替え | REQ-007、REQ-009、REQ-010 / ui-design.md SCR-002（画像のマーカーの操作、パーツのダイアログ） | `src/features/note-management/frontend/src/components/` | 4h | JPEG・PNG・バイナリを登録でき、画像が倍率どおりに表示される／10 MB 超は選んだ時点で断られる／マーカーの配置・移動・文字・削除ができ、保存後に再現される／過去の世代が一覧され、ダウンロードできる／画像を差し替えるとマーカーが空になる |
| T-029 | チェックリスト: 表示（この画面ではチェックを操作できない）、編集（ダイアログ内。タイトル、カテゴリの追加・名前変更・削除（確認）・上下、項目の追加・タイトル・チェック・削除・上下・カテゴリの選択による移動、ドラッグでの並び替えとカテゴリ間の移動、エラー表示。操作のたびに保存し、応答の状態で更新） | REQ-007、REQ-012 / ui-design.md SCR-002（チェックリストの編集） | `src/features/note-management/frontend/src/components/` | 4h | 全操作が保存され、表示が最新の状態になる／無名カテゴリが先頭で見出しなしになる／ドラッグと、ボタン・選択欄の両方で並び替え・移動できる／同名のカテゴリのエラーがダイアログの先頭に出る |
| T-030 | ファイル 1 件の PDF 出力: SCR-002 の「PDF 出力」、印刷用のレイアウトにパーツの全種別（画像・行動予定・チェックリスト・Markdown・TeX・URL・テキスト、バイナリはファイル名と大きさ）を、画面と同じ内容で出す | REQ-013 / ui-design.md PDF 出力（印刷用のレイアウト） | `src/features/note-management/frontend/src/components/`、`views/` | 2.5h | 印刷用のメディアで、フォルダ名・タイトル・パーツが並び、操作の部品が出ない／画像・TeX が表示される／削除されていないパーツだけが出る |

### F. 仕上げ

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-031 | 画面幅の確認と調整: 全画面・ダイアログを Wide（1024px 以上）と Compact（400px 前後）で確認し、はみ出し・長い文字列・0 件・多数のフォルダ・パーツ・大きな画像を直す | REQ-003〜REQ-013 / ui-design.md レイアウトの違い、`rules/31-web-app-responsive-layout-spec.md` | `src/features/note-management/frontend/src/` | 2h | 全画面・ダイアログで横スクロールが出ない／ページ全体がスクロールしない／タップ領域が 44px 以上／フォーカスの表示がある／Compact で行の操作が折り返される |
| T-032 | デプロイ資料: `frontend/nginx.example.conf`（公開 URL `/portal_note_management/`、API を同一オリジンにする場合の proxy（`client_max_body_size` 16m 以上、画像・バイナリの応答のバッファリング無効））、`src/features/note-management/Readme.txt`（初回の準備・起動・DDL 適用・テスト） | REQ-001 / design.md デプロイ上の考慮、`rules/17-nginx-deploy.md` | `src/features/note-management/frontend/nginx.example.conf`、`src/features/note-management/Readme.txt` | 1.5h | nginx の設定例が `rules/17-nginx-deploy.md` に沿っている（`rewrite` は `last`、`try_files` と `break` を同じ location に置かない）／Readme の手順どおりに、バックエンドとフロントエンドを起動できる |
| T-033 | 結合確認: ブラウザ（自動操作）で、フォルダ・ファイルの作成・名前変更・移動・並び替え・削除・削除解除、各種別のパーツの追加・編集・削除・削除解除、画像のマーカー・過去世代、チェックリスト、PDF 出力の準備、Compact 幅の表示を通しで確認。実際の移行元 DB に対して、ドライランを実行し、結果を報告する | REQ-001〜REQ-018 / requirements.md 全受け入れ条件 | `src/features/note-management/` | 3h | requirements.md の受け入れ条件を一通り確認し、未達があれば一覧にして報告する／移行のドライランが、想定の件数（表のパーツ 5 件・チェックリストの削除済みなどの対象外を含む）で通る |

## 実施順

1. 基盤: T-001 → T-002 → T-003
2. バックエンド API: T-004 → T-005 → T-006 → T-007、T-008（T-005 の後。独立）→ T-009
3. テスト: T-010（T-003 の後）、T-011（T-004 の後）、T-012（T-005 の後）、T-013（T-006・T-007 の後）、T-014（T-008 の後）。各 API の実装と並行して進めてよい。
4. 移行: T-015（T-002 の後。バックエンド API とは独立）→ T-016 → T-017 → T-018
5. フロントエンド: T-019 → T-020、T-021 → T-022 → T-023 → T-024、T-025 → T-026 → T-027、T-028、T-029（独立）→ T-030
6. 仕上げ: T-031、T-032 → T-033

合計の見積もり: 約 103 時間（バックエンド基盤 8.5h、業務 API 20.5h、テスト 15.5h、移行 12h、フロントエンド 47h のうち土台・共通 13h ほか、仕上げ 6.5h を含む）。

## 要件とタスクの対応

| 要件 | タスク |
|------|--------|
| REQ-001 | T-001、T-003、T-010、T-019、T-020 |
| REQ-002 | T-004〜T-008、T-011〜T-014 |
| REQ-003 | T-004、T-011、T-022 |
| REQ-004 | T-004、T-011、T-023 |
| REQ-005 | T-005、T-012、T-023 |
| REQ-006 | T-002、T-004〜T-006、T-011〜T-013、T-022、T-023、T-025 |
| REQ-007 | T-006、T-007、T-013、T-021、T-025、T-028、T-029 |
| REQ-008 | T-006、T-007、T-013、T-025、T-026 |
| REQ-009 | T-006、T-007、T-013、T-021、T-028 |
| REQ-010 | T-007、T-013、T-028 |
| REQ-011 | T-006、T-013、T-021、T-027 |
| REQ-012 | T-008、T-014、T-029 |
| REQ-013 | T-024、T-030 |
| REQ-014 | T-001、T-009、T-010 |
| REQ-015 | T-015、T-017 |
| REQ-016 | T-015〜T-017 |
| REQ-017 | T-016、T-017 |
| REQ-018 | T-015〜T-018 |
| 横断（画面幅・デプロイ・結合確認） | T-031、T-032、T-033 |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-21 23:01 | 未承認 | 初版 |
| 2026-09-21 23:02 | 承認済み | 初版を承認 |
