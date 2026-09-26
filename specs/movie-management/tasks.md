# movie-management タスク分解

> `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後に作成する。
> タスクは 1〜4 時間程度で完了できる粒度にする。

## 概要

対象機能: `movie-management`

ソース配置:

- フロントエンド: `src/features/movie-management/frontend`
- バックエンド: `src/features/movie-management/backend`（移行プログラムは `backend/scripts/`）
- テスト: `src/features/movie-management/tests`

関連要件: REQ-001 〜 REQ-023

前提:

- `portal` の Python は import しない。ユーザ・セッション・システム設定・機能マスタ・メニュー割当は `public` の既存を読むだけ（複製しない）。本機能固有の業務テーブルはスキーマ `movie_management` に置く。本機能の機能マスタ登録と利用者への割当は、ユーザ管理機能で行う（本タスクの対象外）。
- 他機能の Vue・CSS・コンポーネントを import しない。`icons/` の SVG から使う分だけ `frontend/src/components/Icon.vue` に複製する（`rules/15-ui-style.md`）。
- 実装の参考は `sample/movie`（動画の分割アップロード、範囲配信、再生の各処理）。ただしソースをそのまま複製せず、本プロジェクトの方式（psycopg2、Cookie セッション、Vue Router の `createWebHistory`）に合わせて書き直す。
- ポート: バックエンド 8007、フロントエンド 5181。
- 各タスクは、実装前に `requirements.md` と 4 つの設計書を確認する。設計にない機能は加えない。
- 実施の順序は、下の「実施順」に従う。

## タスク一覧

### A. バックエンド（基盤・認証）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-001 | バックエンドの土台: `venv`、`requirements.txt`（fastapi、uvicorn、psycopg2-binary、python-dotenv、python-multipart、pytest、httpx）、`.env`（ひな型 `specs/templates/backend.env.example`）、`.gitignore`、`app/config.py`、`app/logger.py`、`app/db.py`、`app/main.py`（CORS、ルータ登録の枠） | REQ-018 / design.md 起動・モジュール構成 | `src/features/movie-management/backend/` | 2h | `backend` で venv を有効化して `uvicorn app.main:app --reload --port 8007` が起動する／`.env` の接続情報（tstdb / tstuser）で DB に接続できる／`LOG_MAX_BYTES` `LOG_BACKUP_COUNT` を `.env` から読み、`log/` にサイズローテーションで出力する／秘密情報をソースに直書きしていない |
| T-002 | DDL: `sql/01_movie_management.sql`（スキーマ、10 テーブル、制約、索引、`video_chunks.data` の `STORAGE EXTERNAL`、共通ジャンル 7 件の初期データ）。再実行できること（`IF NOT EXISTS`、`ON CONFLICT DO NOTHING`） | REQ-010 / db-design.md 全テーブル | `src/features/movie-management/backend/sql/` | 3h | 開発用 DB に適用でき、2 回目の適用でもエラーにならない／db-design.md の全テーブル・制約・索引が存在する／共通ジャンルが 7 件入る／共通ジャンルの同名重複、同一作品内の話数重複、`octet_length(data) <> byte_length` の登録がそれぞれ DB で拒否される |
| T-003 | セッション検証と機能割当判定: `app/security.py`、`app/deps.py`（Cookie `session_id`、期限切れ・論理削除は 401、割当なしは 403、`DEBUG_USER`、期限の延長）、`app/services/access_service.py`、`app/repos/public.py`（ユーザ・セッション・システム設定・機能割当の読み取り）、`app/routers/settings.py`（`GET /settings`） | REQ-001 / design.md 認証 / 認可、api-design.md 認証・`GET /settings` | `src/features/movie-management/backend/app/` | 3h | 未ログイン・期限切れは 401、割当なし・論理削除済みの機能は 403／`DEBUG_USER` 指定時のみ Cookie なしで通り、その場合も割当を判定する／`GET /settings` が認証なしで返る／セッション ID をログ・応答に出さない |
| T-004 | 共通部品: `app/errors.py`（入力不正・対象なし・重複・処理不可の例外）、例外ハンドラ（400 / 404 / 409 / 422 / 500 の本文は api-design.md の文言）、ページ分けの入力検証と `pagination` の組み立て、文字列（前後の空白除去・空判定）の検証 | REQ-018 / api-design.md 共通事項（データ形式・ページ分け・エラー） | `src/features/movie-management/backend/app/` | 2h | 共通エラーが api-design.md の本文どおりに返る／`page` `per_page` の範囲外は 400／`total_pages` が仕様どおり（0 件は 0）／内部情報が本文に出ない |

### B. バックエンド（業務 API）

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-005 | ジャンル API: `GET` `POST /genres`（`app/repos/genre.py`、`app/services/genre_service.py`、`app/routers/genres.py`） | REQ-010、REQ-002 / api-design.md ジャンル | `src/features/movie-management/backend/app/` | 2h | 共通ジャンルと本人の独自ジャンルだけが表示順で返り、`is_system` で区別できる／他ユーザの独自ジャンルは返らない／独自ジャンルを追加でき、同名は 409（共通ジャンルと同名は可）／共通ジャンルは変更できない |
| T-006 | 作品 API: `GET` `POST /series`、`GET /series/{series_id}`（`repos/series.py`、`services/series_service.py`、`routers/series.py`） | REQ-009、REQ-002 / api-design.md 作品 | `src/features/movie-management/backend/app/` | 2h | 本人の作品だけが登録日時の降順で返る／`q` でタイトルの部分一致（大文字小文字を区別しない）／詳細で所属動画が作品内順序・話数の順に返る／他ユーザの作品は 404 |
| T-007 | 動画の登録・取得・編集・削除: `POST /videos`、`GET /videos/{video_id}`、`PATCH /videos/{video_id}`、`DELETE /videos/{video_id}`（`repos/video.py`、`services/video_service.py`、`routers/videos.py`。ジャンルの関連の置換、作品・ジャンルの所有確認、話数重複の 409、変更不可項目の 400） | REQ-003、REQ-006、REQ-008 / api-design.md 動画 | `src/features/movie-management/backend/app/` | 4h | 動画情報が「登録中」で作られる（再生時間の範囲・タイトルの検査）／他ユーザの作品・ジャンルの指定は 404、話数重複は 409／PATCH は指定項目だけ更新し、ジャンルを全置換、`duration_ms` などの指定は 400／DELETE でチャンク・サムネイル・ジャンル関連・再生状態・プレイリスト項目が消え、続きから視聴の参照が NULL になる |
| T-008 | 動画一覧: `GET /videos`（状態・ジャンル・作品・キーワードの絞り込み、3 種の並び替え、最終再生日時の並びで未再生を末尾、`VideoSummary` の組み立て（作品名・ジャンル・サムネイルの有無・再生位置・視聴完了）、ページ分け） | REQ-005 / api-design.md `GET /videos`、VideoSummary | `src/features/movie-management/backend/app/` | 3h | 既定は「再生可能」のみ／`status=all` で全状態／`genre_id` `series_id` `q` で絞り込める／`sort` `order` の全組み合わせが仕様どおり／応答に動画ファイルのデータが含まれない／N+1 にならない（一覧 1 回の取得＋補助の取得 2〜3 回以内） |
| T-009 | アップロード: `POST /videos/{video_id}/chunks`、`POST /videos/{video_id}/complete`、`POST /videos/{video_id}/replace`（`services/upload_service.py`。チャンクの妥当性・重複・8 MiB 上限、チャンク数とサイズの同時更新、完了時の照合、差し替え開始時の既存チャンク削除と再生状態のリセット） | REQ-003、REQ-007 / design.md 動画の登録とアップロード・動画ファイルの差し替え、api-design.md | `src/features/movie-management/backend/app/` | 3h | 「登録中」の動画にだけチャンクを追加でき、重複は 409、空・8 MiB 超は 400／完了はチャンク数が 0 または不一致なら 422、一致すれば「再生可能」／差し替えでチャンクが消え「登録中」に戻り、再生位置と視聴完了がリセットされ、動画情報とサムネイルは残る |
| T-010 | 動画の配信: `GET /videos/{video_id}/stream`（`services/stream_service.py`。チャンクのバイト長の積み上げ、`Range` の 3 形式、206 / 416 / 400 / 422、要求の範囲にかかるチャンクだけを 1 つずつ取得、応答ヘッダ） | REQ-011、REQ-002 / design.md 動画の配信（範囲配信）、api-design.md `GET /videos/{video_id}/stream` | `src/features/movie-management/backend/app/` | 4h | `Range` なしで全体、あり（`a-b`、`a-`、`-n`）で 206 と正しい `Content-Range`／範囲が動画の末尾を超えるときは末尾に丸め、開始が大きさ以上は 416／複数範囲・不正な形式は 400、「再生可能」でなければ 422／チャンクの境界をまたぐ範囲で、元のファイルと一致するバイト列が返る／全体を同時にメモリへ載せない |
| T-011 | サムネイル: `GET` `PUT /videos/{video_id}/thumbnail`（`repos/thumbnail.py`。1 動画 1 枚の置き換え、画像形式・サイズの検証） | REQ-004、REQ-002 / api-design.md サムネイル | `src/features/movie-management/backend/app/` | 2h | 登録・置き換えでき、取得で登録時の形式と本体が返る／未登録・他ユーザの動画は 404／5 MiB 超、画像でない形式は 400 |
| T-012 | 再生: `POST /videos/{video_id}/playback/start`、`PUT /videos/{video_id}/playback/state`、`GET /videos/{video_id}/next`、`GET /playback/history`、`GET /playback/last`（`repos/playback.py`、`services/playback_service.py`、`routers/playback.py`。再開位置の決定、再生回数・最終再生日時の更新、位置の範囲検査、作品内／単発の次の動画、続きから視聴の情報の更新と参照解除の扱い） | REQ-011〜015 / design.md 再生、api-design.md 再生系 | `src/features/movie-management/backend/app/` | 4h | 開始で `resume` に応じた位置（動画の長さ以上の前回位置、つまり超えるとき・末尾のときは 0）と `start_chunk` が返り、再生回数が増える／「再生可能」でなければ 422／状態の保存は範囲外を 400 とし、再生回数は変えない／次の動画が仕様どおり（作品内は作品内順序で、同じ順序は話数・識別子の順。単発は登録日時順。いずれも「再生可能」のみ）／履歴が最終再生日時の降順／`/playback/last` が、削除・再生不可のものを返さない |
| T-013 | プレイリスト管理: `GET` `POST /playlists`、`GET` `PATCH` `DELETE /playlists/{playlist_id}`、`PUT /playlists/{playlist_id}/items`（`repos/playlist.py`、`services/playlist_service.py`、`routers/playlists.py`。件数の集計、項目の置換を 1 トランザクション、本人の動画のみ、更新日時の更新） | REQ-016 / design.md 作品・ジャンル・プレイリスト、api-design.md プレイリスト | `src/features/movie-management/backend/app/` | 3h | 更新日時の降順の一覧に、名前・説明・件数が出る／詳細で項目が並び順に返る／項目の置換で他ユーザの動画は 404、同じ動画を複数回含められ、途中で失敗しても元の並びが残る／削除しても動画は残る／他ユーザのプレイリストは 404 |
| T-014 | プレイリスト再生: `POST /playlists/{playlist_id}/playback/start`、`GET .../items/{item_id}/next`、`GET .../items/{item_id}/prev`、`PUT .../items/{item_id}/playback/state`（`playlist_service.py` の拡張。続きから視聴の情報の更新、再生できない項目でも 200 で `start_chunk` を null にする） | REQ-012、REQ-015、REQ-017 / design.md プレイリストの再生、api-design.md プレイリスト再生系 | `src/features/movie-management/backend/app/` | 3h | 開始が `resume` に応じて先頭または続きから／空のプレイリストは 422／次・前が `sort_order` の隣接で、無いときは `has_next` / `has_prev` が false／再生できない動画の項目も 200／位置の保存が動画の再生状態と「最後に再生したプレイリスト」を更新し、「最後に単独で再生した動画」は変えない |
| T-015 | ログの組み込み: 各サービスに、入力・判断結果・失敗理由の出力を入れる。高頻度の処理（チャンクの受信・配信、位置の定期保存）は動画単位・再生単位でまとめて出す。パスワード・セッション ID・Cookie を出さない | REQ-018 / design.md ログ | `src/features/movie-management/backend/app/` | 2h | 登録・変更・削除・ファイルの登録・差し替え・再生開始・一覧・検索の試行と成否が `log/` に出る／失敗時に内部理由が出る／チャンクごとの行が出ない／セッション ID が出ない |

### C. バックエンドのテスト

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-016 | テスト基盤と、認証・ジャンル・作品のテスト（`conftest.py`: テスト用ユーザ・セッション・機能割当の作成と後始末、`test_auth.py`、`test_genres_series.py`） | REQ-001、REQ-002、REQ-009、REQ-010 / api-design.md 認証・ジャンル・作品 | `src/features/movie-management/tests/` | 3h | 401 / 403 / 論理削除済みユーザ、他ユーザのデータが 404、ジャンルの共通・独自の扱いと重複、作品の一覧・詳細を検証するテストが通る／テストが本番データに影響しない |
| T-017 | 動画・アップロード・配信・サムネイルのテスト（`test_videos.py`、`test_upload.py`、`test_stream.py`、`test_thumbnail.py`） | REQ-003〜008、REQ-011 / api-design.md 動画・配信・サムネイル | `src/features/movie-management/tests/` | 4h | 登録の 3 段階（正常・重複チャンク・チャンク数不一致・登録中以外）、差し替え、削除の連鎖、一覧の絞り込み・並び替え、配信の `Range` 各形式（チャンク境界をまたぐ範囲を含む）と 416 / 400 / 422、サムネイルの置き換えを検証するテストが通る |
| T-018 | 再生・プレイリストのテスト（`test_playback.py`、`test_playlists.py`） | REQ-011〜017 / api-design.md 再生系・プレイリスト | `src/features/movie-management/tests/` | 3h | 再開位置、状態の保存と範囲外、次の動画（作品内・単発）、履歴、続きから視聴（削除・再生不可を除く）、プレイリストの作成・置換・削除・再生・前後移動を検証するテストが通る |

### D. 移行プログラム

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-019 | 移行の骨格: `scripts/migrate_from_movie.py`（引数と環境変数、移行元の読み取り専用接続、移行先の接続（`backend/.env`）、接続失敗の表示（どちらの DB か。パスワードを出さない）、ユーザの対応付けと対象外の一覧、`--dry-run` `--username`、進捗・結果報告の共通処理、終了コード） | REQ-019、REQ-021、REQ-023 / design.md 移行プログラム | `src/features/movie-management/backend/scripts/` | 3h | 移行元・移行先のどちらの接続失敗かがわかる／ユーザ名が一致し論理削除でない利用者だけが対象になり、対象外はユーザ名と件数が一覧される／`--username` で絞れる／`--dry-run` で書き込みが起きない／失敗があれば終了コードが 0 以外／移行元へ書き込む SQL が存在しない |
| T-020 | 移行（ジャンル・作品・動画）: 共通ジャンルの名称対応（無ければ追加）、独自ジャンル・作品の対応付けと追加、動画 1 件 1 トランザクションの移行（「再生可能」のみ、移行済みの判定、チャンクをサーバ側カーソルで 1 件ずつコピー、サムネイル・ジャンル関連、チャンク数・バイト長の合計の照合、失敗時のロールバック、日時・話数・作品内順序などの引き継ぎ） | REQ-020、REQ-022 / design.md 動画 1 件の移行 | `src/features/movie-management/backend/scripts/` | 4h | 移行元と移行先で、チャンクのバイト列がすべて一致する／識別子は移行先で採番し、登録日時・更新日時・話数・作品内順序・再生時間・ファイル形式・チャンクの分割が移行元と同じ／「登録中」「エラー」は対象外として一覧される／照合が不一致または途中失敗の動画は移行先に残らず、次の動画へ進む／再実行で移行済みがスキップされる／メモリに動画全体を載せない（数百 MB の動画で確認） |
| T-021 | 移行（再生状態・プレイリスト・続きから視聴）: 再生状態の移行（移行先に既にあればスキップ）、プレイリストと項目の移行（同一利用者・同名はスキップ、移行されなかった動画の項目を取り除き一覧）、続きから視聴の移行（移行先に既にあればスキップ、指す先が無い部分は空） | REQ-020、REQ-022 / design.md 処理の流れ 6〜8 | `src/features/movie-management/backend/scripts/` | 3h | 再生位置・視聴完了・再生回数・最終再生日時が引き継がれる／プレイリストの並びが同じで、取り除いた項目が一覧される／再実行で重複が生じない／移行先で進んでいる再生状態を上書きしない |
| T-022 | 移行のテスト: 移行元 DB（サンプルの構成を再現する DDL を `tests/fixtures/` に置き、テスト用の別 DB に作る）と、移行先（開発用 DB）の両方を使うテスト（`test_migration.py`） | REQ-019〜022 / design.md 移行プログラム | `src/features/movie-management/tests/` | 4h | ユーザ対応付け（一致・不一致・論理削除）、状態による対象外、共通ジャンルの名称対応、動画のバイト列の一致、照合不一致時のロールバック、再実行のスキップ、プレイリスト項目の取り除き、`--dry-run` で書き込みが起きないことを検証するテストが通る／テスト後にテスト用 DB と移行先のテストデータが後始末される |
| T-023 | 移行の手順書 `scripts/README.md`（前提、事前準備（移行先の DDL 適用・利用者の存在）、接続情報の指定、ドライラン、実行、再実行、結果の読み方、後片付け） | REQ-023 / design.md 移行プログラム | `src/features/movie-management/backend/scripts/README.md` | 1h | README の手順どおりに、ドライランと本実行ができる／対象・対象外・スキップの意味と、再実行の挙動が書かれている |

### E. フロントエンド

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-024 | フロントの土台: `package.json`（vue、vue-router、vite、typescript、vue-tsc）、`vite.config.ts`（`base: "/portal_movie_management/"`、port 5181）、`tsconfig`、`.env`（`VITE_API_MOVIE_MANAGEMENT_URL`）、`.gitignore`、`index.html`、`main.ts`、`router.ts`（`createWebHistory(import.meta.env.BASE_URL)`、11 画面のルート）、`styles.css`（`rules/15-ui-style.md` のトークン、`--color-primary` は Violet `#A78BFA`）、`components/Icon.vue`、`api.ts`（基点 URL、Cookie 送信、認証エラーの共通処理、設定の取得） | REQ-001 / design.md フロントエンド設計、ui-design.md 共通の構成 | `src/features/movie-management/frontend/` | 3h | `frontend` で `npm run dev` が起動する／`npm run build`（型検査を含む）が通る／ルートが 11 画面分あり、画面は仮の見出しでよい／API 基点をコードに直書きしていない |
| T-025 | 殻と共通部品: `App.vue`（ヘッダ・ナビ、PC は左ナビ / 768px 未満は下ナビ、現在地の強調）、未ログイン時のログイン画面 URL への誘導、権限なしの表示、メッセージ帯（成功・エラー）、確認ダイアログ（背景で閉じない）、ページ送り、動画カード、進捗バー | REQ-001、REQ-005 / ui-design.md 共通の構成・共通の表示 | `src/features/movie-management/frontend/src/` | 4h | ナビ 5 項目が PC・スマートフォンで規定の配置になり、下位画面でも入口の項目が現在地になる／ヘッダの戻るがメニュー画面 URL へ進む／401 でログイン画面 URL へ進み、403 でその旨を表示する／確認ダイアログが背景の押下で閉じない／ページ全体がスクロールしない |
| T-026 | API モジュールと型: ジャンル・作品・動画・再生・プレイリストの各 API 呼び出しと、応答の型（api-design.md のオブジェクト）。エラー（400 / 404 / 409 / 422）の判別 | REQ-003〜017 / api-design.md 全エンドポイント | `src/features/movie-management/frontend/src/api/`、`src/types/` | 2h | api-design.md の全エンドポイントに対応する関数があり、`any` を使わずに型検査が通る／409 の文言（話数重複・同名ジャンル）で判別できる |
| T-027 | ジャンル画面 SCR-008 | REQ-010 / ui-design.md SCR-008 | `src/features/movie-management/frontend/src/views/` | 2h | 共通・独自のラベル付きで一覧が表示される／独自ジャンルを追加でき、同名は「同じ名前のジャンルがあります」を表示する／読込中・空・エラーの表示がある |
| T-028 | 作品画面 SCR-006、作品詳細画面 SCR-007 | REQ-009 / ui-design.md SCR-006・SCR-007 | `src/features/movie-management/frontend/src/views/` | 3h | 一覧・タイトル検索・ページ送り・登録フォーム（モーダル）が動く／詳細で所属動画が並び、「再生可能」の行だけ再生画面へ進める／存在しない作品で「作品が見つかりません」と表示され一覧へ戻れる |
| T-029 | 動画ファイルの処理部品: `utils/mp4Codec.ts`（映像コーデックの判定、H.264 への変換コマンド例）、`utils/videoThumbnail.ts`（5 秒地点または先頭フレームの生成）、動画ファイルの再生時間の取得、分割アップロード関数（約 4 MB ごとに順番に送信、進捗の通知、完了通知） | REQ-003、REQ-004、REQ-007 / design.md 動画のアップロードと再生（フロントの責務） | `src/features/movie-management/frontend/src/utils/`、`src/api/` | 3h | H.265 の MP4 を判定できる／サムネイルが生成できる（5 秒未満は先頭）／4 MB を超えるファイルが複数チャンクに分けて送信され、進捗が「n/m」で通知され、最後に完了が通知される／チャンクの送信が 1 つずつ順に行われる |
| T-030 | 動画登録画面 SCR-002 | REQ-003、REQ-004 / ui-design.md SCR-002 | `src/features/movie-management/frontend/src/views/` | 4h | 必須項目の検証、コーデック表示、H.265 の警告と保存不可／作品（なし・既存・新規作成）とジャンルを選べる／進捗表示の順序が仕様どおりで、実行中は操作が無効になる／失敗時に「登録中」の動画が残る旨を表示する／成功で動画一覧へ進む |
| T-031 | 動画一覧画面 SCR-001（続きから視聴パネルを含む） | REQ-005、REQ-015 / ui-design.md SCR-001 | `src/features/movie-management/frontend/src/views/` | 4h | 検索・ジャンル・作品・状態の絞り込みと並び替えが動き、既定が仕様どおり／動画カードのサムネイル（無いときは「画像なし」）・進捗バー・視聴完了・状態ラベルが出る／続きから視聴の 2 枚のカードから、それぞれ再生画面へ進める／スマートフォンで絞り込みが開閉式／スマートフォンで続きから視聴パネルが既定で非表示で、「続きから」ボタンで表示・非表示を切り替えられる（情報が無いときはボタンも出ない。PC では常時表示）／読込中・空・エラーの表示がある |
| T-032 | 動画編集画面 SCR-004 | REQ-006、REQ-007、REQ-008 / ui-design.md SCR-004 | `src/features/movie-management/frontend/src/views/` | 4h | 情報の編集と保存、話数重複のエラー表示／ファイルの差し替え（確認ダイアログ、H.265 の警告、進捗、失敗時の表示）／削除（確認ダイアログ）／成功時の遷移が仕様どおり |
| T-033 | 再生の部品: `composables/useVideoPlayer.ts`（開始・再開位置・位置の保存（一時停止・位置の移動の完了・画面離脱・10 秒ごと）・次の動画・再生終了時の遷移）、`useControlsAutoHide.ts`（3 秒）、`useFullscreen.ts`、再生ステージのコンポーネント（動画要素、開始ボタン、操作部、状態表示） | REQ-011、REQ-012、REQ-013 / design.md 動画のアップロードと再生、ui-design.md SCR-003 | `src/features/movie-management/frontend/src/composables/`、`src/components/` | 4h | 動画要素が配信 URL を直接指定して再生でき、シークで途中から再生できる／位置の保存が上記の契機で送信され、失敗しても再生が止まらない／操作部が 3 秒で隠れ、一時停止中と操作中は隠れない／全画面の入切ができる／デコード・取得の失敗、H.265 が原因と考えられる場合のメッセージが出る |
| T-034 | 動画再生画面 SCR-003 | REQ-011〜013 / ui-design.md SCR-003 | `src/features/movie-management/frontend/src/views/` | 3h | 前回位置があるとき「続きから再生」「最初から再生」を選べる／「次の動画」と、再生終了時の次の動画への自動遷移（次が無ければ視聴完了で停止し「最初から再生」を出す）／再生できない状態の動画は理由を表示する |
| T-035 | 視聴履歴画面 SCR-005 | REQ-014 / ui-design.md SCR-005 | `src/features/movie-management/frontend/src/views/` | 1.5h | 一覧・ページ送り・行から再生画面への遷移／読込中・空・エラーの表示がある |
| T-036 | プレイリスト一覧画面 SCR-009 | REQ-016 / ui-design.md SCR-009 | `src/features/movie-management/frontend/src/views/` | 2h | 名前・説明・件数・「再生」・編集が並び、動画が 0 件のときは「再生」が無効／作成フォーム（モーダル）で作成でき、成功で編集画面へ進む |
| T-037 | プレイリスト編集画面 SCR-010 | REQ-016 / ui-design.md SCR-010 | `src/features/movie-management/frontend/src/views/` | 4h | 名前・説明の編集、動画の並びの上へ・下へ・外す、動画の検索と追加（同じ動画の複数回追加を含む）、保存で名前・説明と並びをまとめて更新／削除（確認ダイアログ）／PC で並びと追加が左右、スマートフォンで追加が開閉式 |
| T-038 | プレイリスト再生: `composables/usePlaylistPlayer.ts`（`useVideoPlayer` の処理を共有した、開始・前後移動・再生終了時の遷移・位置の保存）、プレイリスト再生画面 SCR-011 | REQ-012、REQ-015、REQ-017 / ui-design.md SCR-011 | `src/features/movie-management/frontend/src/composables/`、`src/views/` | 4h | 続きから／最初から、前の動画・次の動画（無いときは無効）、再生終了で次を先頭から再生／再生できない動画の項目で理由を表示し前後へ移動できる／空のプレイリストで案内と編集への導線が出る／位置の保存がプレイリスト用の API で送信される |

### F. 仕上げ

| No | タスク | 対応する要件/設計 | 実装パス | 所要時間 | 完了条件 |
|----|--------|--------------------|----------|----------|----------|
| T-039 | 画面幅の確認と調整: 全画面を Wide（1024px 以上）と Compact（400px 前後）で確認し、はみ出し・長い文字列・0 件・大量件数を直す | REQ-005 / ui-design.md レイアウトの違い、`rules/31-web-app-responsive-layout-spec.md` | `src/features/movie-management/frontend/src/` | 3h | 全画面で横スクロールが出ない／ページ全体がスクロールしない／タップ領域が 44px 以上／フォーカスの表示がある／ui-design.md の PC・スマートフォンの配置の表のとおりになる |
| T-040 | デプロイ資料: `frontend/nginx.example.conf`（公開 URL `/portal_movie_management/`、API を同一オリジンにする場合の proxy、チャンクのために本文の上限 8 MB 以上、動画配信のバッファリングなし）、`src/features/movie-management/Readme.txt`（初回の準備・起動・DDL 適用） | REQ-011 / design.md デプロイ上の考慮、`rules/17-nginx-deploy.md` | `src/features/movie-management/frontend/nginx.example.conf`、`src/features/movie-management/Readme.txt` | 1.5h | nginx の設定例が `rules/17-nginx-deploy.md` に沿っている（`rewrite` は `last`、`try_files` と `break` を同じ location に置かない）／Readme の手順どおりに、バックエンドとフロントエンドを起動できる |
| T-041 | 結合確認: 実際の MP4（4 MB を超えるもの、複数 100 MB のもの）で、登録・再生・シーク・位置の保存・差し替え・削除、プレイリスト、続きから視聴を通しで確認。移行を、実データに近い移行元でドライランと本実行し、再実行も確認 | REQ-001〜023 / requirements.md 全受け入れ条件 | `src/features/movie-management/` | 3h | requirements.md の受け入れ条件を一通り確認し、未達があれば一覧にして報告する／PC のブラウザとスマートフォンのブラウザ（可能なら iPhone の Safari）で再生できる／移行で動画のバイト列が一致し、移行後の画面で再生できる |

## 実施順

1. 基盤: T-001 → T-002 → T-003 → T-004
2. バックエンド API: T-005、T-006（独立）→ T-007 → T-008、T-009 → T-010、T-011 → T-012 → T-013 → T-014 → T-015
3. テスト: T-016（T-003〜006 の後）、T-017（T-007〜011 の後）、T-018（T-012〜014 の後）。各 API の実装と並行して進めてよい。
4. 移行: T-019（T-002 の後。バックエンド API とは独立）→ T-020 → T-021 → T-022 → T-023
5. フロントエンド: T-024 → T-025、T-026 → T-027、T-028、T-029 → T-030、T-031、T-032（それぞれ、対応するバックエンド API の後）→ T-033 → T-034 → T-035 → T-036 → T-037 → T-038
6. 仕上げ: T-039、T-040 → T-041

合計の見積もり: 約 116 時間（バックエンド 43h、テスト 10h、移行 15h、フロントエンド 45h、仕上げ 7.5h ほか）。

## 要件とタスクの対応

| 要件 | タスク |
|------|--------|
| REQ-001 | T-003、T-016、T-024、T-025 |
| REQ-002 | T-005〜T-008、T-010、T-011、T-016、T-017 |
| REQ-003 | T-007、T-009、T-017、T-029、T-030 |
| REQ-004 | T-011、T-017、T-029、T-030 |
| REQ-005 | T-008、T-017、T-025、T-031 |
| REQ-006 | T-007、T-017、T-032 |
| REQ-007 | T-009、T-017、T-029、T-032 |
| REQ-008 | T-007、T-017、T-032 |
| REQ-009 | T-006、T-016、T-028 |
| REQ-010 | T-002、T-005、T-016、T-027 |
| REQ-011 | T-010、T-012、T-017、T-018、T-033、T-034 |
| REQ-012 | T-012、T-014、T-018、T-033、T-038 |
| REQ-013 | T-012、T-018、T-033、T-034 |
| REQ-014 | T-012、T-018、T-035 |
| REQ-015 | T-012、T-014、T-018、T-031、T-038 |
| REQ-016 | T-013、T-018、T-036、T-037 |
| REQ-017 | T-014、T-018、T-038 |
| REQ-018 | T-001、T-004、T-015 |
| REQ-019 | T-019、T-022 |
| REQ-020 | T-020、T-021、T-022 |
| REQ-021 | T-019、T-022 |
| REQ-022 | T-020、T-021、T-022 |
| REQ-023 | T-019、T-022、T-023 |
| 横断（画面幅・デプロイ・結合確認） | T-039、T-040、T-041 |

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 22:16 | 未承認 | 初版 |
| 2026-09-20 22:20 | 承認済み | 初版を承認 |
| 2026-09-21 06:15 | 未承認 | 実装との差異を解消（再開位置が動画の末尾のときは先頭から再生する、作品内順序が同じ動画は話数・識別子の順で前後を決める） |
| 2026-09-21 06:33 | 承認済み | 実装との差異の解消（末尾位置からの再開、作品内順序が同じ動画の並び）を承認 |
| 2026-09-26 14:59 | 未承認 | T-031 の完了条件に、スマートフォンでの続きから視聴パネルの開閉（既定は非表示）を追加（ui-design.md SCR-001 の改訂に伴う） |
| 2026-09-26 15:00 | 承認済み | T-031 の完了条件の追加（スマートフォンでの続きから視聴パネルの開閉）を承認 |
