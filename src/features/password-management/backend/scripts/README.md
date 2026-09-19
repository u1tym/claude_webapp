# 別サーバ版（psinfo）からのデータ移行

`sample/psinfo` で稼働している別サーバ版のパスワード管理サービスから、本機能（password-management）へデータを移行する手順。

## 前提

- 移行対象は、旧システムで削除されていない（`deleted_count = 0`）パスワードエントリだけ。
- 旧システムのアカウント名（`public.accounts.username`）と、本プロジェクトの `public.users.username` が一致するユーザだけに移行する。一致しないユーザのエントリは移行せず、一覧表示する。
- 移行先で既に同じタイトルが登録済みのエントリはスキップし、一覧表示する（`(user_id, title)` の一意制約に違反させないため）。
- パスワードの値は、いずれのスクリプトも標準出力・ログに出力しない。

## 手順

### 1. エクスポート（旧サーバ側、または旧サーバの DB に到達できる環境で実行）

```bash
python export_from_psinfo.py \
  --host <旧DBのホスト> --port 5432 --dbname tamtdb \
  --user tamtuser --password <旧DBのパスワード> \
  --output psinfo_export.json
```

接続情報は環境変数（`PSINFO_DB_HOST` / `PSINFO_DB_PORT` / `PSINFO_DB_NAME` / `PSINFO_DB_USER` / `PSINFO_DB_PASSWORD`）でも指定できる。

実行すると `psinfo_export.json` に、旧システムの全アカウント（`id`・`username`）と、未削除のパスワードエントリ（`aid`・`title`・`userword`・`psword`・`site`・`memo`）が書き出される。この JSON ファイルには平文パスワードが含まれるため、取り扱いに注意する（作業後は削除するか、安全な方法で破棄する）。

### 2. エクスポートした JSON を、本プロジェクトの実行環境へ転送する

`psinfo_export.json` を、この `password-management` バックエンドの venv が使える環境へコピーする。

### 3. インポート（本プロジェクトの DB に対して実行）

`src/features/password-management/backend` の venv を有効化し、`backend/.env` が本プロジェクトの DB を指していることを確認したうえで実行する。

```bash
cd src/features/password-management/backend
python scripts/import_to_password_management.py --input /path/to/psinfo_export.json
```

標準エラー出力に、成功件数・対象外（ユーザ不一致）件数・スキップ（タイトル重複）件数と、それぞれの内訳が表示される。

### 4. 後片付け

エクスポートした JSON ファイル（平文パスワードを含む）を、作業完了後に削除する。
