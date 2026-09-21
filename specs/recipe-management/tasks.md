# recipe-management タスク分解

> `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後に作成する。
> タスクは 1〜4 時間程度で完了できる粒度にする。

## 概要

対象機能: `recipe-management`

ソース配置:

- フロントエンド: `src/features/recipe-management/frontend`
- バックエンド: `src/features/recipe-management/backend`（移行プログラムは `backend/scripts/`）
- テスト: `src/features/recipe-management/tests`

関連要件: REQ-001 〜 REQ-014

前提:

- `portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当は `public` の既存を読むだけ（複製しない）。本機能固有の業務テーブルはスキーマ `recipe_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能で行う（本タスクの対象外）。
- 他機能の Vue・CSS・コンポーネントを import しない。`icons/` の SVG から使う分だけ `frontend/src/components/Icon.vue` に複製する（`rules/15-ui-style.md`）。
- 実装の参考は `sample/recipe`（レシピの登録・取得・一覧、材料・分量名称の追加、入力フォームの動作）。ただしソースをそのまま複製せず、本プロジェクトの方式（psycopg2 の同期接続、Cookie セッション、Vue Router の `createWebHistory`）と、承認済みの設計（利用者ごとのデータ、削除の追加、更新は同じ識別子で上書き）に合わせて書き直す。
- 土台の実装（設定ファイルの読み込み、接続プール、認証、ログ、例外ハンドラ、移行プログラムの骨格）は、`movie-management` の実装を参考にし、次の点を最初から取り入れる: 設定ファイルの変数名は `DB_SERVER` 形式と `Server` 形式の両方を受け付ける、設定ファイルの場所を環境変数（`RECIPE_MANAGEMENT_ENV_FILE`）で切り替えられる、DB に接続できないときに接続の枠を返す、DB の失敗の原因（先頭の 1 行）をログに残す。
- ポート: バックエンド 8008、フロントエンド 5182。`--color-primary` は Orange `#FFA36C`。
- 各タスクは、実装前に `requirements.md` と 4 つの設計書を確認する。設計にない機能は加えない。
- 実施の順序は、下の「実施順」に従う。

## タスク一覧

### A. バックエンド（基盤・認証）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-001 | バックエンドの土台: `venv`、`requirements.txt`（fastapi、uvicorn、psycopg2-binary、python-dotenv、pytest、httpx）、`.env`（ひな型 `specs/templates/backend.env.example`）、`.gitignore`、`app/config.py`（変数名の両形式、`RECIPE_MANAGEMENT_ENV_FILE`）、`app/logger.py`、`app/db.py`（接続プール、専用接続、接続失敗時に枠を返す）、`app/main.py`（CORS、ルータ登録の枠、例外ハンドラ、DB の失敗の原因のログ） | REQ-010 / design.md 起動・モジュール構成 | `src/features/recipe-management/backend/` | 2h | `backend` で venv を有効化して `uvicorn app.main:app --reload --port 8008` が起動する／`.env` の接続情報で DB に接続できる／`Server=` 形式の `.env` も読める／`LOG_MAX_BYTES` `LOG_BACKUP_COUNT` を `.env` から読み、`log/` にサイズローテーションで出力する／秘密情報をソースに直書きしていない |
| T-002 | DDL: `sql/01_recipe_management.sql`（スキーマ、5 テーブル、制約、索引、共通の材料 12 件・分量名称 4 件の初期データ）と `sql/apply.py`。再実行できること（`IF NOT EXISTS`、`ON CONFLICT DO NOTHING`） | REQ-008、REQ-009 / db-design.md 全テーブル | `src/features/recipe-management/backend/sql/` | 2h | 開発用 DB に適用でき、2 回目の適用でもエラーにならない／db-design.md の全テーブル・制約・索引が存在する／共通の材料 12 件・分量名称 4 件が入る／共通の同名重複、同一利用者の未削除レシピの同名重複、接頭語・接尾語が両方空の分量名称、`step_no` の重複がそれぞれ DB で拒否され、削除済みレシピと同名の登録は許される |
| T-003 | セッション検証と機能割当判定、共通部品: `app/security.py`、`app/deps.py`（Cookie `session_id`、期限切れ・論理削除は 401、割当なしは 403、`DEBUG_USER`、期限の延長）、`app/services/access_service.py`、`app/repos/public.py`、`app/routers/settings.py`（`GET /settings`）、`app/errors.py`（入力不正・対象なし・重複）、`app/common.py`（前後の空白を除いた必須の文字列の型） | REQ-001、REQ-010 / design.md 認証 / 認可・共通、api-design.md 認証・共通エラー・`GET /settings` | `src/features/recipe-management/backend/app/` | 3h | 未ログイン・期限切れは 401、割当なし・論理削除済みの機能は 403／`DEBUG_USER` 指定時のみ Cookie なしで通り、その場合も割当を判定する／`GET /settings` が認証なしで返る／共通エラーが api-design.md の本文どおりに返る／セッション ID をログ・応答に出さない |

### B. バックエンド（業務 API）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-004 | 材料 API: `GET` `POST /ingredients`（`repos/ingredient.py`、`services/ingredient_service.py`、`routers/ingredients.py`） | REQ-008、REQ-002 / api-design.md 材料 | `src/features/recipe-management/backend/app/` | 2h | 共通と本人の独自だけが、かなの昇順（同じなら識別子の昇順）で返り、`is_system` で区別できる／他ユーザの独自は返らない／独自を追加でき、同じ名前が共通・本人の独自にあるときは 409（他ユーザの独自と同じ名前は可）／名前・かなが空・空白のみは 400／追加した値は前後の空白が除かれる |
| T-005 | 分量名称 API: `GET` `POST /measurements`（`repos/measurement.py`、`services/measurement_service.py`、`routers/measurements.py`） | REQ-009、REQ-002 / api-design.md 分量名称 | `src/features/recipe-management/backend/app/` | 2h | 共通と本人の独自だけが、接頭語・接尾語・識別子の昇順で返り、`is_system` で区別できる／他ユーザの独自は返らない／独自を追加でき、同じ接頭語と接尾語の組が共通・本人の独自にあるときは 409／接頭語・接尾語が両方空（空白のみを含む）は 400／`ness_amount` の必須・型を検証する |
| T-006 | レシピの登録・一覧・詳細: `POST /recipes`、`GET /recipes`、`GET /recipes/{recipe_id}`（`repos/recipe.py`、`services/recipe_service.py`、`routers/recipes.py`。入力の検証、材料・分量名称の利用可否の確認、数量の規則、1 トランザクションでの登録、同名の 409、詳細の組み立て） | REQ-003、REQ-004、REQ-005 / design.md レシピの一覧・詳細・登録・編集、api-design.md レシピ | `src/features/recipe-management/backend/app/` | 4h | 登録で、レシピ・工程（1 から連番）・材料の行（1 から連番）が作られ、詳細が並び順どおりに返る／数量ありで数量が空は 400、数量なしの数量は空で保存される／他ユーザの独自・存在しない材料・分量名称は 404 で、何も登録されない／本人の未削除レシピと同名は 409、削除済みと同名は登録できる／一覧が、かなの昇順・同じなら識別子の昇順で、未削除の本人のものだけ／他ユーザのレシピは 404 |
| T-007 | レシピの更新・削除: `PUT /recipes/{recipe_id}`、`DELETE /recipes/{recipe_id}`（行ロック、工程・材料の作り直し、自身を除いた同名の 409、論理削除） | REQ-006、REQ-007 / design.md レシピの登録・編集・削除、api-design.md `PUT`・`DELETE` | `src/features/recipe-management/backend/app/` | 3h | 更新で、識別子・作成日時が変わらず、内容が入力で置き換わり、更新日時が進む／名前を変えても、別のレシピにならず、削除済みのレシピが増えない／自身以外の未削除レシピと同名は 409 で、元の内容が残る（途中失敗でもロールバックされる）／削除は論理削除で、以降の一覧・詳細・更新・削除の対象にならず、同名で再登録できる／存在しない・削除済み・他ユーザは 404 |
| T-008 | ログの組み込み: 各サービスに、入力・判断結果・失敗理由の出力を入れる。工程の説明の本文、パスワード・セッション ID・Cookie を出さない | REQ-010 / design.md ログ | `src/features/recipe-management/backend/app/` | 1.5h | 登録・変更・削除・一覧・詳細・材料と分量名称の追加の試行と成否が `log/` に出る／失敗時に内部理由が出る／工程の説明の本文が出ない／セッション ID が出ない |

### C. バックエンドのテスト

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-009 | テスト基盤と、認証・設定・DDL のテスト（`conftest.py`: テスト用ユーザ・セッション・機能割当の作成と後始末、`test_auth.py`、`test_config.py`（変数名の両形式、DB の失敗の原因のログ、接続失敗が続いても枠が尽きない）、`test_ddl.py`） | REQ-001、REQ-010 / api-design.md 認証、db-design.md | `src/features/recipe-management/tests/` | 2h | 401 / 403 / 論理削除済みユーザ、セッションの延長、`DEBUG_USER`、設定の読み込み、DDL の制約と再適用を検証するテストが通る／テストが本番データに影響しない |
| T-010 | 材料・分量名称のテスト（`test_ingredients.py`、`test_measurements.py`） | REQ-002、REQ-008、REQ-009 / api-design.md 材料・分量名称 | `src/features/recipe-management/tests/` | 2h | 共通の初期データ、独自の追加、他ユーザに見えない、同名・同じ組の 409（共通・本人の独自との重複）、検証（空・空白・両方空）、並び順を検証するテストが通る |
| T-011 | レシピのテスト（`test_recipes.py`） | REQ-002〜007 / api-design.md レシピ | `src/features/recipe-management/tests/` | 3h | 登録・詳細・一覧（並び、未削除のみ）・更新（識別子の維持、作り直し、同名、ロールバック）・削除（論理削除、再登録）、数量の規則、他ユーザの材料・分量名称の指定、他ユーザのレシピの操作（404）、工程・材料の並びを検証するテストが通る |

### D. 移行プログラム

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-012 | 移行の骨格: `scripts/migrate_from_recipe.py`（引数と環境変数、移行元の読み取り専用接続、移行先の接続（`backend/.env`）、接続失敗の表示（どちらの DB か。パスワードを出さない）、`--username`（必須）による利用者の解決と、存在しない・論理削除済みのときの終了、`--dry-run`、進捗・結果報告の共通処理、終了コード） | REQ-011、REQ-012、REQ-014 / design.md 移行プログラム | `src/features/recipe-management/backend/scripts/` | 3h | 移行元・移行先のどちらの接続失敗かがわかる／指定した利用者が無い・論理削除済みのときは何も書き込まずに終了する／`--dry-run` で書き込みが起きない／失敗があれば終了コードが 0 以外／移行元へ書き込む SQL が存在しない |
| T-013 | 移行（材料・分量名称・レシピ）: 材料・分量名称の対応付け（共通 → 指定した利用者の独自 → 追加。数量の要否の違いの一覧表示）、レシピ 1 件 1 トランザクションの移行（削除済みは対象外、移行済み（同名）のスキップ、工程番号・材料の行の並び・数量・説明の引き継ぎ、移行元に存在しない材料・分量名称の行の取り除きと一覧表示、工程数・材料の行数の照合、失敗時のロールバック） | REQ-012、REQ-013 / design.md 処理の流れ・レシピ 1 件の移行 | `src/features/recipe-management/backend/scripts/` | 4h | 移行元と移行先で、レシピ・工程・材料の行の内容と並びが一致する／識別子は移行先で採番される／共通と同じ材料・分量名称は共通に対応付けられ、それ以外は指定した利用者の独自として追加される／削除済みレシピは対象外として一覧される／照合が不一致または途中失敗のレシピは移行先に残らず、次へ進む／再実行で移行済みがスキップされ、二重に増えない |
| T-014 | 移行のテスト: 移行元 DB（サンプルの構造を再現する DDL を `tests/fixtures/` に置き、テスト用の別 DB に作る）と、移行先（開発用 DB）の両方を使うテスト（`test_migration.py`） | REQ-011〜014 / design.md 移行プログラム | `src/features/recipe-management/tests/` | 3h | 利用者の指定（存在・論理削除・未指定）、共通・独自・追加のマスタの対応付け、数量の要否の違いの表示、削除済みの対象外、値と並びの一致、照合不一致時のロールバック、再実行のスキップ、取り除いた行の一覧、`--dry-run` で書き込みが起きないこと、接続失敗と終了コードを検証するテストが通る／テスト後にテスト用 DB と移行先のテストデータが後始末される |
| T-015 | 移行の手順書 `scripts/README.md`（前提、事前準備（移行先の DDL 適用・利用者の存在）、接続情報の指定、移行先の切り替え、ドライラン、実行、再実行、結果の読み方、後片付け） | REQ-014 / design.md 移行プログラム | `src/features/recipe-management/backend/scripts/README.md` | 1h | README の手順どおりに、ドライランと本実行ができる／対象・対象外・スキップの意味と、再実行の挙動が書かれている |

### E. フロントエンド

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-016 | フロントの土台: `package.json`（vue、vue-router、vite、typescript、vue-tsc）、`vite.config.ts`（`base: "/portal_recipe_management/"`、port 5182）、`tsconfig`、`.env`（`VITE_API_RECIPE_MANAGEMENT_URL`）、`.gitignore`、`index.html`、`main.ts`、`router.ts`（`createWebHistory(import.meta.env.BASE_URL)`、4 画面のルート。`/recipes/new` を先に定義）、`styles.css`（`rules/15-ui-style.md` のトークン、`--color-primary` は `#FFA36C`）、`components/Icon.vue` | REQ-001 / design.md フロントエンド設計、ui-design.md 共通の構成 | `src/features/recipe-management/frontend/` | 2h | `frontend` で `npm run dev` が起動する／`npm run build`（型検査を含む）が通る／ルートが 4 画面分あり、画面は仮の見出しでよい／API 基点をコードに直書きしていない |
| T-017 | 殻と共通部品: `App.vue`（ヘッダ・ナビ「レシピ」、PC は左ナビ / 768px 未満は下ナビ）、未ログイン時のログイン画面 URL への誘導、権限なしの表示、`api/client.ts`（Cookie 送信、認証エラーの共通処理）、確認ダイアログ（背景で閉じない） | REQ-001 / ui-design.md 共通の構成・共通の表示 | `src/features/recipe-management/frontend/src/` | 3h | ナビが PC・スマートフォンで規定の配置になり、詳細・登録・編集でも「レシピ」が現在地になる／ヘッダの戻るがメニュー画面 URL へ進む／401 でログイン画面 URL へ進み、403 でその旨を表示する／確認ダイアログが背景の押下で閉じない／ページ全体がスクロールしない |
| T-018 | API モジュール・型・補助関数: 材料・分量名称・レシピの各 API 呼び出しと、応答の型（api-design.md のオブジェクト）、`utils/`（分量の表示（接頭語＋数量＋接尾語）、分量名称の選択の補助（接頭語 → 接尾語）、入力の検証（メッセージに手順・材料の番号を含める）） | REQ-004、REQ-005、REQ-009 / api-design.md 全エンドポイント、ui-design.md SCR-002 | `src/features/recipe-management/frontend/src/api/`、`src/utils/` | 2h | api-design.md の全エンドポイントに対応する関数があり、`any` を使わずに型検査が通る／409 の文言で判別できる／分量の表示が数量あり・なしで仕様どおり／検証が、メニュー名・かな・説明・分量名称・数量の各規則で、番号入りのメッセージを返す |
| T-019 | レシピ一覧画面 SCR-001 | REQ-003 / ui-design.md SCR-001 | `src/features/recipe-management/frontend/src/views/` | 1.5h | メニュー名とかなが、かなの順に並び、行から詳細へ進める／新規から登録へ進める／読込中・空・エラーの表示がある |
| T-020 | レシピの入力フォーム部品と追加ダイアログ: `RecipeForm.vue`（メニュー名・かな、手順の追加・削除（最後の 1 件は削除不可）、材料の行の追加・削除、材料の選択、分量名称の選択（接頭語 → 接尾語）、数量（数量なしのときは入力不可）、手順説明、保存前の検証と、番号入りのエラー表示）、材料の追加ダイアログ、分量名称の追加ダイアログ（追加後に選択肢を取得し直し、その行に選ぶ） | REQ-005、REQ-008、REQ-009 / ui-design.md SCR-002 | `src/features/recipe-management/frontend/src/components/` | 4h | 手順・材料の行の追加・削除が仕様どおり／接頭語を選び直すと接尾語が先頭の組にそろう／数量なしの分量名称では数量が入力できず空になる／材料が未選択の行は送信から除かれる／追加ダイアログで追加した材料・分量名称が、開いた行で選ばれ、同名の 409 の文言がダイアログに出る／ダイアログが背景で閉じない |
| T-021 | レシピ登録画面 SCR-002、レシピ編集画面 SCR-004（`RecipeForm.vue` の利用、編集の初期値の組み立て、保存、保存後の詳細への遷移、エラー表示） | REQ-005、REQ-006 / ui-design.md SCR-002・SCR-004 | `src/features/recipe-management/frontend/src/views/` | 2h | 登録できて、詳細へ進む／同名のメニュー名で「同じメニュー名のレシピがあります」が出て入力が残る／編集で、現在の値が入った状態から更新でき、更新後の詳細へ進む／存在しないレシピで「レシピが見つかりません」が出て一覧へ戻れる |
| T-022 | レシピ詳細画面 SCR-003（メニュー名・かな、材料一覧、手順のカード、分量の表示、編集・削除、削除の確認ダイアログ、削除後の遷移） | REQ-004、REQ-007 / ui-design.md SCR-003 | `src/features/recipe-management/frontend/src/views/` | 2.5h | 材料一覧が工程の順・工程内の並びの順で、材料が無いレシピでは出ない／手順が番号順のカードで、分量の表示が仕様どおり／削除が確認ダイアログの後にだけ実行され、一覧へ戻る（成功メッセージを数秒示す）／存在しない・削除済みで「レシピが見つかりません」 |

### F. 仕上げ

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-023 | 画面幅の確認と調整: 全画面を Wide（1024px 以上）と Compact（400px 前後）で確認し、はみ出し・長い文字列・0 件・多数の手順と材料を直す | REQ-003〜006 / ui-design.md レイアウトの違い、`rules/31-web-app-responsive-layout-spec.md` | `src/features/recipe-management/frontend/src/` | 2h | 全画面で横スクロールが出ない／ページ全体がスクロールしない／タップ領域が 44px 以上／フォーカスの表示がある／材料の行が、Compact で縦に積まれる |
| T-024 | デプロイ資料: `frontend/nginx.example.conf`（公開 URL `/portal_recipe_management/`、API を同一オリジンにする場合の proxy）、`src/features/recipe-management/Readme.txt`（初回の準備・起動・DDL 適用） | REQ-001 / design.md デプロイ上の考慮、`rules/17-nginx-deploy.md` | `src/features/recipe-management/frontend/nginx.example.conf`、`src/features/recipe-management/Readme.txt` | 1h | nginx の設定例が `rules/17-nginx-deploy.md` に沿っている（`rewrite` は `last`、`try_files` と `break` を同じ location に置かない）／Readme の手順どおりに、バックエンドとフロントエンドを起動できる |
| T-025 | 結合確認: ブラウザ（自動操作）で、登録・詳細・編集・削除、材料・分量名称の追加、同名の失敗、Compact 幅の表示を通しで確認。実際の移行元 DB に対して、ドライランを実行し、結果を報告する | REQ-001〜014 / requirements.md 全受け入れ条件 | `src/features/recipe-management/` | 3h | requirements.md の受け入れ条件を一通り確認し、未達があれば一覧にして報告する／移行のドライランが、想定の件数（レシピ 12 件・対象外 2 件など）で通る |

## 実施順

1. 基盤: T-001 → T-002 → T-003
2. バックエンド API: T-004、T-005（独立）→ T-006 → T-007 → T-008
3. テスト: T-009（T-003 の後）、T-010（T-004・005 の後）、T-011（T-006・007 の後）。各 API の実装と並行して進めてよい。
4. 移行: T-012（T-002 の後。バックエンド API とは独立）→ T-013 → T-014 → T-015
5. フロントエンド: T-016 → T-017、T-018 → T-019 → T-020 → T-021 → T-022
6. 仕上げ: T-023、T-024 → T-025

合計の見積もり: 約 60 時間（バックエンド 20h、テスト 7h、移行 11h、フロントエンド 17h、仕上げ 6h ほか）。

## 要件とタスクの対応

| 要件 | タスク |
|------|--------|
| REQ-001 | T-003、T-009、T-016、T-017 |
| REQ-002 | T-004〜T-007、T-010、T-011 |
| REQ-003 | T-006、T-011、T-019 |
| REQ-004 | T-006、T-011、T-018、T-022 |
| REQ-005 | T-006、T-011、T-018、T-020、T-021 |
| REQ-006 | T-007、T-011、T-020、T-021 |
| REQ-007 | T-007、T-011、T-022 |
| REQ-008 | T-002、T-004、T-010、T-020 |
| REQ-009 | T-002、T-005、T-010、T-018、T-020 |
| REQ-010 | T-001、T-003、T-008、T-009 |
| REQ-011 | T-012、T-014 |
| REQ-012 | T-012、T-013、T-014 |
| REQ-013 | T-013、T-014 |
| REQ-014 | T-012、T-014、T-015 |
| 横断（画面幅・デプロイ・結合確認） | T-023、T-024、T-025 |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-21 21:23 | 未承認 | 初版 |
| 2026-09-21 21:24 | 承認済み | 初版を承認 |
