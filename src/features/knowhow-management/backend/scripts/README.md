# 別サーバ版（knowhow）からのデータ移行

`sample/knowhow` で稼働している別サーバ版のノウハウ管理サービスから、本機能（knowhow-management）へデータを移行する手順。

## 前提

- 移行対象は、旧システムで削除されていない（`is_deleted = false`）大項目・中項目・ノウハウだけ。
- 旧システムのアカウント名（`public.accounts.username`）と、本プロジェクトの `public.users.username` が一致するユーザだけに移行する。一致しないユーザの分は移行せず、一覧表示する。
- 親（大項目・中項目）が対象外・スキップになった場合、その配下の中項目・ノウハウも移行されない（「対象外（親大項目が未移行）」「対象外（所属中項目が未移行）」として一覧表示する）。
- 移行先で名称が重複する大項目・中項目はスキップし、一覧表示する。
- 表示順は移行元の値をそのまま使う。

## 手順

### 1. エクスポート（旧サーバ側、または旧サーバの DB に到達できる環境で実行）

```bash
python export_from_knowhow.py \
  --host <旧DBのホスト> --port 5432 --dbname <旧DB名> \
  --user <旧DBユーザ> --password <旧DBパスワード> \
  --output knowhow_export.json
```

接続情報は環境変数（`KNOWHOW_DB_HOST` / `KNOWHOW_DB_PORT` / `KNOWHOW_DB_NAME` / `KNOWHOW_DB_USER` / `KNOWHOW_DB_PASSWORD`）でも指定できる。

実行すると `knowhow_export.json` に、旧システムの全アカウント（`id`・`username`）と、未削除の大項目・中項目・ノウハウが書き出される。

### 2. エクスポートした JSON を、本プロジェクトの実行環境へ転送する

`knowhow_export.json` を、この `knowhow-management` バックエンドの venv が使える環境へコピーする。

### 3. インポート（本プロジェクトの DB に対して実行）

`src/features/knowhow-management/backend` の venv を有効化し、`backend/.env` が本プロジェクトの DB を指していることを確認したうえで実行する。

```bash
cd src/features/knowhow-management/backend
python scripts/import_to_knowhow_management.py --input /path/to/knowhow_export.json
```

標準エラー出力に、大項目・中項目・ノウハウそれぞれの成功件数、対象外（ユーザ不一致、または親が未移行）件数、スキップ（名称重複）件数と、その内訳が表示される。

### 4. 後片付け

エクスポートした JSON ファイルを、作業完了後に削除する。
