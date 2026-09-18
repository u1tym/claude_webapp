portal（ログインとメニュー）

作業は Windows PowerShell を想定する。


1. 起動方法

1.1 初回だけ

開発用 DB（localhost:5432）
  データベース: tstdb
  ユーザ: tstuser
  パスワード: TSTPASS
  管理者が作る場合は、管理者 postgres / postgres で
    python sql/apply.py
  を実行する（後述の「3. DDL の再適用」と同じ）。無ければ DB とユーザも作る。

バックエンド
  cd src\features\portal\backend
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  .env が無ければ、docs\specs\templates\backend.env.example を
  src\features\portal\backend\.env にコピーして値を確認する。

フロントエンド
  cd src\features\portal\frontend
  npm install
  .env が無ければ、次を置く。
    VITE_API_PORTAL_URL=http://localhost:8000

1.2 毎回の起動

バックエンド（作業ディレクトリは backend）
  cd src\features\portal\backend
  .\venv\Scripts\Activate.ps1
  uvicorn app.main:app --reload --port 8000

フロントエンド（作業ディレクトリは frontend、別の PowerShell）
  cd src\features\portal\frontend
  npm run dev

画面: http://localhost:5173/portal/
API:  http://localhost:8000
ログイン画面: http://localhost:5173/portal/login
メニュー画面: http://localhost:5173/portal/menu

nginx で出すときは、`npm run build` の dist をドキュメントルートの portal/ に置く
（portal/login/ には置かない）。設定例は frontend/nginx.example.conf。
既存 DB の login_url / menu_url が古いパスのときは、システム設定を
  http://<ホスト>/portal/login と http://<ホスト>/portal/menu に合わせる。


2. 運用コマンド

作業ディレクトリは backend。venv を有効化する。

  cd src\features\portal\backend
  .\venv\Scripts\Activate.ps1

ユーザ
  python -m app.cli user list
  python -m app.cli user add <ユーザ名> <パスワード>
  python -m app.cli user delete <ユーザ名>

機能
  python -m app.cli feature add <機能ID> <タイトル> <遷移先URL> [アイコンファイル]
  python -m app.cli feature update <機能ID> --title <タイトル> --url <遷移先URL> --icon <アイコンファイル>
  python -m app.cli feature delete <機能ID>

  add のアイコンファイルは省略できる。省略したときはアイコンなしで登録する。
  update の --title / --url / --icon は必要なものだけ指定する。
  アイコンは png / jpg / jpeg / gif / webp。DB に格納し、リポジトリには置かない。

メニュー割当
  python -m app.cli menu assign <ユーザ名> <機能ID> <表示順>
  python -m app.cli menu unassign <ユーザ名> <機能ID>

  表示順は整数。値が小さいほど先に表示する。


3. DDL の再適用

作業ディレクトリは backend。venv を有効化する。

  cd src\features\portal\backend
  .\venv\Scripts\Activate.ps1
  python sql/apply.py

内容:
  - 管理者 postgres で tstdb と tstuser が無ければ作る
  - sql/01_public.sql を tstuser で適用する
    （users / sessions / system_settings / features / menu_assignments）
  - システム設定の初期キーが無ければ入れる

CREATE TABLE IF NOT EXISTS と INSERT ... ON CONFLICT DO NOTHING のため、
既存の表や初期キーは消さない。
