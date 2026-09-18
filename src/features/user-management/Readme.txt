user-management（ユーザ管理）

作業は Windows PowerShell を想定する。
ログインとメニューは portal が担う。本機能はログイン画面を持たない。
表は portal が用意した public を使う。DDL は持たない。


1. 起動方法

1.1 前提

  portal の DB（localhost:5432 の tstdb / tstuser）が使えること。
  無ければ portal の Readme.txt「3. DDL の再適用」を先に行う。

  画面から使うときは、portal の API（8000）と画面（5173）も起動する。
  先に portal でログインしてから、本機能の画面を開く。

1.2 初回だけ

バックエンド
  cd src\features\user-management\backend
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  .env が無ければ、docs\specs\templates\backend.env.example を
  src\features\user-management\backend\.env にコピーして値を確認する。
  CORS_ORIGINS は本機能の Vue オリジンにする。
    CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174,http://[::1]:5174
  SESSION_TIMEOUT_MINUTES は portal と同じ値にする。

フロントエンド
  cd src\features\user-management\frontend
  npm install
  .env が無ければ、次を置く。
    VITE_API_USER_MANAGEMENT_URL=http://localhost:8001

1.3 毎回の起動

バックエンド（作業ディレクトリは backend）
  cd src\features\user-management\backend
  .\venv\Scripts\Activate.ps1
  uvicorn app.main:app --reload --port 8001

フロントエンド（作業ディレクトリは frontend、別の PowerShell）
  cd src\features\user-management\frontend
  npm run dev

画面: http://localhost:5174/portal_user_management/
API:  http://localhost:8001
ユーザ画面: http://localhost:5174/portal_user_management/users
機能画面: http://localhost:5174/portal_user_management/features
割当画面: http://localhost:5174/portal_user_management/assignments

nginx で出すときは、`npm run build` の dist をドキュメントルートの
features/user-management/ に置く。公開 URL は /portal_user_management/ のまま
（設定例は frontend/nginx.example.conf）。
ブラウザで /features/user-management/ は開かない。
機能マスタの遷移先 URL は公開パスに合わせる
（本番例: https://<ホスト>/portal_user_management/users）。

未ログインで画面を開くと、portal のログイン画面へ進む。
本機能が割り当てられていないときは「この機能を使えません」と出す。


2. 本機能の登録

初回だけ、portal の運用コマンドで機能マスタへ載せ、運用ユーザへ割り当てる。
作業ディレクトリは portal の backend。venv を有効化する。

  cd src\features\portal\backend
  .\venv\Scripts\Activate.ps1
  python -m app.cli feature add user-management ユーザ管理 http://localhost:5174/portal_user_management/users
  python -m app.cli menu assign <ユーザ名> user-management 1

アイコンファイルは省略できる。指定するときはコマンド末尾に付ける。
形式は png / jpg / jpeg / gif / webp。DB に格納し、リポジトリには置かない。
表示順は整数。値が小さいほど先に表示する。

以降のユーザ・機能・割当の追加・更新・削除は、本機能の画面で行う。
自分自身の削除、本機能（user-management）の削除、
自分自身から本機能を外すことはできない。


3. テスト

作業ディレクトリは backend。venv を有効化する。

  cd src\features\user-management\backend
  .\venv\Scripts\Activate.ps1
  python -m pytest ..\tests
