# contract-management タスク分解

> `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後に作成する。
> タスクは 1〜4 時間程度で完了できる粒度にする。

## 概要

対象機能: `contract-management`

ソース配置:

- フロントエンド: `src/features/contract-management/frontend`
- バックエンド: `src/features/contract-management/backend`（取り込みスクリプトは `backend/scripts/`）
- テスト: `src/features/contract-management/tests`（フロントのテストは `frontend` の `vitest`）

関連要件: REQ-001 〜 REQ-014

前提:

- `portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当・API キーは `public` の既存を読むだけ（複製しない。API キーは最終利用日時だけ更新する）。本機能固有の業務テーブルはスキーマ `contract_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能で行う（本タスクの対象外）。
- 他機能の Vue・CSS・コンポーネントを import しない。`icons/` の SVG から使う分だけ `frontend/src/components/Icon.vue` に複製する（`rules/15-ui-style.md`）。
- 土台の実装（設定ファイルの読み込み、接続プール、認証、ログ、例外ハンドラ、フロントの殻・API クライアント・確認ダイアログ・アイコン）は、`password-management` と `expense-management`（API キー認証を含む）の実装を参考にし、次の点を取り入れる: 設定ファイルの変数名は `DB_SERVER` 形式と `Server` 形式の両方を受け付ける、設定ファイルの場所を環境変数（`CONTRACT_MANAGEMENT_ENV_FILE`）で切り替えられる、接続に失敗したときに接続プールの枠を返す、DB の失敗の原因（先頭の 1 行）をログに出す。
- ポート: バックエンド 8012、フロントエンド 5186。`--color-primary` は Magenta `#E58FE0`。
- 各タスクは、実装前に `requirements.md` と 4 つの設計書を確認する。設計にない機能は加えない。
- MCP サーバへのツールの追加は、本タスクの対象外（別プロジェクト `mcp` で、本機能の完成後に別途行う）。`api-key-management` の SPEC の改訂も対象外。
- 実施の順序は、下の「実施順」に従う。

## タスク一覧

### A. バックエンド（基盤・認証）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-001 | バックエンドの土台: `venv`、`requirements.txt`（fastapi、uvicorn、psycopg2-binary、python-dotenv、pytest、httpx）、`.env`（ひな型 `specs/templates/backend.env.example`。CORS は `http://localhost:5186`）、`.gitignore`、`app/config.py`（変数名の両形式、`CONTRACT_MANAGEMENT_ENV_FILE`）、`app/logger.py`、`app/db.py`（接続プール、接続失敗時に枠を返す）、`app/main.py`（FastAPI 生成、CORS、例外ハンドラ、ログの初期化） | REQ-001、REQ-011 / design.md 起動・モジュール構成 | `src/features/contract-management/backend/` | 2.5h | `uvicorn app.main:app --port 8012` が起動する／`.env` の値を読める（両形式の変数名）／ログが `log/` に出て、サイズでローテーションする／未処理例外は 500 の一文だけを返し、内部情報を含めない |
| T-002 | DDL: `sql/01_contract_management.sql`（スキーマ、4 テーブル `categories`・`contracts`・`contract_dependencies`・`cancellation_plan`、制約、部分一意・一意（遅延可能を含む）インデックス、検査）と `sql/apply.py`。再実行できること（`IF NOT EXISTS` 等） | REQ-001〜REQ-008、REQ-014 / db-design.md 全テーブル | `src/features/contract-management/backend/sql/` | 3h | 開発用 DB に適用でき、2 回目の適用も成功する／db-design.md の制約・インデックスが作られている（区分の名称の重複、「その他」の重複・金融機関、ステータス・周期・精度の値、維持費の組、契約日と精度の整合、契約終了日の条件、契約を伴わない契約の項目が NULL、2段階認証の送付先と方式、自分自身への依存・支払方法、解約順の `position` の重複が、DB で拒否される）／削除済み同士の同名は入る |
| T-003 | セッション検証と API キー認証、機能割当判定、共通部品: `app/security.py`（SHA-256 ハッシュ）、`app/deps.py`（Cookie `session_id`、期限切れ・論理削除は 401、割当なしは 403、`DEBUG_USER`、期限の延長。`Authorization: Bearer` のとき `public.api_keys` で判定し `last_used_at` を更新、期限は延ばさない、失敗しても Cookie に戻らない。判定の経路を要求に渡し、API キーで許可しない操作は 403 にするための部品）、`app/services/access_service.py`、`app/repos.py`（`public` の読み取り）、`app/routers/settings.py`（`GET /settings`）、`app/errors.py`（入力不正・対象なし・競合）、`app/common.py`（前後の空白を除いた必須の文字列など） | REQ-001、REQ-013 / design.md 認証 / api-design.md 認証・API キーによる認証・`GET /settings` | `src/features/contract-management/backend/app/` | 4h | 未ログイン・期限切れ・論理削除済みユーザは 401、割当なしは 403（本文は api-design.md の文言）／`DEBUG_USER` で Cookie なしでも動く／API キーで、不正・失効・期限切れ・持ち主の論理削除は 401、割当なしは 403、許可で `last_used_at` が更新される／`GET /settings` が認証不要で 4 つの値を返す／業務エラーが 400・404・409 と一文の本文に変換される |

### B. バックエンド（業務 API）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-004 | 区分 API: `GET /categories`（「その他」がなければ作ってから返す）、`POST /categories`、`PATCH /categories/{id}`、`DELETE /categories/{id}`（`repos.py`、`services/category_service.py`、`routers/categories.py`。名称の検査、重複の 409、「その他」の変更・削除・金融機関の拒否、使用中の削除の 409、金融機関の指定を外す制限） | REQ-006、REQ-012 / design.md 区分、api-design.md 区分 | `src/features/contract-management/backend/app/` | 3h | api-design.md のステータス・文言どおり／「その他」が先頭、続いて ID 昇順で返る／使用中の区分の削除、支払方法として使われている区分の金融機関の指定を外す操作が 409／削除済みの区分と同じ名称で追加できる／他ユーザの区分は 404／API キーでは `GET` だけ許可、それ以外は 403 |
| T-005 | 契約の入力検査と表現（Contract）の部品: 入力の検査（`has_contract` による項目の制限、維持費の組、契約日と精度の整合と形式、契約終了日の条件、2段階認証の送付先と方式、依存契約・支払方法の対象（本人・削除されていない・自分以外・重複なし・金融機関の区分）、名称・文字列のトリム、`password` の空文字）、契約の表現の組み立て（`login_methods`、`has_password`・`password_unset`、`fee_*`、契約日の文字列、`depends_on`・`payment_contract`・`depended_by`・`payment_for`（削除されていないものだけ）を、一覧でも問い合わせの回数が増えすぎないようまとめて取得） | REQ-001、REQ-005、REQ-014 / design.md 契約・パスワードの扱い、api-design.md 契約の表現・契約の入力 | `src/features/contract-management/backend/app/` | 4h | api-design.md の表のとおりに入力を検査・正規化し、違反は 400／契約の表現が、契約を伴わない契約で、契約を伴う契約だけの項目を `null`（配列は `[]`）にする／どの表現にも、パスワードの値が含まれない／単体テストで、境界（0、精度ごとの形式、空白、重複）を確認できる |
| T-006 | 契約の参照 API: `GET /contracts`（keyword、category_id、status、has_contract、password_unset の絞り込み）、`GET /contracts/{id}`、`GET /contracts/{id}/password`、`GET /accounts`（`repos.py`、`services/contract_service.py`、`routers/contracts.py`、`routers/credentials.py`） | REQ-004、REQ-005、REQ-007、REQ-013、REQ-014 / api-design.md 各エンドポイント | `src/features/contract-management/backend/app/` | 3h | 一覧が、本人の削除されていない契約を ID 昇順で返し、条件の組み合わせが「すべてに合う」で絞れる／keyword が大文字小文字を区別せず、パスワードを対象にしない／`GET /accounts` が、ユーザ名またはパスワードを持つ契約だけを返し、パスワードの値を含めない／パスワードの取得が 1 件ずつ、`null`（未設定）も返す／他ユーザ・削除済みは 404／API キーで、一覧・詳細は許可、パスワードの取得とアカウント一覧は 403 |
| T-007 | 契約の登録・更新・削除 API: `POST /contracts`、`PATCH /contracts/{id}`、`DELETE /contracts/{id}`（`services/contract_service.py`、`routers/contracts.py`。依存の循環の検査（依存先をたどる）、金融機関の区分から金融機関でない区分への変更の制限、契約を伴わないへの切替で項目を消し解約順から外す、ステータスが解約で契約終了日を消し解約順から外す、更新で `password` なしのときは保存済みの値を変えない、API キーで `password` を含むと 400、削除で解約順から外す） | REQ-001〜REQ-003、REQ-012、REQ-013 / design.md 契約・パスワードの扱い、api-design.md 契約の入力・POST・PATCH・DELETE | `src/features/contract-management/backend/app/` | 4h | api-design.md のとおり登録・更新・論理削除できる／同じ名称で登録できる／循環が 409、区分の変更の制限が 409／API キーで登録した契約は、パスワードが未設定／API キーで `password` を含む要求は 400 で何も保存されない／更新で `password` を省略するとパスワードが変わらない／API キーで `DELETE` は 403／削除した契約が他の契約の表現から外れる |
| T-008 | 解約順 API: `GET /cancellation-plan`（`position` 順、対象の条件を満たさない契約を除く、警告の算出）、`GET /cancellation-plan/candidates`、`PUT /cancellation-plan`（全置き換え、`position` は 1 から連番、遅延可能な一意制約を使う）（`services/cancellation_service.py`、`routers/cancellation.py`） | REQ-008、REQ-009、REQ-012、REQ-013 / design.md 解約順、api-design.md 解約順 | `src/features/contract-management/backend/app/` | 3h | 保存した順で返り、再取得しても同じ／契約を伴わない・ステータスが解約・他ユーザ・重複・削除済みを含む保存は 400／ステータスが解約になった契約、削除した契約、契約を伴わないにした契約が、取得で除かれる／警告が、依存先が先に並ぶ組を返す／応答にパスワード・ユーザ名・登録メールアドレスが含まれない／API キーで `GET /cancellation-plan` は許可、それ以外は 403 |
| T-009 | ログの組み込み: 各サービス・ルータに、入力・判断結果・失敗理由の出力を入れる。パスワード、ユーザ名、登録メールアドレス、2段階認証の送付先、API キー全体とそのハッシュ、セッション ID を出さない。API キーによる要求は、識別用の先頭部分と持ち主のユーザ名を出す | REQ-011 / design.md ログ | `src/features/contract-management/backend/app/` | 1.5h | 契約・区分・解約順の登録・変更・削除・参照（一覧・アカウント一覧・詳細・パスワードの取得）の試行と成否が `log/` に出る／失敗の内部理由が出る／パスワードなどの値が出ない（識別子・件数・名称だけ） |

### C. バックエンドのテスト

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-010 | テスト基盤と、認証・設定・DDL のテスト（`conftest.py`: テスト用ユーザ・セッション・機能割当・API キーの作成と後始末（依存のある行を順に消す）、`test_auth.py`（Cookie・`DEBUG_USER`・API キーの各判定）、`test_config.py`（変数名の両形式、DB の失敗の原因のログ、接続失敗が続いても枠が尽きない）、`test_ddl.py`（制約・インデックスの確認）） | REQ-001、REQ-011、REQ-013 / api-design.md 認証、db-design.md | `src/features/contract-management/tests/` | 3h | 未ログイン・期限切れ・論理削除ユーザ・割当なし・`DEBUG_USER`・API キーの各挙動を確認できる／DDL の制約（部分一意、遅延可能な一意、検査）が DB で効くことを直接確認する／テスト用のデータがテスト後に残らない |
| T-011 | 区分のテスト（`test_categories.py`） | REQ-006、REQ-012 / api-design.md 区分 | `src/features/contract-management/tests/` | 2h | 取得（「その他」の自動作成、並び順）、追加（空白、重複、削除済みと同名は可、金融機関）、名称変更の反映、「その他」の変更・削除の拒否、使用中の削除の 409、金融機関の指定を外す制限、他ユーザの 404 を、DB の値と照合して確認する |
| T-012 | 契約の参照のテスト（`test_contracts_read.py`、`test_accounts.py`） | REQ-004、REQ-005、REQ-007、REQ-014 / api-design.md 契約の表現・GET | `src/features/contract-management/tests/` | 3h | 一覧の絞り込み（各条件と組み合わせ、keyword の大文字小文字、パスワードが対象外）、表現の各項目（契約日の形式、`has_password`・`password_unset`、`depends_on`・`payment_contract`・`depended_by`・`payment_for`）、パスワードの取得、アカウント一覧の対象と除外、応答のどこにもパスワードの値がないこと、他ユーザ・削除済みの 404 を確認する |
| T-013 | 契約の登録・更新・削除のテスト（`test_contracts_write.py`） | REQ-001〜REQ-003、REQ-012 / api-design.md 契約の入力・POST・PATCH・DELETE | `src/features/contract-management/tests/` | 4h | 各項目の検査（名称、維持費の組、契約日の精度、契約終了日の条件、2段階認証の送付先、契約を伴わない契約の項目、依存契約・支払方法の対象）、同名の登録、更新（`password` の省略で維持、全項目の置き換え、契約を伴わないへの切替で項目が消え解約順から外れる、解約で契約終了日が消える）、循環の 409、区分変更の制限の 409、削除（参照元の表現から外れる、解約順から外れる）、他ユーザの ID の指定が 400・404 になることを確認する |
| T-014 | 解約順のテスト（`test_cancellation.py`） | REQ-008、REQ-009、REQ-012 / api-design.md 解約順 | `src/features/contract-management/tests/` | 2h | 保存・取得の順序、候補の条件、保存の入力検査（重複、対象外の契約）、条件を満たさなくなった契約の除外、警告の算出（依存先が先／後）、空配列の保存、応答に機微な項目が含まれないこと、他ユーザの契約の指定が 400 になることを確認する |
| T-015 | API キーの権限のテスト（`test_api_key_scope.py`） | REQ-013 / api-design.md 認証・エンドポイント一覧の API キー列 | `src/features/contract-management/tests/` | 2h | エンドポイント一覧の「API キー」列どおり、可のものは動き、不可のものは 403／`password` を含む登録・更新は 400 で保存されない／API キーで登録・更新した契約のパスワードが変わらない・未設定になる／API キーの持ち主以外の契約は参照も更新もできない／どの応答にもパスワードの値が含まれない |

### D. 取り込み（password-management から）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-016 | 取り込みスクリプト `scripts/import_password_management.py`: `password_management.entries` の削除されていない行を、利用者ごとに、契約を伴わない契約として取り込む（名称←タイトル、ユーザ名、パスワード、ホームページ←サイトURL、メモ、区分は「その他」（なければ作る）、ステータスは有効、ログイン方法はユーザ名とパスワード）。`imported_from_entry_id` で重複を防ぐ（再実行可）。取り込み元は読み取りだけ。ドライラン（`--dry-run`）。件数と、取り込めなかった件数・理由を出力する（パスワード・ユーザ名の値は出さない）。接続失敗の表示（どの DB か。パスワードを出さない） | REQ-010 / design.md 取り込み | `src/features/contract-management/backend/scripts/` | 3h | 取り込んだ契約が、契約を伴わない・ステータス有効・区分「その他」で、各項目が写っている／2 回実行しても重複しない／取り込み元の行が変わらない／ドライランは書き込まない／件数と理由が出力される |
| T-017 | 取り込みのテスト（`test_import.py`）: テスト用のユーザと `password_management.entries` の行を作って実行し、結果を DB の値と照合する | REQ-010 / design.md 取り込み | `src/features/contract-management/tests/` | 2.5h | 利用者ごとに本人のエントリだけが取り込まれる／削除済みのエントリは取り込まれない／再実行で件数が増えない／取り込み元が変わらない／ログ・出力にパスワード・ユーザ名の値が出ない |
| T-018 | 取り込みの手順書 `scripts/README.md`（前提、事前準備（DDL の適用、利用者の存在）、実行、ドライラン、再実行、結果の読み方、取り込み後の確認） | REQ-010 | `src/features/contract-management/backend/scripts/` | 1h | 手順書のとおりにドライランと実行ができる |

### E. フロントエンド

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-019 | フロントの土台: `package.json`（vue、vue-router、vite、typescript、vue-tsc、vitest）、`vite.config.ts`（`base: "/portal_contract_management/"`、port 5186）、`tsconfig`、`.env`（`VITE_API_CONTRACT_MANAGEMENT_URL`）、`.gitignore`、`main.ts`、`router.ts`（`createWebHistory(import.meta.env.BASE_URL)`。`/` がアカウント一覧、`/contracts`、`/categories`、`/cancellation`）、`styles.css`（トークン、Magenta） | REQ-001 / design.md 起動・モジュール構成、ui-design.md 画面一覧 | `src/features/contract-management/frontend/` | 2.5h | `npm run dev` で 5186 に起動する／`npm run build`（型検査含む）が通る／4 つのルートが解決される |
| T-020 | 殻と共通部品: `App.vue`（ヘッダ・ナビ「アカウント一覧」「契約一覧」「区分」「解約順」の順、PC は左ナビ / 768px 未満は下ナビ）、未ログイン時のログイン画面 URL への誘導、権限なしの表示、`api/client.ts`（Cookie 送信、認証エラーの扱い）、`components/Icon.vue`、確認ダイアログ、コピーボタン、パスワードの表示切替・コピーの共通部品、成功・エラー・読込中・空の表示 | REQ-001、REQ-005 / ui-design.md 画面一覧・状態別の表示、`rules/15-ui-style.md` | `src/features/contract-management/frontend/src/` | 3h | 未ログインは `login_url` へ誘導される／ナビが Wide と Compact で切り替わり、本機能を開くとアカウント一覧が表示される／ダイアログは背景のクリックで閉じない／アイコンのみのボタンに `aria-label` がある |
| T-021 | API モジュール・型・補助関数: api-design.md の全エンドポイントの呼び出しと応答・入力の型（`any` を使わない）、補助関数（契約日の精度ごとの表示と入力形式、維持費の表示、ステータス・周期・ログイン方法の表示名） | REQ-001〜REQ-009 / api-design.md 全エンドポイント | `src/features/contract-management/frontend/src/` | 2.5h | 全エンドポイントの呼び出しが型付きで揃う／補助関数の単体テストが通る（契約日 3 精度と不明、維持費の「月額 / 年間」表示） |
| T-022 | アカウント一覧 SCR-001: 検索欄、一覧（名称・ユーザ名・ホームページのリンク・コピー・パスワードのマスク／表示／隠す／コピー（操作時に取得）・「パスワード未設定」の表示）、読込中・空・エラー、スマートフォンのカード表示 | REQ-007、REQ-014 / ui-design.md SCR-001 | `src/features/contract-management/frontend/src/` | 3h | 一覧が表示され、検索で絞り込める／パスワードは「表示」「コピー」を押すまで取得されず、一覧の取得の応答にも含まれない／未設定の行はボタンが出ない／コピー直後に「コピー済」になる |
| T-023 | 区分 SCR-003: 追加欄（名称・「金融機関」のチェック）、一覧（「金融機関」のバッジ、編集（名称・金融機関の指定）、削除・確認、「その他」は編集・削除なし）、使用中・外せないときのメッセージ、読込中・空・エラー | REQ-006 / ui-design.md SCR-003 | `src/features/contract-management/frontend/src/` | 3h | 追加・名称変更・金融機関の指定・削除ができる／「その他」にボタンが出ない／使用中の削除、金融機関の指定を外せないときにメッセージが一覧の先頭に出る／重複・空白が入力欄の近くに出る |
| T-024 | 契約一覧 SCR-002 の一覧: 検索欄、絞り込み（区分、ステータス、契約の有無、パスワード未設定のみ）、新規登録ボタン、一覧（名称・区分・ステータス・維持費・更新日・「パスワード未設定」のバッジ）、読込中・空・エラー、スマートフォンのカード表示 | REQ-004、REQ-014 / ui-design.md SCR-002 | `src/features/contract-management/frontend/src/` | 3h | 条件を組み合わせて絞り込める（すべてに合うもの）／維持費・更新日が無い行は「-」／既定でステータスが解約の契約も表示される／0 件の文言が絞り込みの有無で変わる |
| T-025 | 契約一覧の詳細表示（モーダル）: 基本・ログイン・契約・問い合わせ先・関連の表示、パスワードのマスク／表示／コピー（操作時に取得）、各項目のコピー、ホームページのリンク、契約日の精度に応じた表示、関連の名称リンクで別の契約の詳細へ切り替え、編集・削除・閉じる | REQ-005、REQ-014 / ui-design.md SCR-002 詳細表示 | `src/features/contract-management/frontend/src/` | 4h | 全項目が表示され、契約を伴わない契約では契約の節が出ない／設定されていない項目は「-」／パスワードの扱いが ui-design.md のとおり（未設定は「パスワード未設定」）／関連のリンクで切り替わる |
| T-026 | 登録・編集フォーム（基本とログイン）: 名称、契約を伴う・伴わない、区分、ステータス、ホームページ、メモ、ログイン方法（チェックと、2段階認証の送付先の出し分け）、ユーザ名、パスワード（表示切替。編集では空欄で「変更するときだけ入力」）、登録メールアドレス、送信前の検査、保存・キャンセル、失敗時のメッセージ | REQ-001、REQ-002 / ui-design.md SCR-002 登録・編集フォーム | `src/features/contract-management/frontend/src/` | 4h | 名称だけで登録できる／送付先の入力欄が、対応する方式を選んだときだけ出る／編集でパスワードを空欄のまま保存すると変わらない／失敗はフォーム内に一文で示され、フォームは残る |
| T-027 | 登録・編集フォーム（契約と関連）: 契約を伴うときだけの項目（維持費と周期、更新日、契約日の精度と入力の切り替え、無料期間の終了日、契約終了日（ステータスが解約のときだけ）、自動更新、契約者名義、会員番号、解約の受付期限、解約手数料・違約金、最低契約期間、解約方法、問い合わせ先）、依存契約（複数選択、名称で絞り込み、自分以外）、支払方法（金融機関の区分の契約から 1 つ、自分以外。無いときの文言）、契約を伴わないへの切替で値が消えるときの確認 | REQ-001、REQ-002 / ui-design.md SCR-002 登録・編集フォーム | `src/features/contract-management/frontend/src/` | 4h | 契約を伴わないに切り替えると契約の項目が隠れ、値が入っているときは保存時に確認が出る（キャンセルでフォームに戻る）／契約日の精度で入力欄が切り替わる／支払方法の選択肢が金融機関の区分の契約だけ／循環・区分変更の制限などの 409 がフォーム内の一文で出る |
| T-028 | 契約の削除: 詳細からの削除確認ダイアログ、削除後の一覧の更新と成功メッセージ、失敗時の表示 | REQ-003 / ui-design.md SCR-002 削除確認 | `src/features/contract-management/frontend/src/` | 1.5h | 削除すると一覧から消え、成功メッセージが数秒出る／キャンセルで何も起きない／失敗は一文で示す |
| T-029 | 解約順 SCR-004 の編集: 解約順の一覧（番号、名称、解約方法の先頭、依存契約、上へ・下へ・外す）、対象にできる契約の一覧（絞り込み、加える）、警告の表示、保存（未保存の表示）、PC は左右・スマートフォンは縦並び、読込中・空・エラー | REQ-008 / ui-design.md SCR-004 | `src/features/contract-management/frontend/src/` | 4h | 加える・外す・上へ・下へが画面内で反映され、保存で確定する／警告が「『A』は『B』に依存しています。『B』が先に解約される並びです」の形で出て、保存もできる／先頭の「上へ」と末尾の「下へ」が無効／未保存の変更が示される |
| T-030 | 解約手順の PDF 出力: 印刷用の領域（見出し、出力日、番号・名称・解約方法。未入力は「未入力」）、「PDF出力」ボタン（0 件・未保存の変更があるとき無効で理由を表示）、`window.print()`、印刷用の CSS（画面には出さない）。パスワード・ユーザ名・登録メールアドレスを取得も出力もしない | REQ-009 / ui-design.md SCR-004 | `src/features/contract-management/frontend/src/` | 3h | 保存した解約順のとおりに印刷用のレイアウトが組まれ、ブラウザの印刷で「PDF に保存」できる／日本語が崩れない／印刷用の領域に機微な項目がない／無効の条件と理由の表示が仕様どおり |
| T-031 | フロントのテスト（`vitest`）: アカウント一覧、契約一覧の絞り込み、詳細のパスワードの扱い（取得は操作時のみ）、フォームの項目の出し分け・送信前の検査・契約を伴わないへの切替の確認、区分の操作、解約順の並べ替え・警告・保存の無効条件、補助関数 | REQ-001〜REQ-009、REQ-014 / ui-design.md 全画面 | `src/features/contract-management/frontend/src/**/*.test.ts` | 4h | `npm test` が全件成功する／パスワードの値が、一覧の描画と、操作前の状態に現れないことを確認するテストがある |

### F. 仕上げ

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-032 | 画面幅の確認と調整: 全画面・ダイアログを Wide（1024px 以上）と Compact（400px 前後）で確認し、はみ出し・長い文字列・0 件・多数の契約を直す | REQ-004〜REQ-009 / ui-design.md、`rules/31-web-app-responsive-layout-spec.md` | `src/features/contract-management/frontend/` | 3h | 横スクロールなしで主要な操作に届く／長い名称・解約方法で崩れない／フォームのダイアログ内で長い項目をスクロールできる |
| T-033 | デプロイ資料: `frontend/nginx.example.conf`（公開 URL `/portal_contract_management/`）、`README.md`（起動、環境変数、DDL の適用、取り込みの参照、ポート、API キーの使い方（許可する操作とパスワードを扱わないこと）） | 横断 / design.md、`rules/17-nginx-deploy.md` | `src/features/contract-management/` | 2h | 資料のとおりに開発・配置・API キーでの参照ができる |
| T-034 | 結合確認: ブラウザ（自動操作）で、区分の追加・金融機関の指定、契約（契約を伴う・伴わない）の登録・編集・削除、パスワードの表示・コピー、アカウント一覧、解約順の保存・警告・PDF 出力の画面、を確認する。API キーで、参照・登録・更新ができ、パスワードの値が返らず、削除ができないことを確認する | REQ-001〜REQ-014 / 全設計 | （確認のみ） | 3h | 主な操作が実画面で成功する／API キーの確認が仕様どおり／確認で見つかった不具合を直す |

## 実施順

1. 基盤: T-001 → T-002 → T-003
2. バックエンド API: T-004、T-005（T-003 の後）→ T-006 → T-007 → T-008 → T-009
3. テスト: T-010（T-003 の後）、T-011（T-004 の後）、T-012（T-006 の後）、T-013（T-007 の後）、T-014（T-008 の後）、T-015（T-008 の後）。各 API の実装と並行して進めてよい。
4. 取り込み: T-016（T-002 の後。バックエンド API とは独立）→ T-017 → T-018
5. フロントエンド: T-019 → T-020、T-021 → T-022、T-023、T-024（独立）→ T-025 → T-026 → T-027 → T-028 → T-029 → T-030 → T-031
6. 仕上げ: T-032、T-033 → T-034

合計の見積もり: 約 100 時間（バックエンド基盤 9.5h、業務 API 18.5h、テスト 16h、取り込み 6.5h、フロントエンド 41.5h、仕上げ 8h）。

## 要件とタスクの対応

| 要件 | タスク |
|------|--------|
| REQ-001 | T-001〜T-003、T-005、T-007、T-010、T-013、T-019、T-020、T-026、T-027、T-031 |
| REQ-002 | T-005、T-007、T-013、T-026、T-027、T-031 |
| REQ-003 | T-007、T-013、T-028 |
| REQ-004 | T-006、T-012、T-024、T-031 |
| REQ-005 | T-005、T-006、T-012、T-020、T-025、T-031 |
| REQ-006 | T-004、T-011、T-023、T-031 |
| REQ-007 | T-006、T-012、T-022、T-031 |
| REQ-008 | T-008、T-014、T-029、T-031 |
| REQ-009 | T-008、T-014、T-030、T-031 |
| REQ-010 | T-016、T-017、T-018 |
| REQ-011 | T-001、T-009、T-010 |
| REQ-012 | T-004、T-007、T-008、T-011、T-013、T-014 |
| REQ-013 | T-003、T-006〜T-008、T-010、T-015、T-033、T-034 |
| REQ-014 | T-002、T-005、T-006、T-012、T-022、T-024、T-025 |
| 横断（画面幅・デプロイ・結合確認） | T-032、T-033、T-034 |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-10-03 11:11 | 未承認 | 初版 |
| 2026-10-03 11:14 | 承認済み | 初版を承認 |
