recipe-management（レシピ管理）

作業は Windows PowerShell を想定する。


1. 起動方法

1.1 初回だけ

開発用 DB（localhost:5432）
  データベース: tstdb
  ユーザ: tstuser
  パスワード: TSTPASS

DDL の適用（スキーマ recipe_management と 5 テーブル、共通の材料 12 件・分量名称 4 件）
  cd src\features\recipe-management\backend
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python sql\apply.py
  何度実行しても同じ結果になる。

バックエンドの設定
  .env が無ければ、specs\templates\backend.env.example を
  src\features\recipe-management\backend\.env にコピーして値を確認する。
  CORS_ORIGINS は http://localhost:5182 にする。

フロントエンドの設定
  cd src\features\recipe-management\frontend
  npm install
  .env が無ければ、次を置く。
    VITE_API_RECIPE_MANAGEMENT_URL=http://localhost:8008

利用者への割当
  本機能の機能マスタへの登録（識別子 recipe-management、遷移先 URL /portal_recipe_management/）と、
  利用者への割当は、ユーザ管理で行う。
  ログインは portal で行う（portal のログイン Cookie を使う）。


1.2 毎回の起動

バックエンド（作業ディレクトリは backend）
  cd src\features\recipe-management\backend
  .\venv\Scripts\Activate.ps1
  uvicorn app.main:app --reload --port 8008

フロントエンド（作業ディレクトリは frontend、別の PowerShell）
  cd src\features\recipe-management\frontend
  npm run dev
  ブラウザで http://localhost:5182/portal_recipe_management/ を開く。

デバッグ実行（ログインを省く）
  backend\.env の DEBUG_USER に、本機能が割り当てられたユーザ名を指定する。
  本番では空にする。


2. 材料・分量名称について

- 全利用者共通の材料・分量名称（初期データ）と、利用者ごとの独自のものがある。
  共通のものは変更・削除できない。独自のものは、レシピの登録・編集の画面から追加できる。
- レシピは、利用者ごとに持つ。削除したレシピは一覧・詳細に出ない（論理削除）。


3. テスト

  cd src\features\recipe-management
  backend\venv\Scripts\python.exe -m pytest tests

- 開発用 DB を使う。テスト用のユーザ・データはテストごとに作り、終了時に削除する。
- tests\test_migration.py は、管理者（既定 postgres / postgres。環境変数 PG_ADMIN_USER /
  PG_ADMIN_PASSWORD で変更可）で一時的な DB を作って移行を検証する。管理者で接続できないときは飛ばす。
- tests\test_config.py は、接続できない場合の確認で待ち時間があるため、1 分ほどかかる。


4. 別サーバ版（recipe）からのデータ移行

  backend\scripts\README.md を参照する。


5. nginx でのデプロイ

  frontend\nginx.example.conf を参照する。公開 URL は /portal_recipe_management/ 。
  フロントは npm run build で作る dist の中身を、ドキュメントルートの features/recipe-management/ に置く。


6. ログ

  backend\log\recipe-management.log（サイズでローテーション。LOG_MAX_BYTES / LOG_BACKUP_COUNT）
