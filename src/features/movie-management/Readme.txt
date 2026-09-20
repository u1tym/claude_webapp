movie-management（動画管理・視聴）

作業は Windows PowerShell を想定する。


1. 起動方法

1.1 初回だけ

開発用 DB（localhost:5432）
  データベース: tstdb
  ユーザ: tstuser
  パスワード: TSTPASS

DDL の適用（スキーマ movie_management と 10 テーブル、共通ジャンル 7 件）
  cd src\features\movie-management\backend
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python sql\apply.py
  何度実行しても同じ結果になる。

バックエンドの設定
  .env が無ければ、specs\templates\backend.env.example を
  src\features\movie-management\backend\.env にコピーして値を確認する。
  CORS_ORIGINS は http://localhost:5181 にする。

フロントエンドの設定
  cd src\features\movie-management\frontend
  npm install
  .env が無ければ、次を置く。
    VITE_API_MOVIE_MANAGEMENT_URL=http://localhost:8007

利用者への割当
  本機能の機能マスタへの登録（識別子 movie-management、遷移先 URL /portal_movie_management/）と、
  利用者への割当は、ユーザ管理で行う。
  ログインは portal で行う（portal のログイン Cookie を使う）。


1.2 毎回の起動

バックエンド（作業ディレクトリは backend）
  cd src\features\movie-management\backend
  .\venv\Scripts\Activate.ps1
  uvicorn app.main:app --reload --port 8007

フロントエンド（作業ディレクトリは frontend、別の PowerShell）
  cd src\features\movie-management\frontend
  npm run dev
  ブラウザで http://localhost:5181/portal_movie_management/ を開く。

デバッグ実行（ログインを省く）
  backend\.env の DEBUG_USER に、本機能が割り当てられたユーザ名を指定する。
  本番では空にする。


2. 動画ファイルについて

- 動画は MP4（H.264 + AAC、-movflags +faststart 推奨）にする。
  H.265 (HEVC) は iPhone のブラウザで再生できないため、登録できない。
  変換例:
    ffmpeg -i input.mp4 -c:v libx264 -profile:v main -level 4.0 -pix_fmt yuv420p -c:a aac -movflags +faststart output.mp4
- 動画の長さは最大 約 4 時間。
- 動画のデータは DB に約 4 MB のチャンクに分けて保管する。


3. テスト

  cd src\features\movie-management
  backend\venv\Scripts\python.exe -m pytest tests

- 開発用 DB を使う。テスト用のユーザ・データはテストごとに作り、終了時に削除する。
- tests\test_migration.py は、管理者（既定 postgres / postgres。環境変数 PG_ADMIN_USER /
  PG_ADMIN_PASSWORD で変更可）で一時的な DB を作って移行を検証する。管理者で接続できないときは飛ばす。


4. 別サーバ版（movie）からのデータ移行

  backend\scripts\README.md を参照する。


5. nginx でのデプロイ

  frontend\nginx.example.conf を参照する。公開 URL は /portal_movie_management/ 。
  フロントは npm run build で作る dist の中身を、ドキュメントルートの features/movie-management/ に置く。
  API を nginx 経由で公開するときは、チャンクのアップロード（1 リクエスト約 4 MB）のため、
  リクエスト本文の上限（client_max_body_size）を 8 MB 以上にし、動画の配信はバッファリングしない設定にする。


6. ログ

  backend\log\movie-management.log（サイズでローテーション。LOG_MAX_BYTES / LOG_BACKUP_COUNT）
