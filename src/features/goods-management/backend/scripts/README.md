# 別サーバ版（goods）からのデータ移行

`sample/goods` で稼働している別サーバ版のグッズ管理サービスから、本機能（goods-management）へデータを移行する手順。

## 前提

- 移行対象は、旧システムで削除されていない（`is_deleted = false`）商品と、それに関連する人物・アーティスト・媒体・アーティストと人物の関連・商品画像。
- 旧システムにはユーザ・アカウントの区別が無い。そのため全データは、インポート時に指定する本プロジェクトの **1人のユーザ** の所有として取り込む。
- 表示順（商品画像）は移行元の値をそのまま使う。

## 手順

### 1. エクスポート（旧サーバ側、または旧サーバの DB に到達できる環境で実行）

```bash
python export_from_goods.py \
  --host <旧DBのホスト> --port 5432 --dbname <旧DB名> \
  --user <旧DBユーザ> --password <旧DBパスワード> \
  --output goods_export.json
```

接続情報は環境変数（`GOODS_DB_HOST` / `GOODS_DB_PORT` / `GOODS_DB_NAME` / `GOODS_DB_USER` / `GOODS_DB_PASSWORD`）でも指定できる。

実行すると `goods_export.json` に、未削除の人物・アーティスト・アーティストと人物の関連・媒体・商品・商品画像が書き出される（画像データは Base64 化される）。

### 2. エクスポートした JSON を、本プロジェクトの実行環境へ転送する

`goods_export.json` を、この `goods-management` バックエンドの venv が使える環境へコピーする。

### 3. インポート（本プロジェクトの DB に対して実行）

`src/features/goods-management/backend` の venv を有効化し、`backend/.env` が本プロジェクトの DB を指していることを確認したうえで実行する。取り込み先のユーザ（`public.users.username`）を `--username` で指定する。

```bash
cd src/features/goods-management/backend
python scripts/import_to_goods_management.py --input /path/to/goods_export.json --username <取り込み先のユーザ名>
```

指定したユーザが存在しない、または論理削除済みの場合はエラーで終了する。

標準エラー出力に、人物・アーティスト・アーティストと人物の関連・媒体・商品・商品画像それぞれの成功件数（商品・商品画像は対象外件数も）が表示される。商品が対象外になるのは、参照する媒体・アーティストの取り込みに失敗した場合のみで、通常は発生しない。

### 4. 後片付け

エクスポートした JSON ファイルを、作業完了後に削除する（画像データを含むため）。
