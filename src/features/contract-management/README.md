# 契約管理（contract-management）

契約（電気・動画配信・金融口座・ファンクラブなど）の情報と、解約するための手順を、一元管理する機能です。契約を伴わないアカウント（ユーザ名とパスワードだけを控えるもの）も、同じ場所で管理します。

- 契約の登録・編集・削除・一覧・絞り込み・詳細（維持費、更新日、契約日、ログイン方法、依存契約、支払方法、解約方法など）
- 区分（利用者が作る。「金融機関」の指定を付けると、その区分の契約を、他の契約の支払方法に選べる）
- アカウント一覧（ユーザ名とパスワードだけを、手早く参照・コピーする。本機能を開いたときの最初の画面）
- 解約順の整理と、解約手順の PDF 出力（解約順に、名称と解約方法を並べる）
- 外部システム（生成AI など）が、API キーで、契約の参照・登録・更新をする（**パスワードの値は、入出力しない**）
- `password-management` からのデータの取り込み（統合の準備。`backend/scripts/README.md`）

仕様は `specs/contract-management/`（`requirements.md`、`design.md`、`ui-design.md`、`db-design.md`、`api-design.md`、`tasks.md`）にあります。

## 構成

| 場所 | 内容 |
|------|------|
| `backend/` | FastAPI（ポート 8012）。契約・区分・解約順の API。取り込みスクリプトは `backend/scripts/` |
| `frontend/` | Vue（開発用ポート 5186）。公開 URL は `/portal_contract_management/` |
| `tests/` | バックエンドのテスト（pytest）。フロントエンドのテストは `frontend/tests/`（vitest） |

認証は、`portal` が発行したセッション（Cookie）か、API キー（`Authorization: Bearer`。許可する操作は限られる）で行います。ログイン画面とメニュー画面は `portal` が担います。

## 開発環境のセットアップ

前提: 開発用 DB（`rules/13-db.md`）が起動していて、`portal` の DDL（スキーマ `public`）と、`api-key-management` の DDL（`public.api_keys`）が適用済みであること。

### バックエンド

```powershell
cd src\features\contract-management\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # 値を埋める（下の表）
.\venv\Scripts\python.exe sql\apply.py          # スキーマ contract_management と表を作る（繰り返し実行してよい）
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8012
```

`backend/.env` の主な項目（ひな型は `backend/.env.example`）:

| 項目 | 内容 |
|------|------|
| `DB_SERVER`、`DB_PORT`、`DB_DATABASE`、`DB_USERNAME`、`DB_PASSWORD` | 開発用 DB の接続情報（`Server`、`Port` などの形式も受け付ける） |
| `CORS_ORIGINS` | 許可するフロントのオリジン（開発では `http://localhost:5186`） |
| `SESSION_TIMEOUT_MINUTES` | セッションの有効期間。他機能と同じ値にする |
| `LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` | ログのローテーション（1 ファイルの上限バイト数と世代数。既定 10485760 と 5） |
| `DEBUG_USER` | 開発時だけ、認証せずにそのユーザとして処理する。本番では空にする |

別の設定ファイルを使うときは、環境変数 `CONTRACT_MANAGEMENT_ENV_FILE` に、そのパスを指定します（取り込みスクリプトの取り込み先を、本番の DB にするときなど）。

`.env` は秘密情報を含むため、リポジトリに含めません（`backend/.gitignore` で除外済み）。ログは `backend/log/contract-management.log` に出ます。**パスワード、ユーザ名、登録メールアドレス、2段階認証の送付先、API キー、セッション ID の値は、ログに出ません。**

### フロントエンド

```powershell
cd src\features\contract-management\frontend
npm install
copy .env.example .env      # VITE_API_CONTRACT_MANAGEMENT_URL（既定 http://localhost:8012）
npm run dev                 # http://localhost:5186/portal_contract_management/
```

### テスト

```powershell
# バックエンド（開発用 DB を使う。テスト用のデータは、テスト後に消える）
cd src\features\contract-management\tests
..\backend\venv\Scripts\python.exe -m pytest -q

# フロントエンド（API は、fetch の代役。DB・バックエンドは要らない）
cd src\features\contract-management\frontend
npm test
npm run build               # 型検査を含む
```

## パスワードの保存について

パスワードは、`password-management` と同じく、**DB に平文で保存**します（暗号化保存は対象外。`specs/contract-management/requirements.md` の非機能要件）。そのため、次の扱いにしています。

- 一覧、アカウント一覧、詳細、解約順、API キーの応答には、パスワードの値を含めない。含めるのは、設定されているか（`has_password`）と、「パスワード未設定」か（`password_unset`）だけ。
- パスワードの値は、`GET /contracts/{id}/password` で、1 件ずつ返す。画面の「表示」「コピー」を操作した時点で取得する。この API は、**Cookie 認証だけ**で、API キーでは 403。
- ログには、パスワードの値を出さない。

DB のバックアップや DB の管理者権限の扱いには、注意してください。

## 機能マスタへの登録とメニュー割当

契約管理をメニューに出し、メニューから開けるようにするには、`portal` の運用コマンドで、機能マスタへの登録と、利用者への割当を行います。運用コマンドは Web を介さず DB を直接更新します。実行する場所は `portal` のバックエンドです。

```powershell
cd src\features\portal\backend
```

### 1. 機能の登録

機能 ID は **`contract-management` のままにします**。バックエンドは、この ID の機能が利用者に割り当てられているかで、利用の可否を判定します（API キーも同じ）。

```powershell
# 開発（フロントを npm run dev で動かすとき）
.\venv\Scripts\python.exe -m app.cli feature add contract-management 契約管理 http://localhost:5186/portal_contract_management/

# 本番（nginx で公開するとき。ホストは環境に合わせる）
.\venv\Scripts\python.exe -m app.cli feature add contract-management 契約管理 https://example.com/portal_contract_management/
```

遷移先 URL は、**末尾に `/` を付けた公開 URL** にします（`frontend/nginx.example.conf` の注記）。URL を直すときは、`feature update contract-management --url ...` を使います。

### 2. 利用者への割当

```powershell
.\venv\Scripts\python.exe -m app.cli user list
.\venv\Scripts\python.exe -m app.cli menu assign <ユーザ名> contract-management 10    # 最後の数字は、メニューの表示順
.\venv\Scripts\python.exe -m app.cli menu unassign <ユーザ名> contract-management
```

### 3. 確認する

1. 割当を受けたユーザで `portal` にログインし、メニューに「契約管理」が出ること。
2. 「契約管理」を選ぶと、`/portal_contract_management/` が開き、アカウント一覧が表示されること。
3. 割り当てていないユーザで開くと、「この機能は利用できません」と、戻るボタンだけが出ること。

## 本番への配置

1. `frontend` で `npm run build` を実行し、`dist` の中身を、ドキュメントルートの `features/contract-management/` に置く。
2. nginx の設定は `frontend/nginx.example.conf` を参考にする（公開 URL `/portal_contract_management/`、API を同一オリジンにする場合の proxy）。
3. バックエンドは、`backend` の venv で uvicorn（または gunicorn）を起動する。ポートは 8012。`.env` の `DEBUG_USER` は空にする。
4. DDL の適用（`sql\apply.py`）と、機能マスタへの登録・割当を行う。
5. `password-management` のデータを取り込むときは、`backend/scripts/README.md` の手順に従う。

## 外部システム（生成AI など）からの利用（API キー）

API キーの発行・失効は、機能 `api-key-management` の画面で行います。発行したキーを、`Authorization: Bearer <キー>` で渡します（URL には載せない）。キーの権限は、持ち主と同じで、持ち主に「契約管理」が割り当てられている必要があります。

### 使えること（API キー）

| 操作 | API |
|------|-----|
| 契約の一覧・詳細（絞り込み: `keyword`、`category_id`、`status`、`has_contract`、`password_unset`） | `GET /contracts`、`GET /contracts/{id}` |
| 契約の登録・更新 | `POST /contracts`、`PATCH /contracts/{id}` |
| 区分の一覧 | `GET /categories` |
| 解約順（解約の対象と順序、警告） | `GET /cancellation-plan` |

### 使えないこと（API キー。403）

契約の削除、パスワードの値の取得、アカウント一覧、区分の追加・変更・削除、解約順の保存・候補の取得。

### パスワードについて

- 応答には、パスワードの値を含めません。設定されているか（`has_password`）と、「パスワード未設定」か（`password_unset`）だけを返します。
- 登録・更新の要求に `password` を含めると、**`null` でも空文字でも 400** で、何も保存しません。
- API キーで登録した契約は、パスワードが未設定になります。**パスワードは、人が画面で入力・変更します。** 画面の契約一覧で、「パスワード未設定のみ」にチェックを入れると、入力待ちの契約が見つかります。
- 更新（`PATCH`）は、`password` 以外の全項目を送ります。送らなかった任意の項目は、空になります。保存済みのパスワードは、変わりません。

### 例

```powershell
$h = @{ Authorization = "Bearer wak_xxxxxxxx" }

# 契約の一覧（パスワードが未設定のもの）
Invoke-RestMethod -Headers $h "https://example.com/portal-contract-management-api/contracts?password_unset=true"

# 契約の登録（名称だけは必須。区分を省略すると「その他」）
Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
  -Body '{"name":"ネット動画","login_methods":["password"],"username":"taro@example.com","fee_amount":990,"fee_cycle":"monthly"}' `
  "https://example.com/portal-contract-management-api/contracts"
```

MCP サーバ（別プロジェクト `mcp`）へのツールの追加は、この機能の完成後に、別途行います。

## 取り込み（password-management から）

`backend/scripts/import_password_management.py` が、`password-management` の削除されていないエントリを、契約を伴わない契約として取り込みます（何度実行しても、重複しません。取り込み元は変更しません）。手順は `backend/scripts/README.md` です。
