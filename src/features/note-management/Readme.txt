note-management（ノート管理）

作業は Windows PowerShell を想定する。


1. 起動方法

1.1 初回だけ

開発用 DB（localhost:5432）
  データベース: tstdb
  ユーザ: tstuser
  パスワード: TSTPASS

DDL の適用（スキーマ note_management と 7 テーブル）
  cd src\features\note-management\backend
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python sql\apply.py
  何度実行しても同じ結果になる。

バックエンドの設定
  .env が無ければ、specs\templates\backend.env.example を
  src\features\note-management\backend\.env にコピーして値を確認する。
  CORS_ORIGINS は http://localhost:5183 にする。
  追加の設定（省略できる）:
    PARTS_MAX_REVISIONS  画像・バイナリの過去世代の保管数（既定 3）
    PART_MAX_BYTES       画像・バイナリ 1 件の大きさの上限（既定 10485760 = 10 MB）

フロントエンドの設定
  cd src\features\note-management\frontend
  npm install
  .env が無ければ、次を置く。
    VITE_API_NOTE_MANAGEMENT_URL=http://localhost:8009

利用者への割当
  本機能の機能マスタへの登録（識別子 note-management、遷移先 URL /portal_note_management/）と、
  利用者への割当は、ユーザ管理で行う。
  ログインは portal で行う（portal のログイン Cookie を使う）。


1.2 毎回の起動

バックエンド（作業ディレクトリは backend）
  cd src\features\note-management\backend
  .\venv\Scripts\Activate.ps1
  uvicorn app.main:app --reload --port 8009

フロントエンド（作業ディレクトリは frontend、別の PowerShell）
  cd src\features\note-management\frontend
  npm run dev
  ブラウザで http://localhost:5183/portal_note_management/ を開く。

デバッグ実行（ログインを省く）
  backend\.env の DEBUG_USER に、本機能が割り当てられたユーザ名を指定する。
  本番では空にする。


2. 機能について

- フォルダとファイルの階層で整理し、ファイルの中に、パーツ（テキスト・Markdown・TeX・URL・行動予定・
  チェックリスト・JPEG・PNG・バイナリ）を並べる。表のパーツは、提供しない。
- 削除は論理削除。画面の「削除済みを表示」から、削除解除できる。
- PDF 出力は、印刷用のレイアウトを作って、ブラウザの印刷ダイアログを開く。「PDF に保存」を選ぶ。
- 画像・バイナリは、1 件 10 MB まで。差し替えるたびに、前の内容が過去世代として保管される（既定 3 世代）。


3. テスト

  cd src\features\note-management
  backend\venv\Scripts\python.exe -m pytest tests

- 開発用 DB を使う。テスト用のユーザ・データはテストごとに作り、終了時に削除する。
- tests\test_migration.py は、管理者（既定 postgres / postgres。環境変数 PG_ADMIN_USER /
  PG_ADMIN_PASSWORD で変更可）で一時的な DB を作って移行を検証する。管理者で接続できないときは飛ばす。
- tests\test_config.py は、接続できない場合の確認で待ち時間があるため、1 分ほどかかる。


4. 別サーバ版（note）からのデータ移行

  backend\scripts\README.md を参照する。表のパーツは移行されない。


5. nginx でのデプロイ

  frontend\nginx.example.conf を参照する。公開 URL は /portal_note_management/ 。
  フロントは npm run build で作る dist の中身を、ドキュメントルートの features/note-management/ に置く。
  API を nginx 経由で公開するときは、画像・バイナリのアップロード（Base64 で最大 約 14 MB）のため、
  リクエスト本文の上限（client_max_body_size）を 16 MB 以上にし、画像の応答はバッファリングしない設定にする。


6. ログ

  backend\log\note-management.log（サイズでローテーション。LOG_MAX_BYTES / LOG_BACKUP_COUNT）
