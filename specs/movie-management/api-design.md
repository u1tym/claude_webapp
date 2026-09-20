# movie-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。移行プログラム（REQ-019〜023）はコマンドラインで動くため、API は持たない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_MOVIE_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）。以降のパスは、ベース URL からの相対パス。

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。動画（`/videos/{id}/stream`）とサムネイル（`/videos/{id}/thumbnail`）は、ブラウザの動画要素・画像要素が Cookie を自動で送るため、URL にトークンを付けない。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `movie-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

すべてのデータは、ログイン中ユーザ本人のものだけが対象である。他ユーザの行は、存在しないものとして扱う（404）。ただし、全利用者共通のジャンルは全員が参照できる。

### データ形式

- 要求・応答は JSON（UTF-8）。動画のアップロード（チャンク・サムネイル）は `multipart/form-data`。動画の配信とサムネイルの取得は、バイナリ。
- 日時は ISO 8601（オフセット付き。例 `2026-09-20T13:00:00+09:00`）。
- 時間は、すべてミリ秒の整数（`_ms`）。
- 識別子は整数。応答の対象そのものの識別子は `id`、他の対象への参照は `series_id` `video_id` などとする。
- 文字列の必須項目は、前後の空白を除いた結果が空のときは入力不正とする。

### ページ分け

一覧（動画・作品・プレイリスト・視聴履歴）は、次のクエリを受け付ける。

| 項目 | 型 | 既定 | 説明 |
|------|----|------|------|
| `page` | integer | 1 | ページ番号（1 以上） |
| `per_page` | integer | 20 | 1 ページの件数（1〜100） |

応答は、`items`（配列）と、次の `pagination` を持つ。

```json
{
  "items": [],
  "pagination": { "page": 1, "per_page": 20, "total_count": 0, "total_pages": 0 }
}
```

`total_pages` は、`total_count` が 0 のとき 0、それ以外は `ceil(total_count / per_page)`。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正（型・範囲・必須・文字数） | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 競合（重複） | 409、本文の `detail` は各エンドポイントに示す文言 |
| 処理できない状態 | 422、本文の `detail` は各エンドポイントに示す文言 |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表と各エンドポイントに示す文言だけを使う。以降の「エラー」の表は、共通のうち 401・403・500 を省き、各エンドポイント固有のものと、400・404 の条件だけを書く。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/genres` | 要 | REQ-010 |
| POST | `/genres` | 要 | REQ-010 |
| GET | `/series` | 要 | REQ-009 |
| POST | `/series` | 要 | REQ-009 |
| GET | `/series/{series_id}` | 要 | REQ-009 |
| GET | `/videos` | 要 | REQ-005 |
| POST | `/videos` | 要 | REQ-003 |
| GET | `/videos/{video_id}` | 要 | REQ-005、REQ-006、REQ-011 |
| PATCH | `/videos/{video_id}` | 要 | REQ-006 |
| DELETE | `/videos/{video_id}` | 要 | REQ-008 |
| POST | `/videos/{video_id}/chunks` | 要 | REQ-003、REQ-007 |
| POST | `/videos/{video_id}/complete` | 要 | REQ-003、REQ-007 |
| POST | `/videos/{video_id}/replace` | 要 | REQ-007 |
| GET | `/videos/{video_id}/stream` | 要 | REQ-011 |
| GET | `/videos/{video_id}/thumbnail` | 要 | REQ-004 |
| PUT | `/videos/{video_id}/thumbnail` | 要 | REQ-004 |
| POST | `/videos/{video_id}/playback/start` | 要 | REQ-011 |
| PUT | `/videos/{video_id}/playback/state` | 要 | REQ-012 |
| GET | `/videos/{video_id}/next` | 要 | REQ-013 |
| GET | `/playback/history` | 要 | REQ-014 |
| GET | `/playback/last` | 要 | REQ-015 |
| GET | `/playlists` | 要 | REQ-016 |
| POST | `/playlists` | 要 | REQ-016 |
| GET | `/playlists/{playlist_id}` | 要 | REQ-016 |
| PATCH | `/playlists/{playlist_id}` | 要 | REQ-016 |
| DELETE | `/playlists/{playlist_id}` | 要 | REQ-016 |
| PUT | `/playlists/{playlist_id}/items` | 要 | REQ-016 |
| POST | `/playlists/{playlist_id}/playback/start` | 要 | REQ-017 |
| GET | `/playlists/{playlist_id}/items/{item_id}/next` | 要 | REQ-017 |
| GET | `/playlists/{playlist_id}/items/{item_id}/prev` | 要 | REQ-017 |
| PUT | `/playlists/{playlist_id}/items/{item_id}/playback/state` | 要 | REQ-012、REQ-015、REQ-017 |

`/playback/history` と `/playback/last` は、`/videos/{video_id}/...` とは別のパスであり、競合しない。

## 共通のオブジェクト

### Genre

```json
{ "id": 1, "name": "洋画", "sort_order": 1, "is_system": true }
```

`is_system` は、全利用者共通のジャンルなら true。

### VideoSummary（動画一覧の要素）

```json
{
  "id": 100,
  "title": "第1話 はじまり",
  "description": "説明",
  "series_id": 10,
  "series_title": "サンプル作品",
  "episode_number": 1,
  "episode_title": "はじまり",
  "sort_order": 1,
  "duration_ms": 3600000,
  "mime_type": "video/mp4",
  "file_size_bytes": 524288000,
  "status": "ready",
  "genres": [{ "id": 3, "name": "アニメ" }],
  "has_thumbnail": true,
  "position_ms": 120000,
  "completed": false,
  "created_at": "2026-09-20T13:00:00+09:00",
  "updated_at": "2026-09-20T13:00:00+09:00"
}
```

| 項目 | 説明 |
|------|------|
| `status` | `uploading`（登録中）／`ready`（再生可能）／`error`（エラー） |
| `series_id` `series_title` `episode_number` `episode_title` `description` | 無いときは null |
| `position_ms` | 前回の再生位置。一度も再生していなければ null |
| `completed` | 視聴完了か。一度も再生していなければ false |

### VideoDetail

`VideoSummary` に、次を加えたもの。

```json
{ "chunk_count": 720, "play_count": 3, "last_played_at": "2026-09-20T15:30:00+09:00" }
```

`play_count` は、一度も再生していなければ 0。`last_played_at` は、一度も再生していなければ null。

### ChunkMeta

```json
{ "chunk_index": 24, "start_time_ms": 120000, "end_time_ms": 125000, "byte_length": 4194304 }
```

### Pagination

「ページ分け」の節のとおり。

## エンドポイント詳細

### GET `/settings`

- 認証: 不要

要求: なし

応答: 200

```json
{
  "login_url": "string",
  "menu_url": "string",
  "icon_system": "string",
  "icon_back": "string"
}
```

`icon_*` は data URL。未ログイン時の誘導先（`login_url`）と、ヘッダの「戻る」（`menu_url`）に使う。`public.system_settings` から取得する（`portal` が管理するデータを読むだけで、本機能は変更しない）。

エラー:

| 状況 | 応答 |
|------|------|
| 必須キーが欠けている | 500 |

### GET `/genres`

対応 REQ: REQ-010

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 1, "name": "洋画", "sort_order": 1, "is_system": true },
    { "id": 8, "name": "邦画名作", "sort_order": 10, "is_system": false }
  ]
}
```

処理概要: 全利用者共通のジャンルと、本人の独自ジャンルを、表示順（`sort_order` 昇順、`id` 昇順）で返す。ページ分けしない。

エラー: 共通エラーのみ。

### POST `/genres`

対応 REQ: REQ-010

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | 1〜100 文字（前後の空白を除く） |
| `sort_order` | integer | 任意 | 0 以上。省略時は 0 |

応答: 201（`Genre`。`is_system` は false）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ・101 文字以上、`sort_order` が負 | 400 |
| 本人の独自ジャンルに同名がある | 409、`{ "detail": "同じ名前のジャンルがあります" }` |

処理概要: 本人の独自ジャンルとして登録する。共通ジャンルと同じ名前の独自ジャンルは、登録できる（共通ジャンルと独自ジャンルは別に一意）。

### GET `/series`

対応 REQ: REQ-009

要求（クエリ）: `page`、`per_page`、`q`（string、任意。作品のタイトルの部分一致。大文字小文字を区別しない）

応答: 200

```json
{
  "items": [
    {
      "id": 10,
      "title": "サンプル作品",
      "description": "説明",
      "created_at": "2026-09-20T13:00:00+09:00",
      "updated_at": "2026-09-20T13:00:00+09:00"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1 }
}
```

処理概要: 本人の作品を、登録日時の降順（同じなら `id` の降順）で返す。`description` は無いとき null。

エラー: 共通エラーのみ（範囲外の `page` `per_page` は 400）。

### POST `/series`

対応 REQ: REQ-009

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `title` | string | 必須 | 1〜500 文字（前後の空白を除く） |
| `description` | string | 任意 | 説明 |

応答: 201（`GET /series` の `items` の要素と同じ形式）

エラー:

| 状況 | 応答 |
|------|------|
| `title` が空・空白のみ・501 文字以上 | 400 |

### GET `/series/{series_id}`

対応 REQ: REQ-009

要求: なし

応答: 200

```json
{
  "id": 10,
  "title": "サンプル作品",
  "description": "説明",
  "videos": [
    {
      "id": 100,
      "title": "第1話 はじまり",
      "episode_number": 1,
      "episode_title": "はじまり",
      "sort_order": 1,
      "duration_ms": 3600000,
      "status": "ready"
    }
  ],
  "created_at": "2026-09-20T13:00:00+09:00",
  "updated_at": "2026-09-20T13:00:00+09:00"
}
```

処理概要: 作品の情報と、その作品に属する本人の動画を、作品内順序の昇順、同じなら話数の昇順（話数が無いものは後）で返す。全状態の動画を含む。

エラー:

| 状況 | 応答 |
|------|------|
| 作品が存在しない、または他ユーザのもの | 404 |

### GET `/videos`

対応 REQ: REQ-005

要求（クエリ）:

| 項目 | 型 | 既定 | 説明 |
|------|----|------|------|
| `page` `per_page` | integer | 1 / 20 | ページ分け |
| `genre_id` | integer | - | このジャンルが付いた動画だけ |
| `series_id` | integer | - | この作品の動画だけ |
| `status` | string | `ready` | `ready` / `uploading` / `error` / `all` |
| `q` | string | - | タイトルまたは話タイトルの部分一致（大文字小文字を区別しない） |
| `sort` | string | `created_at` | `created_at`（登録日時）/ `title` / `last_played_at`（最終再生日時） |
| `order` | string | `desc` | `asc` / `desc` |

応答: 200（`VideoSummary` の `items` と `pagination`）

処理概要: 本人の動画を、条件で絞り込み、並べて返す。`sort=last_played_at` のとき、一度も再生していない動画は、昇順・降順のどちらでも末尾。同じ値の並びは `id` の降順で定める。動画ファイルのデータは含めない。

エラー:

| 状況 | 応答 |
|------|------|
| `status` `sort` `order` が上記以外、`page` `per_page` が範囲外 | 400 |

### POST `/videos`

対応 REQ: REQ-003

動画の登録の第 1 段階。動画情報を「登録中」で作成する。動画ファイルは、`POST /videos/{video_id}/chunks` で送る。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `title` | string | 必須 | 1〜500 文字（前後の空白を除く） |
| `description` | string | 任意 | 説明 |
| `series_id` | integer | 任意 | 所属する作品。本人の作品 |
| `episode_number` | integer | 任意 | 1 以上 |
| `episode_title` | string | 任意 | 500 文字以内 |
| `sort_order` | integer | 任意 | 0 以上。省略時は 0 |
| `duration_ms` | integer | 必須 | 1〜14,400,000 |
| `mime_type` | string | 任意 | 省略時は `video/mp4` |
| `genre_ids` | integer[] | 任意 | ジャンルの識別子。共通ジャンルまたは本人の独自ジャンル |

応答: 201

```json
{
  "id": 100,
  "status": "uploading",
  "title": "第1話 はじまり",
  "chunk_count": 0,
  "created_at": "2026-09-20T13:00:00+09:00"
}
```

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、文字数・範囲の不正、`genre_ids` の重複 | 400 |
| `series_id` の作品が存在しない、または他ユーザのもの。`genre_ids` に、存在しない、または他ユーザの独自ジャンルがある | 404 |
| 同一作品内で `episode_number` が重複する | 409、`{ "detail": "話数が重複しています" }` |

### GET `/videos/{video_id}`

対応 REQ: REQ-005、REQ-006、REQ-011

要求: なし

応答: 200（`VideoDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| 動画が存在しない、または他ユーザのもの | 404 |

### PATCH `/videos/{video_id}`

対応 REQ: REQ-006

動画情報の編集。指定した項目だけを更新する（指定しない項目は変えない）。`series_id` `episode_number` `episode_title` `description` は、null を指定して値を消せる。

要求（JSON。すべて任意）:

| 項目 | 型 | 説明 |
|------|----|------|
| `title` | string | 1〜500 文字（前後の空白を除く） |
| `description` | string \| null | 説明 |
| `series_id` | integer \| null | 所属する作品（null で単発動画にする） |
| `episode_number` | integer \| null | 1 以上 |
| `episode_title` | string \| null | 500 文字以内 |
| `sort_order` | integer | 0 以上 |
| `genre_ids` | integer[] | 指定した内容で全置換。空配列ですべて外す |

`duration_ms`・`mime_type`・動画ファイルは、この API では変更できない（指定しても無視せず、400 とする）。

応答: 200（更新後の `VideoDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| 空のボディ、文字数・範囲の不正、変更できない項目の指定 | 400 |
| 動画が存在しない、または他ユーザのもの。`series_id` の作品、`genre_ids` のジャンルが存在しない、または他ユーザのもの | 404 |
| 変更後、同一作品内で `episode_number` が重複する | 409、`{ "detail": "話数が重複しています" }` |

### DELETE `/videos/{video_id}`

対応 REQ: REQ-008

処理概要: 動画を物理削除する。動画ファイル、サムネイル、ジャンルとの関連、再生状態、プレイリストの項目も削除する。続きから視聴の参照は解除する。状態が「登録中」「エラー」の動画も削除できる。

要求: なし

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| 動画が存在しない、または他ユーザのもの | 404 |

### POST `/videos/{video_id}/chunks`

対応 REQ: REQ-003、REQ-007

動画の登録の第 2 段階。動画ファイルの断片（チャンク）を 1 つ登録する。

要求: `multipart/form-data`

| パート | 型 | 必須 | 説明 |
|--------|----|----|------|
| `chunk_index` | integer | 必須 | チャンクの連番（0 以上。先頭が 0） |
| `start_time_ms` | integer | 必須 | このチャンクに対応する再生時間の開始（0 以上） |
| `end_time_ms` | integer | 必須 | 同、終了（`start_time_ms` より大きい） |
| `data` | file | 必須 | 断片のデータ。1 バイト以上 8 MiB 以下 |

応答: 201

```json
{ "video_id": 100, "chunk_index": 12, "byte_length": 4194304, "uploaded_chunks": 13 }
```

エラー:

| 状況 | 応答 |
|------|------|
| 必須のパートが無い、範囲の不正、`data` が空または 8 MiB を超える | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |
| 同じ `chunk_index` が登録済み | 409、`{ "detail": "同じチャンクが登録済みです" }` |
| 動画の状態が「登録中」でない | 422、`{ "detail": "登録中の動画ではありません" }` |

処理概要: 動画が本人のもので「登録中」であることを確認し、チャンクを保管する。動画のチャンク数とファイルサイズの合計を、同時に更新する。

### POST `/videos/{video_id}/complete`

対応 REQ: REQ-003、REQ-007

動画の登録の第 3 段階。全チャンクの登録後に呼び、再生できる状態にする。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `duration_ms` | integer | 必須 | 確定した総再生時間。1〜14,400,000 |
| `chunk_count` | integer | 必須 | 登録したチャンクの総数（1 以上。整合の確認に使う） |

応答: 200

```json
{
  "id": 100,
  "status": "ready",
  "duration_ms": 3600000,
  "chunk_count": 720,
  "file_size_bytes": 524288000
}
```

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、範囲の不正 | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |
| 動画の状態が「登録中」でない | 422、`{ "detail": "登録中の動画ではありません" }` |
| 登録済みのチャンク数が、0、または `chunk_count` と一致しない | 422、`{ "detail": "チャンク数が一致しません" }` |

処理概要: 登録済みのチャンク数を確認し、再生時間を確定して、状態を「再生可能」にする。

### POST `/videos/{video_id}/replace`

対応 REQ: REQ-007

動画ファイルの差し替えの開始。現在のファイルを削除し、動画を「登録中」に戻す。以降は、`POST /videos/{video_id}/chunks` と `POST /videos/{video_id}/complete` で、新しいファイルを登録する。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `duration_ms` | integer | 必須 | 新しいファイルの総再生時間。1〜14,400,000 |
| `mime_type` | string | 任意 | 新しいファイルの形式。省略時は `video/mp4` |

応答: 200

```json
{ "id": 100, "status": "uploading", "chunk_count": 0 }
```

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、範囲の不正 | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |

処理概要: 既存のチャンクを削除し、チャンク数とファイルサイズの合計を 0、再生時間とファイル形式を要求の値にして、状態を「登録中」にする。本人の再生位置は 0、視聴完了は false にする。動画情報（タイトル・作品・ジャンルなど）とサムネイルは変えない。

### GET `/videos/{video_id}/stream`

対応 REQ: REQ-011

動画ファイルを配信する。ブラウザの動画要素が直接呼ぶ。範囲指定（Range）に対応する。

要求:

| ヘッダ | 必須 | 説明 |
|--------|------|------|
| `Range` | 任意 | `bytes=<開始>-<終了>`、`bytes=<開始>-`、`bytes=-<末尾からのバイト数>` のいずれか 1 つ。複数の範囲は指定できない |

応答:

| 条件 | 応答 |
|------|------|
| `Range` なし | 200、動画ファイル全体 |
| `Range` あり | 206、指定範囲。`Content-Range: bytes <開始>-<終了>/<全体>` |

共通のヘッダ: `Content-Type`（動画の形式）、`Accept-Ranges: bytes`、`Content-Length`（本文のバイト数）、`Cache-Control: private`。本文は動画ファイルのバイト列（先頭のチャンクから積み上げた位置）。

エラー:

| 状況 | 応答 |
|------|------|
| `Range` の形式が不正、または複数の範囲 | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |
| 範囲の開始が動画の大きさ以上、または開始が終了より大きい | 416、`Content-Range: bytes */<全体>`、本文 `{ "detail": "指定の範囲は取得できません" }` |
| 動画の状態が「再生可能」でない | 422、`{ "detail": "再生できない動画です" }` |

処理概要: 範囲の終了が動画の大きさを超えるときは、動画の末尾までに丸める。要求の範囲にかかるチャンクだけを 1 つずつ取得して返す（`design.md`）。

### GET `/videos/{video_id}/thumbnail`

対応 REQ: REQ-004

要求: なし

応答: 200。`Content-Type` は登録時の画像の形式（通常 `image/jpeg`）、本文は画像のバイト列。`Cache-Control: private`。

エラー:

| 状況 | 応答 |
|------|------|
| 動画が存在しない、または他ユーザのもの。サムネイルが登録されていない | 404 |

### PUT `/videos/{video_id}/thumbnail`

対応 REQ: REQ-004

サムネイルを登録する。既にあるときは置き換える。

要求: `multipart/form-data`

| パート | 型 | 必須 | 説明 |
|--------|----|----|------|
| `data` | file | 必須 | 画像のバイト列。1 バイト以上 5 MiB 以下 |
| `mime_type` | string | 任意 | 省略時は `image/jpeg`。`image/` で始まる値だけ |
| `width` | integer | 任意 | 画像の幅（px。1 以上） |
| `height` | integer | 任意 | 画像の高さ（px。1 以上） |

応答: 200

```json
{ "video_id": 100, "mime_type": "image/jpeg", "width": 320, "height": 180 }
```

エラー:

| 状況 | 応答 |
|------|------|
| `data` が無い・空・5 MiB を超える、`mime_type` が画像でない、`width` `height` の不正 | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |

### POST `/videos/{video_id}/playback/start`

対応 REQ: REQ-011

再生の開始を記録し、再生に必要な情報を返す。動画のデータは、`GET /videos/{video_id}/stream` で取得する。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `resume` | boolean | 任意 | 既定は true。true は前回の再生位置から、false は先頭から |

応答: 200

```json
{
  "id": 100,
  "title": "第1話 はじまり",
  "duration_ms": 3600000,
  "mime_type": "video/mp4",
  "chunk_count": 720,
  "position_ms": 120000,
  "completed": false,
  "status": "ready",
  "start_chunk": { "chunk_index": 24, "start_time_ms": 120000, "end_time_ms": 125000, "byte_length": 4194304 }
}
```

`position_ms` は、開始する再生位置。`resume` が false のとき、または前回の位置が動画の長さ以上のとき（超えるとき、および末尾のとき）は 0。`start_chunk` は、その位置に対応するチャンクで、参考情報である（動画要素の再生には使わない）。

エラー:

| 状況 | 応答 |
|------|------|
| ボディの型の不正 | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |
| 動画の状態が「再生可能」でない | 422、`{ "detail": "再生できない動画です" }` |

処理概要: 再生回数を 1 増やし、最終再生日時を更新する。続きから視聴の「最後に単独で再生した動画」を、この動画と開始位置にする。

### PUT `/videos/{video_id}/playback/state`

対応 REQ: REQ-012

再生位置と視聴完了を保存する。一時停止・位置の移動の完了・画面を離れるとき・再生中の一定間隔に呼ぶ。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `position_ms` | integer | 必須 | 現在の再生位置。0 以上、動画の長さ以下 |
| `completed` | boolean | 任意 | 最後まで視聴したとき true。省略時は false |

応答: 200

```json
{ "video_id": 100, "position_ms": 125000, "completed": false, "last_played_at": "2026-09-20T13:05:00+09:00" }
```

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、`position_ms` が負または動画の長さを超える | 400 |
| 動画が存在しない、または他ユーザのもの | 404 |

処理概要: 本人・この動画の再生状態を更新する（無ければ作成する）。最終再生日時を更新する。続きから視聴の「最後に単独で再生した動画」の位置を、この値にする。再生回数は変えない。

### GET `/videos/{video_id}/next`

対応 REQ: REQ-013

要求: なし

応答: 200

```json
{
  "has_next": true,
  "video": {
    "id": 101,
    "title": "第2話 展開",
    "episode_number": 2,
    "sort_order": 2,
    "duration_ms": 3600000,
    "status": "ready"
  }
}
```

次の動画が無いときは、`{ "has_next": false, "video": null }`。

処理概要:

- 動画が作品に属するとき: 同一作品の、状態が「再生可能」の本人の動画のうち、作品内順序が現在より大きい最小のもの。作品内順序が同じ動画は、話数（無いものは後）、識別子の順で前後を決める（`GET /series/{series_id}` の並びと同じ）。
- 動画が作品に属さないとき: 作品に属さない、状態が「再生可能」の本人の動画のうち、登録日時が現在より新しい最も古いもの。

エラー:

| 状況 | 応答 |
|------|------|
| 動画が存在しない、または他ユーザのもの | 404 |

### GET `/playback/history`

対応 REQ: REQ-014

要求（クエリ）: `page`、`per_page`

応答: 200

```json
{
  "items": [
    {
      "video_id": 100,
      "title": "第1話 はじまり",
      "position_ms": 125000,
      "completed": false,
      "duration_ms": 3600000,
      "last_played_at": "2026-09-20T13:05:00+09:00"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1 }
}
```

処理概要: 本人の再生状態を、最終再生日時の降順（同じなら `video_id` の降順）で返す。

エラー: 共通エラーのみ（範囲外の `page` `per_page` は 400）。

### GET `/playback/last`

対応 REQ: REQ-015

要求: なし

応答: 200

```json
{
  "video": {
    "video_id": 100,
    "title": "第1話 はじまり",
    "duration_ms": 3600000,
    "position_ms": 125000,
    "updated_at": "2026-09-20T13:05:00+09:00"
  },
  "playlist": {
    "playlist_id": 5,
    "playlist_name": "お気に入り",
    "item_id": 42,
    "video_id": 101,
    "video_title": "第2話 展開",
    "duration_ms": 3600000,
    "position_ms": 60000,
    "updated_at": "2026-09-20T12:00:00+09:00"
  }
}
```

`video` と `playlist` は、それぞれ、示すものが無いとき null。

処理概要:

- `video`: 続きから視聴の「最後に単独で再生した動画」が、削除されておらず、状態が「再生可能」のとき。
- `playlist`: 続きから視聴の「最後に再生したプレイリスト」と項目が、削除されておらず、項目の動画の状態が「再生可能」のとき。

エラー: 共通エラーのみ。

### GET `/playlists`

対応 REQ: REQ-016

要求（クエリ）: `page`、`per_page`

応答: 200

```json
{
  "items": [
    {
      "id": 5,
      "name": "お気に入り",
      "description": "説明",
      "item_count": 3,
      "created_at": "2026-09-20T13:00:00+09:00",
      "updated_at": "2026-09-20T13:00:00+09:00"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1 }
}
```

処理概要: 本人のプレイリストを、更新日時の降順（同じなら `id` の降順）で返す。

エラー: 共通エラーのみ（範囲外の `page` `per_page` は 400）。

### POST `/playlists`

対応 REQ: REQ-016

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | 1〜500 文字（前後の空白を除く） |
| `description` | string | 任意 | 説明 |

応答: 201（`PlaylistDetail`。`items` は空）

```json
{
  "id": 5,
  "name": "お気に入り",
  "description": "説明",
  "items": [],
  "created_at": "2026-09-20T13:00:00+09:00",
  "updated_at": "2026-09-20T13:00:00+09:00"
}
```

エラー:

| 状況 | 応答 |
|------|------|
| `name` が空・空白のみ・501 文字以上 | 400 |

### GET `/playlists/{playlist_id}`

対応 REQ: REQ-016

要求: なし

応答: 200（`PlaylistDetail`）

```json
{
  "id": 5,
  "name": "お気に入り",
  "description": "説明",
  "items": [
    {
      "item_id": 42,
      "video_id": 100,
      "title": "第1話 はじまり",
      "duration_ms": 3600000,
      "status": "ready",
      "has_thumbnail": true,
      "sort_order": 0
    }
  ],
  "created_at": "2026-09-20T13:00:00+09:00",
  "updated_at": "2026-09-20T13:00:00+09:00"
}
```

`items` は `sort_order` の昇順。

エラー:

| 状況 | 応答 |
|------|------|
| プレイリストが存在しない、または他ユーザのもの | 404 |

### PATCH `/playlists/{playlist_id}`

対応 REQ: REQ-016

名前・説明の編集。指定した項目だけを更新する。

要求（JSON。すべて任意。1 つ以上）:

| 項目 | 型 | 説明 |
|------|----|------|
| `name` | string | 1〜500 文字（前後の空白を除く） |
| `description` | string \| null | 説明 |

応答: 200（更新後の `PlaylistDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| 空のボディ、`name` の不正 | 400 |
| プレイリストが存在しない、または他ユーザのもの | 404 |

処理概要: 更新日時を更新する。

### DELETE `/playlists/{playlist_id}`

対応 REQ: REQ-016

処理概要: プレイリストと、その項目を削除する。含まれていた動画は削除しない。続きから視聴の参照は解除する。

要求: なし

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| プレイリストが存在しない、または他ユーザのもの | 404 |

### PUT `/playlists/{playlist_id}/items`

対応 REQ: REQ-016

プレイリストに含める動画を、並びごと置き換える。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `items` | object[] | 必須 | 並び順に並べた項目。空配列も可 |
| `items[].video_id` | integer | 必須 | 動画の識別子。本人の動画。同じ動画を複数回指定してよい |

応答: 200（更新後の `PlaylistDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| `items` が無い、要素の不正 | 400 |
| プレイリストが存在しない、または他ユーザのもの。`video_id` の動画が存在しない、または他ユーザのもの | 404 |

処理概要: 既存の項目をすべて削除し、指定の順（0 始まりの `sort_order`）で項目を作り直す。1 つのトランザクションで行う。更新日時を更新する。項目が入れ替わるため、続きから視聴の「プレイリスト内の項目」の参照は解除される。

### POST `/playlists/{playlist_id}/playback/start`

対応 REQ: REQ-017

プレイリストの再生を開始する。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `resume` | boolean | 任意 | 既定は true。true は、そのプレイリストで最後に再生した項目と位置から（位置が動画の長さ以上のときは、その項目を先頭から）。false、または該当する項目が無いときは、先頭の項目を先頭から |

応答: 200（`PlaylistPlaybackItem`）

```json
{
  "playlist_id": 5,
  "item_id": 42,
  "video_id": 100,
  "title": "第1話 はじまり",
  "duration_ms": 3600000,
  "mime_type": "video/mp4",
  "status": "ready",
  "position_ms": 60000,
  "sort_order": 0,
  "has_next": true,
  "has_prev": false,
  "start_chunk": { "chunk_index": 12, "start_time_ms": 60000, "end_time_ms": 65000, "byte_length": 4194304 }
}
```

`status` が「再生可能」でない項目（動画が登録中・エラー）のときも、200 を返す。その場合、`start_chunk` は null、`position_ms` は 0。フロントは、その旨を表示し、前後の項目へ移動できる。動画の配信は、`GET /videos/{video_id}/stream` で行う。

エラー:

| 状況 | 応答 |
|------|------|
| ボディの型の不正 | 400 |
| プレイリストが存在しない、または他ユーザのもの | 404 |
| プレイリストに項目が無い | 422、`{ "detail": "プレイリストに動画がありません" }` |

処理概要: 開始する項目を、続きから視聴の「最後に再生したプレイリスト」の情報に反映する（プレイリスト、項目、位置）。動画の再生回数と最終再生日時は、単独再生と同じく更新する（再生できる項目のとき）。

### GET `/playlists/{playlist_id}/items/{item_id}/next`

対応 REQ: REQ-017

要求: なし

応答: 200

```json
{ "has_next": true, "item": { "...": "PlaylistPlaybackItem" } }
```

次の項目が無いときは、`{ "has_next": false, "item": null }`。`item` は `PlaylistPlaybackItem`（`position_ms` は 0）。

処理概要: 現在の項目より `sort_order` が大きい最小の項目を返し、続きから視聴の情報にする（位置は 0）。

エラー:

| 状況 | 応答 |
|------|------|
| プレイリストが存在しない、または他ユーザのもの。項目がそのプレイリストに無い | 404 |

### GET `/playlists/{playlist_id}/items/{item_id}/prev`

対応 REQ: REQ-017

要求: なし

応答: 200

```json
{ "has_prev": true, "item": { "...": "PlaylistPlaybackItem" } }
```

前の項目が無いときは、`{ "has_prev": false, "item": null }`。

処理概要: 現在の項目より `sort_order` が小さい最大の項目を返し、続きから視聴の情報にする（位置は 0）。

エラー:

| 状況 | 応答 |
|------|------|
| プレイリストが存在しない、または他ユーザのもの。項目がそのプレイリストに無い | 404 |

### PUT `/playlists/{playlist_id}/items/{item_id}/playback/state`

対応 REQ: REQ-012、REQ-015、REQ-017

プレイリスト再生中の再生位置と視聴完了を保存する。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `position_ms` | integer | 必須 | 現在の再生位置。0 以上、その項目の動画の長さ以下 |
| `completed` | boolean | 任意 | 最後まで視聴したとき true。省略時は false |

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、`position_ms` が負または動画の長さを超える | 400 |
| プレイリストが存在しない、または他ユーザのもの。項目がそのプレイリストに無い | 404 |

処理概要: 項目の動画について、本人の再生状態（位置・視聴完了・最終再生日時）を更新する（無ければ作成する。再生回数は変えない）。続きから視聴の「最後に再生したプレイリスト」の情報（プレイリスト、項目、位置）も更新する。「最後に単独で再生した動画」の情報は変えない。

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通事項の認証（401・403）、`GET /settings` を除く全エンドポイント |
| REQ-002 | 共通事項（本人のデータのみ、他ユーザは 404）。動画の配信・サムネイルの認証。`/genres` は共通ジャンルを全員に返すが変更はできない |
| REQ-003 | `POST /videos`、`POST /videos/{video_id}/chunks`、`POST /videos/{video_id}/complete`、`PUT /videos/{video_id}/thumbnail`、`POST /series`（作品の新規作成を伴う登録） |
| REQ-004 | `GET`・`PUT /videos/{video_id}/thumbnail`、`VideoSummary.has_thumbnail` |
| REQ-005 | `GET /videos`、`GET /videos/{video_id}`、`GET /genres`、`GET /series` |
| REQ-006 | `PATCH /videos/{video_id}` |
| REQ-007 | `POST /videos/{video_id}/replace`、`POST /videos/{video_id}/chunks`、`POST /videos/{video_id}/complete` |
| REQ-008 | `DELETE /videos/{video_id}` |
| REQ-009 | `GET`・`POST /series`、`GET /series/{series_id}` |
| REQ-010 | `GET`・`POST /genres` |
| REQ-011 | `GET /videos/{video_id}/stream`、`POST /videos/{video_id}/playback/start` |
| REQ-012 | `PUT /videos/{video_id}/playback/state`、`PUT /playlists/{playlist_id}/items/{item_id}/playback/state` |
| REQ-013 | `GET /videos/{video_id}/next` |
| REQ-014 | `GET /playback/history` |
| REQ-015 | `GET /playback/last`、各再生 API による続きから視聴の情報の更新 |
| REQ-016 | `/playlists` 系（一覧・作成・詳細・編集・削除）、`PUT /playlists/{playlist_id}/items` |
| REQ-017 | `POST /playlists/{playlist_id}/playback/start`、`GET .../items/{item_id}/next`・`prev`、`PUT .../items/{item_id}/playback/state` |
| REQ-018 | API 外（ログ）。失敗の本文は内部理由を含まない（共通エラー） |
| REQ-019〜023 | API 外（移行プログラム。コマンドライン） |

## 未決事項

- なし

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-20 22:11 | 未承認 | 初版 |
| 2026-09-20 22:13 | 承認済み | 初版を承認 |
| 2026-09-21 06:15 | 未承認 | 実装との差異を解消（再開位置が動画の末尾のときは先頭から再生する、作品内順序が同じ動画は話数・識別子の順で前後を決める） |
| 2026-09-21 06:33 | 承認済み | 実装との差異の解消（末尾位置からの再開、作品内順序が同じ動画の並び）を承認 |
