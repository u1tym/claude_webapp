# note-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。移行プログラム（REQ-015〜018）と PDF 出力（REQ-013。フロントで印刷用のレイアウトを組み立てる）は、専用の API を持たない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_NOTE_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）。以降のパスは、ベース URL からの相対パス。

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。画像・添付ファイルの取得（`<img>`・ダウンロードのリンク）も、ブラウザが Cookie を自動で送る（フロントと API は、Cookie が送られる関係にする）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `note-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

すべての対象は、ログイン中ユーザ本人のものだけである。他ユーザのフォルダ・ファイル・パーツ・過去世代・チェックリストは、存在しないものとして扱う（404）。他ユーザのフォルダを、親・移動先として指定したときも、存在しないものとして扱う（404）。

### データ形式

- 要求・応答は JSON（UTF-8）。ただし、画像・添付ファイルの取得（`GET /parts/{part_id}/content`、`GET /part-revisions/{revision_id}/content`）の応答は、ファイルの中身（バイナリ）。
- 日時は ISO 8601（オフセット付き。例 `2026-09-21T13:00:00+09:00`）。
- 識別子は整数。応答の対象そのものの識別子は `id`、他の対象への参照は `parent_id` などとする。
- 文字列の必須項目（フォルダ名・ファイルのタイトル・カテゴリ名）は、前後の空白を除いた結果が空のときは入力不正とする。応答には、前後の空白を除いた値を返す。
- 並び順（`sort_order`）は、応答に含めるが、要求では指定しない（末尾に付く。入れ替えの API で変える）。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正（型・必須・空白のみ） | 400、本文 `{ "detail": "入力が不正です" }`。各エンドポイントに示す 400 は、その文言を `detail` に用いる |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 状態・規則に合わない操作（重複、削除済みへの操作、自分の中への移動など） | 409、本文の `detail` は各エンドポイントに示す文言 |
| 画像・添付ファイルが大きすぎる | 413、本文 `{ "detail": "ファイルは 10 MB までです" }`（上限の値は `PART_MAX_BYTES`。文言の数値は上限に合わせる） |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表と各エンドポイントに示す文言だけを使う。以降の「エラー」の表は、共通のうち 401・403・500 を省き、各エンドポイント固有のものと、400・404・409 の条件だけを書く。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/items` | 要 | REQ-003、REQ-006 |
| POST | `/folders` | 要 | REQ-004 |
| PATCH | `/folders/{folder_id}` | 要 | REQ-004 |
| POST | `/folders/{folder_id}/move` | 要 | REQ-004 |
| POST | `/folders/swap-order` | 要 | REQ-004 |
| DELETE | `/folders/{folder_id}` | 要 | REQ-004 |
| POST | `/folders/{folder_id}/undelete` | 要 | REQ-006 |
| POST | `/files` | 要 | REQ-005 |
| GET | `/files/{file_id}` | 要 | REQ-007、REQ-006、REQ-013 |
| PATCH | `/files/{file_id}` | 要 | REQ-005 |
| POST | `/files/{file_id}/move` | 要 | REQ-005 |
| POST | `/files/swap-order` | 要 | REQ-005 |
| DELETE | `/files/{file_id}` | 要 | REQ-005 |
| POST | `/files/{file_id}/undelete` | 要 | REQ-006 |
| POST | `/files/{file_id}/parts` | 要 | REQ-008、REQ-009、REQ-011、REQ-012 |
| PATCH | `/parts/{part_id}` | 要 | REQ-008〜REQ-011 |
| DELETE | `/parts/{part_id}` | 要 | REQ-008 |
| POST | `/parts/{part_id}/undelete` | 要 | REQ-006 |
| POST | `/parts/swap-order` | 要 | REQ-008 |
| GET | `/parts/{part_id}/content` | 要 | REQ-007、REQ-009 |
| GET | `/part-revisions/{revision_id}/content` | 要 | REQ-010 |
| GET | `/checklists/{checklist_id}` | 要 | REQ-007、REQ-012 |
| PATCH | `/checklists/{checklist_id}` | 要 | REQ-012 |
| POST | `/checklists/{checklist_id}/categories` | 要 | REQ-012 |
| PATCH | `/checklists/{checklist_id}/categories/{category_id}` | 要 | REQ-012 |
| DELETE | `/checklists/{checklist_id}/categories/{category_id}` | 要 | REQ-012 |
| POST | `/checklists/{checklist_id}/categories/reorder` | 要 | REQ-012 |
| POST | `/checklists/{checklist_id}/items` | 要 | REQ-012 |
| PATCH | `/checklists/{checklist_id}/items/{item_id}` | 要 | REQ-012 |
| DELETE | `/checklists/{checklist_id}/items/{item_id}` | 要 | REQ-012 |
| POST | `/checklists/{checklist_id}/items/{item_id}/move` | 要 | REQ-012 |

## 共通のオブジェクト

### Folder（フォルダ）

```json
{ "id": 3, "parent_id": null, "name": "旅行", "sort_order": 1, "is_deleted": false, "ancestor_deleted": false }
```

`is_deleted` は、そのフォルダ自身が削除済みなら true。`ancestor_deleted` は、上位のフォルダのいずれかが削除済みなら true（自身の削除とは独立）。ルートフォルダの `ancestor_deleted` は常に false。

### File（ファイルの概要）

```json
{ "id": 8, "folder_id": 3, "title": "持ち物", "sort_order": 1, "is_deleted": false, "ancestor_deleted": false }
```

`ancestor_deleted` は、所属フォルダまたはその上位のいずれかが削除済みなら true。

### Marker（画像のマーカー）

```json
{ "id": "m1", "kind": "number", "x": 0.25, "y": 0.5, "text": "入口", "number": 1 }
```

| 項目 | 型 | 説明 |
|------|----|------|
| `id` | string | マーカーの識別子（1〜64 文字。1 つの画像の中で重複しない） |
| `kind` | string | `house`（家）または `number`（番号） |
| `x` `y` | number | 画像上の位置（0〜1。左上が 0） |
| `text` | string | 説明（空可） |
| `number` | integer | `kind` が `number` のときだけ必須（1 以上）。`house` には付けない |

### Part（パーツ）

```json
{
  "id": 21,
  "sort_order": 1,
  "type": "png",
  "is_deleted": false,
  "data": "",
  "byte_size": 20480,
  "filename": "map.png",
  "title": "地図",
  "markers": [ { "id": "m1", "kind": "house", "x": 0.1, "y": 0.2, "text": "宿" } ],
  "image_scale": 1.0,
  "checklist_id": null,
  "revisions": [
    { "id": 5, "revision_number": 2, "type": "png", "filename": "map_old.png", "byte_size": 18000, "created_at": "2026-09-21T13:00:00+09:00" }
  ]
}
```

| 項目 | 説明 |
|------|------|
| `type` | `text` `md` `tex` `url` `action` `checklist` `jpeg` `png` `binary` |
| `data` | テキスト・Markdown・TeX・URL の文字列、行動予定の JSON 文字列。画像・バイナリ・チェックリストは、空文字（中身は `GET /parts/{part_id}/content` で取得する） |
| `byte_size` | 画像・バイナリの展開後の大きさ（バイト）。それ以外は 0 |
| `filename` | ファイル名（画像・バイナリ）。それ以外は空 |
| `title` | 表示用のタイトル（画像）。それ以外は空 |
| `markers` | マーカーの配列（画像）。それ以外は空配列 |
| `image_scale` | 表示倍率（画像。1.0 = 100%、0.25〜4.0）。それ以外は 1.0 |
| `checklist_id` | チェックリストのパーツの、チェックリストの識別子。それ以外は null |
| `revisions` | 過去世代の一覧（世代番号の降順。中身は含まない）。画像・バイナリだけ。それ以外は空配列 |

### Checklist（チェックリストの状態）

```json
{
  "checklist_id": 4,
  "title": "買い物",
  "categories": [
    { "id": 10, "name": "", "is_unnamed": true, "items": [ { "id": 100, "title": "牛乳", "is_checked": false } ] },
    { "id": 11, "name": "日用品", "is_unnamed": false, "items": [] }
  ]
}
```

削除済みのカテゴリ・項目は含まない。`categories` は、無名カテゴリ（あれば）が先頭、続いて名前のあるカテゴリが表示順。各 `items` は表示順。

### 行動予定の本文（`type` が `action` のときの `data`）

JSON オブジェクトを文字列化したもの。

```json
{
  "points": [
    { "place": "東京駅", "time": "9:00" },
    { "place": "新宿", "arrive": "10:00", "depart": "10:30" },
    { "place": "渋谷", "time": "14:00" }
  ],
  "legs": [
    { "memo": "山手線", "note": "快速利用\n2 号車から乗車" },
    { "memo": "", "note": "" }
  ]
}
```

| 項目 | 説明 |
|------|------|
| `points` | 地点の配列（1 件以上）。各要素は `place`（文字列）と、`time` または `arrive`・`depart`（文字列、いずれも省略可） |
| `points[0]` | 1 番目の地点は、`place` と `time` だけ。`arrive` `depart` は付けない |
| `points[i]`（i ≥ 1） | `time` と、`arrive`・`depart` を、同時に付けない |
| `legs` | 経由メモの配列。要素は `memo`（1 行）、`note`（複数行。改行は `\n`）。どちらも省略可 |

検証と正規化（サーバ）:

- すべての文字列は、末尾の空白を除く（先頭・途中の空白は保つ）。
- 2 番目以降の地点で、すべての項目が空のものが、末尾に続くときは、取り除く。取り除いた地点の前の経由メモ（その地点への経由）も取り除く。
- 取り除いた後、`legs` の件数が、`points` の件数 − 1 と一致しないときは、入力不正。
- 地点の `place` `time` `arrive` `depart` と、経由メモの `memo` `note` の、どれか 1 件以上が空でないこと。
- 本文が JSON として読めない、構造が上と違う、`time` と `arrive`・`depart` が同時にある、のときは入力不正。

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

### GET `/items`

対応 REQ: REQ-003、REQ-006

指定したフォルダの、直下のフォルダとファイルを返す。

要求（クエリ）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `folder_id` | integer | 任意 | 対象のフォルダ。省略するとルート（ルートフォルダの一覧。ファイルは常に空） |
| `include_deleted` | boolean | 任意 | true なら削除済み（上位が削除済みを含む）も返す。既定 false |

応答: 200

```json
{
  "parent": { "id": 3, "name": "旅行", "is_deleted": false, "ancestor_deleted": false },
  "folders": [ { "id": 4, "parent_id": 3, "name": "国内", "sort_order": 1, "is_deleted": false, "ancestor_deleted": false } ],
  "files": [ { "id": 8, "folder_id": 3, "title": "持ち物", "sort_order": 1, "is_deleted": false, "ancestor_deleted": false } ]
}
```

- `parent`: 対象のフォルダ。`folder_id` を省略したときは null。
- `folders`・`files`: 並び順の昇順。`include_deleted` が false のときは、`is_deleted` または `ancestor_deleted` が true のものを含めない。

エラー:

| 状況 | 応答 |
|------|------|
| `folder_id` が整数でない | 400 |
| `folder_id` のフォルダが存在しない、または他ユーザのもの | 404 |

### POST `/folders`

対応 REQ: REQ-004

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `parent_id` | integer \| null | 必須 | 親のフォルダ。null はルート |
| `name` | string | 必須 | フォルダ名 |

応答: 201（`Folder`。並び順は、同じ親の中の末尾）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が無い、空・空白のみ | 400 |
| `parent_id` のフォルダが存在しない、または他ユーザのもの | 404 |
| `parent_id` のフォルダが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| 同じ親の中に、削除されていない同名のフォルダがある | 409、`{ "detail": "同じ名前があります" }` |

### PATCH `/folders/{folder_id}`

対応 REQ: REQ-004

名前を変更する。

要求（JSON）: `{ "name": "国内旅行" }`

応答: 200（`Folder`）

エラー:

| 状況 | 応答 |
|------|------|
| `name` が無い、空・空白のみ | 400 |
| フォルダが存在しない、または他ユーザのもの | 404 |
| フォルダが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| 同じ親の中に、削除されていない同名の（自身以外の）フォルダがある | 409、`{ "detail": "同じ名前があります" }` |

### POST `/folders/{folder_id}/move`

対応 REQ: REQ-004

フォルダを、別のフォルダの中、またはルートへ移動する。移動先の末尾に並ぶ。

要求（JSON）: `{ "new_parent_id": 5 }`（`null` はルート）

応答: 200（移動後の `Folder`）

エラー:

| 状況 | 応答 |
|------|------|
| `new_parent_id` が無い（null は可）、型の不正 | 400 |
| フォルダ、または `new_parent_id` のフォルダが、存在しない、または他ユーザのもの | 404 |
| フォルダ、または移動先が削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| 移動先が、自分自身、または自分の子孫 | 409、`{ "detail": "自分の中には移動できません" }` |
| 移動先が、現在の親と同じ | 409、`{ "detail": "現在の場所と同じです" }` |
| 移動先に、削除されていない同名のフォルダがある | 409、`{ "detail": "同じ名前があります" }` |

### POST `/folders/swap-order`

対応 REQ: REQ-004

同じ親の中の 2 つのフォルダの並び順を入れ替える。

要求（JSON）: `{ "folder_id_1": 4, "folder_id_2": 6 }`

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| 項目が無い、型の不正、2 つが同じ | 400 |
| いずれかが存在しない、または他ユーザのもの | 404 |
| 2 つの親が違う | 400、`{ "detail": "同じ場所の項目ではありません" }` |
| いずれかが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |

### DELETE `/folders/{folder_id}`

対応 REQ: REQ-004

フォルダを論理削除する。子孫のフォルダ・ファイル・パーツの行は変更しない。

要求: なし

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| フォルダが存在しない、または他ユーザのもの | 404 |
| フォルダが既に削除済み | 409、`{ "detail": "既に削除されています" }` |

### POST `/folders/{folder_id}/undelete`

対応 REQ: REQ-006

削除済みのフォルダを、削除解除する。並び順が、同じ親の中の他のフォルダと重なるときは、末尾に付け直す。子孫の行は変更しない。

要求: なし

応答: 200（`Folder`）

エラー:

| 状況 | 応答 |
|------|------|
| フォルダが存在しない、または他ユーザのもの | 404 |
| フォルダが削除済みでない | 409、`{ "detail": "削除されていません" }` |
| 同じ親の中に、削除されていない同名のフォルダがある | 409、`{ "detail": "同じ名前があります" }` |

### POST `/files`

対応 REQ: REQ-005

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `folder_id` | integer | 必須 | 所属するフォルダ（ルートの直下には作れない） |
| `title` | string | 必須 | ファイルのタイトル |

応答: 201（`File`。並び順は、同じフォルダの中の末尾）

エラー:

| 状況 | 応答 |
|------|------|
| `folder_id` `title` が無い、`title` が空・空白のみ | 400 |
| フォルダが存在しない、または他ユーザのもの | 404 |
| フォルダが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| 同じフォルダの中に、削除されていない同じタイトルのファイルがある | 409、`{ "detail": "同じタイトルがあります" }` |

### GET `/files/{file_id}`

対応 REQ: REQ-007、REQ-006、REQ-013

ファイルと、そのパーツを返す。削除済みのファイル（上位が削除済みを含む）も取得できる。

要求（クエリ）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `include_deleted_parts` | boolean | 任意 | true なら削除済みのパーツも返す。既定 false |

応答: 200

```json
{
  "id": 8,
  "folder": { "id": 3, "name": "旅行" },
  "title": "持ち物",
  "is_deleted": false,
  "ancestor_deleted": false,
  "parts": [ /* Part の配列（並び順の昇順） */ ]
}
```

エラー:

| 状況 | 応答 |
|------|------|
| ファイルが存在しない、または他ユーザのもの | 404 |

### PATCH `/files/{file_id}`

対応 REQ: REQ-005

タイトルを変更する。

要求（JSON）: `{ "title": "持ち物（改）" }`

応答: 200（`File`）

エラー:

| 状況 | 応答 |
|------|------|
| `title` が無い、空・空白のみ | 400 |
| ファイルが存在しない、または他ユーザのもの | 404 |
| ファイルが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| 同じフォルダの中に、削除されていない同じタイトルの（自身以外の）ファイルがある | 409、`{ "detail": "同じタイトルがあります" }` |

### POST `/files/{file_id}/move`

対応 REQ: REQ-005

ファイルを、別のフォルダの中へ移動する。移動先の末尾に並ぶ。

要求（JSON）: `{ "new_folder_id": 5 }`

応答: 200（移動後の `File`）

エラー:

| 状況 | 応答 |
|------|------|
| `new_folder_id` が無い、null、型の不正 | 400 |
| ファイル、または移動先のフォルダが、存在しない、または他ユーザのもの | 404 |
| ファイル、または移動先が削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| 移動先が、現在の所属フォルダと同じ | 409、`{ "detail": "現在の場所と同じです" }` |
| 移動先に、削除されていない同じタイトルのファイルがある | 409、`{ "detail": "同じタイトルがあります" }` |

### POST `/files/swap-order`

対応 REQ: REQ-005

同じフォルダの中の 2 つのファイルの並び順を入れ替える。

要求（JSON）: `{ "file_id_1": 8, "file_id_2": 9 }`

応答: 204（本文なし）

エラー: `POST /folders/swap-order` と同じ（対象がファイル。「2 つの親が違う」は、所属フォルダが違うとき）。

### DELETE `/files/{file_id}`

対応 REQ: REQ-005

ファイルを論理削除する。パーツの行は変更しない。

要求: なし

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| ファイルが存在しない、または他ユーザのもの | 404 |
| ファイルが既に削除済み | 409、`{ "detail": "既に削除されています" }` |

### POST `/files/{file_id}/undelete`

対応 REQ: REQ-006

削除済みのファイルを、削除解除する。並び順が重なるときは、末尾に付け直す。

要求: なし

応答: 200（`File`）

エラー:

| 状況 | 応答 |
|------|------|
| ファイルが存在しない、または他ユーザのもの | 404 |
| ファイルが削除済みでない | 409、`{ "detail": "削除されていません" }` |
| 同じフォルダの中に、削除されていない同じタイトルのファイルがある | 409、`{ "detail": "同じタイトルがあります" }` |

### POST `/files/{file_id}/parts`

対応 REQ: REQ-008、REQ-009、REQ-011、REQ-012

ファイルの末尾に、パーツを追加する。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `type` | string | 必須 | `text` `md` `tex` `url` `action` `checklist` `jpeg` `png` `binary` のいずれか |
| `data` | string | 種別による | テキスト・Markdown・TeX・URL は本文（空も可。省略時は空）。行動予定は JSON 文字列（必須）。画像・バイナリは Base64 の文字列（必須）。チェックリストは空（省略可） |
| `filename` | string | 画像・バイナリは必須 | ファイル名。前後の空白を除いた結果が空でない。それ以外の種別では無視する |
| `title` | string | 任意 | 表示用のタイトル。画像だけ有効（省略時は空）。それ以外では空にする |
| `markers` | Marker[] | 任意 | 画像だけ有効（省略時は空配列）。それ以外では空にする |
| `image_scale` | number | 任意 | 画像だけ有効（省略時は 1.0）。0.25〜4.0。それ以外では 1.0 にする |

応答: 201（`Part`。チェックリストは、空のチェックリストが作られ、`checklist_id` が入る）

エラー:

| 状況 | 応答 |
|------|------|
| `type` が上記以外、必須の項目が無い、型の不正 | 400 |
| 行動予定の本文が、規則（「行動予定の本文」の節）に合わない | 400、`{ "detail": "行動予定の内容が正しくありません" }` |
| 画像・バイナリの `data` が Base64 として読めない、または空 | 400、`{ "detail": "ファイルの内容が正しくありません" }` |
| 画像・バイナリの `filename` が、空・空白のみ | 400、`{ "detail": "ファイル名を入力してください" }` |
| JPEG・PNG の中身が、その形式（先頭のバイト列）でない | 400、`{ "detail": "画像の形式が正しくありません" }` |
| `image_scale` が範囲外 | 400、`{ "detail": "表示倍率は 25〜400% の範囲で指定してください" }` |
| マーカーが規則に合わない（位置が 0〜1 の外、`house` に `number` がある、`number` に番号が無い・1 未満、`id` の重複、`kind` が上記以外） | 400、`{ "detail": "マーカーが正しくありません" }` |
| マーカーが 100 個を超える | 400、`{ "detail": "マーカーは 100 個までです" }` |
| 画像・バイナリの展開後の大きさが上限を超える | 413 |
| ファイルが存在しない、または他ユーザのもの | 404 |
| ファイルが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |

### PATCH `/parts/{part_id}`

対応 REQ: REQ-008〜REQ-011

パーツの内容を更新する。要求の項目のうち、指定した項目だけを更新し、省略した項目は現在の値を保つ。

要求（JSON。すべて任意）:

| 項目 | 型 | 説明 |
|------|----|------|
| `type` | string | 種別を変える。`checklist` へ、`checklist` から変えることはできない |
| `data` | string | 本文（`POST /files/{file_id}/parts` と同じ規則）。画像・バイナリは、差し替えるときだけ指定する |
| `filename` | string | ファイル名（画像・バイナリ） |
| `title` | string | 表示用のタイトル（画像） |
| `markers` | Marker[] | マーカー（画像） |
| `image_scale` | number | 表示倍率（画像） |

種別の変更と `data`:

- 種別を、次の 3 つの組の、別の組へ変えるときは、`data` を必ず指定する（指定がなければ 400）: 組 A（`text` `md` `tex` `url`）、組 B（`action`）、組 C（`jpeg` `png` `binary`）。同じ組の中で変えるときは、`data` は省略できる（現在の本文を引き継ぐ）。
- 組 C の中で変えるとき（例: `binary` を `png` へ）は、現在の中身の形式が、新しい種別に合わないと、400（`画像の形式が正しくありません`）。
- 種別を画像（`jpeg` `png`）以外にしたときは、`title` `markers` `image_scale` は、空・空配列・1.0 にする。

過去世代:

- 画像・バイナリのパーツで、中身（`data`）・種別・ファイル名のいずれかが変わるときは、更新前の内容を、過去世代として保管する（世代番号は、そのパーツの最大 + 1）。保管数が `PARTS_MAX_REVISIONS` を超えるときは、古い世代から削除する。`title` `markers` `image_scale` だけの変更では、保管しない。
- 画像の中身（`data`）を差し替えたときは、要求に `markers` がなくても、マーカーは空になる（要求に `markers` があれば、それを用いる）。

応答: 200（更新後の `Part`）

エラー:

| 状況 | 応答 |
|------|------|
| 項目の型の不正、`type` が上記以外 | 400 |
| 組をまたぐ種別の変更で `data` が無い | 400、`{ "detail": "内容を指定してください" }` |
| `POST /files/{file_id}/parts` と同じ入力不正（行動予定、ファイルの内容・ファイル名・形式、倍率、マーカー） | 400（同じ文言） |
| 画像・バイナリの展開後の大きさが上限を超える | 413 |
| パーツが存在しない、または他ユーザのもの | 404 |
| パーツ、または所属ファイルが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| `checklist` へ、または `checklist` から、種別を変えようとした | 409、`{ "detail": "チェックリストの種別は変更できません" }` |

### DELETE `/parts/{part_id}`

対応 REQ: REQ-008

パーツを論理削除する。

要求: なし

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| パーツが存在しない、または他ユーザのもの | 404 |
| 所属ファイルが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| パーツが既に削除済み | 409、`{ "detail": "既に削除されています" }` |

### POST `/parts/{part_id}/undelete`

対応 REQ: REQ-006

削除済みのパーツを、削除解除する。並び順が、同じファイルの中の他のパーツと重なるときは、末尾に付け直す。

要求: なし

応答: 200（`Part`）

エラー:

| 状況 | 応答 |
|------|------|
| パーツが存在しない、または他ユーザのもの | 404 |
| 所属ファイルが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |
| パーツが削除済みでない | 409、`{ "detail": "削除されていません" }` |

### POST `/parts/swap-order`

対応 REQ: REQ-008

同じファイルの中の、削除されていない 2 つのパーツの並び順を入れ替える。

要求（JSON）: `{ "part_id_1": 21, "part_id_2": 22 }`

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| 項目が無い、型の不正、2 つが同じ | 400 |
| いずれかが存在しない、または他ユーザのもの | 404 |
| 2 つの所属ファイルが違う | 400、`{ "detail": "同じ場所の項目ではありません" }` |
| 所属ファイルが削除済み（上位が削除済みを含む）、またはいずれかのパーツが削除済み | 409、`{ "detail": "削除済みのため操作できません" }` |

### GET `/parts/{part_id}/content`

対応 REQ: REQ-007、REQ-009

画像・バイナリのパーツの中身を、バイナリで返す。削除済みのパーツ・ファイルのものも取得できる。

要求（クエリ）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `download` | boolean | 任意 | true なら、ダウンロード（`Content-Disposition: attachment`）として返す。既定 false（画像は `inline`、バイナリは `attachment`） |

応答: 200。本文は、Base64 を展開したファイルの中身。

- `Content-Type`: `jpeg` は `image/jpeg`、`png` は `image/png`、`binary` は `application/octet-stream`
- `Content-Disposition`: ファイル名を付ける（日本語のファイル名は `filename*=UTF-8''...` で示す）
- `Cache-Control: private, no-cache`
- 応答本文・ヘッダにセッション ID を含めない

エラー:

| 状況 | 応答 |
|------|------|
| パーツが存在しない、他ユーザのもの、または種別が画像・バイナリでない | 404 |

### GET `/part-revisions/{revision_id}/content`

対応 REQ: REQ-010

画像・バイナリの過去世代の中身を、ダウンロードとして返す。

要求: なし

応答: 200。ヘッダ・本文は `GET /parts/{part_id}/content`（`download=true`）と同じ形。ファイル名・種別は、その世代のもの。

エラー:

| 状況 | 応答 |
|------|------|
| 世代が存在しない、または他ユーザのもの | 404 |

### GET `/checklists/{checklist_id}`

対応 REQ: REQ-007、REQ-012

要求: なし

応答: 200（`Checklist`）

エラー:

| 状況 | 応答 |
|------|------|
| チェックリストが存在しない、または他ユーザのもの | 404 |

以降のチェックリストの変更は、いずれも、変更後の最新の状態（`Checklist`）を、200 で返す。

チェックリストの変更に共通のエラー:

| 状況 | 応答 |
|------|------|
| チェックリストが存在しない、または他ユーザのもの。カテゴリ・項目が、そのチェックリストに属していない、または削除済み | 404 |
| チェックリストのパーツが削除済み、または所属ファイルが削除済み（上位が削除済みを含む） | 409、`{ "detail": "削除済みのため操作できません" }` |

### PATCH `/checklists/{checklist_id}`

対応 REQ: REQ-012

タイトルを変更する。

要求（JSON）: `{ "title": "買い物" }`（空文字も可。前後の空白は除く）

エラー: 共通のエラー、`title` が無い・型の不正は 400。

### POST `/checklists/{checklist_id}/categories`

対応 REQ: REQ-012

カテゴリを追加する（名前のあるカテゴリだけ。無名カテゴリは、項目の追加で自動で作られる）。末尾に付く。

要求（JSON）: `{ "name": "日用品" }`

エラー:

| 状況 | 応答 |
|------|------|
| `name` が無い、空・空白のみ | 400 |
| 同じ名前の（削除されていない）カテゴリがある | 409、`{ "detail": "同じ名前のカテゴリがあります" }` |

共通のエラーも返す。

### PATCH `/checklists/{checklist_id}/categories/{category_id}`

対応 REQ: REQ-012

カテゴリの名前を変更する。無名カテゴリの名前は変えられない。

要求（JSON）: `{ "name": "食品" }`

エラー: `POST .../categories` と同じ（同名の判定は、自身を除く）。無名カテゴリを指定したときは、409、`{ "detail": "無名のカテゴリは変更できません" }`。

### DELETE `/checklists/{checklist_id}/categories/{category_id}`

対応 REQ: REQ-012

カテゴリを論理削除する。カテゴリの中の項目も、論理削除する。元に戻す操作は提供しない。無名カテゴリも削除できる。

要求: なし

エラー: 共通のエラー。

### POST `/checklists/{checklist_id}/categories/reorder`

対応 REQ: REQ-012

名前のあるカテゴリの表示順を入れ替える。

要求（JSON）: `{ "ordered_ids": [11, 12] }`

`ordered_ids` は、削除されていない、名前のあるカテゴリの識別子を、すべて、重複なく、並べたもの（無名カテゴリは含めない）。

エラー:

| 状況 | 応答 |
|------|------|
| `ordered_ids` が無い、型の不正、重複がある | 400 |
| 識別子の集合が、名前のあるカテゴリの全件と一致しない | 400、`{ "detail": "カテゴリの並びが正しくありません" }` |

共通のエラーも返す。

### POST `/checklists/{checklist_id}/items`

対応 REQ: REQ-012

項目を、カテゴリの末尾に追加する。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `category_id` | integer \| null | 任意 | 追加先のカテゴリ。省略または null は無名カテゴリ（無ければ、自動で作る） |
| `title` | string | 任意 | 項目のタイトル（省略時は空。前後の空白は除く） |

エラー: 共通のエラー、`category_id` の型の不正は 400。

### PATCH `/checklists/{checklist_id}/items/{item_id}`

対応 REQ: REQ-012

項目のタイトル、またはチェック状態を変更する。

要求（JSON。どちらも任意。少なくとも 1 つ）: `{ "title": "牛乳", "is_checked": true }`

エラー: 共通のエラー、どちらも無い・型の不正は 400。

### DELETE `/checklists/{checklist_id}/items/{item_id}`

対応 REQ: REQ-012

項目を論理削除する。元に戻す操作は提供しない。

要求: なし

エラー: 共通のエラー。

### POST `/checklists/{checklist_id}/items/{item_id}/move`

対応 REQ: REQ-012

項目を、別のカテゴリ、または同じカテゴリの中の別の位置へ移す。

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `to_category_id` | integer | 必須 | 移動先のカテゴリ（無名カテゴリも可） |
| `to_index` | integer | 必須 | 移動先の、削除されていない項目の中での位置（0 から。項目を取り除いた後の並びでの位置。件数以上のときは末尾） |

エラー: 共通のエラー（`to_category_id` のカテゴリが存在しない、または別のチェックリストのものは 404）、`to_index` が負・型の不正は 400。

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通事項の認証（401・403）、`GET /settings` を除く全エンドポイント |
| REQ-002 | 共通事項（本人のデータのみ、他ユーザは 404）、全エンドポイント |
| REQ-003 | `GET /items` |
| REQ-004 | `POST /folders`、`PATCH /folders/{folder_id}`、`POST /folders/{folder_id}/move`、`POST /folders/swap-order`、`DELETE /folders/{folder_id}` |
| REQ-005 | `POST /files`、`PATCH /files/{file_id}`、`POST /files/{file_id}/move`、`POST /files/swap-order`、`DELETE /files/{file_id}` |
| REQ-006 | `GET /items`（`include_deleted`）、`GET /files/{file_id}`（`include_deleted_parts`）、`POST .../undelete`（フォルダ・ファイル・パーツ） |
| REQ-007 | `GET /files/{file_id}`、`GET /parts/{part_id}/content`、`GET /checklists/{checklist_id}` |
| REQ-008 | `POST /files/{file_id}/parts`、`PATCH /parts/{part_id}`、`DELETE /parts/{part_id}`、`POST /parts/swap-order` |
| REQ-009 | `Marker`、`Part`（`title` `markers` `image_scale`）、`POST /files/{file_id}/parts`・`PATCH /parts/{part_id}` の検証 |
| REQ-010 | `PATCH /parts/{part_id}`（過去世代の保管）、`Part.revisions`、`GET /part-revisions/{revision_id}/content` |
| REQ-011 | 行動予定の本文、`POST /files/{file_id}/parts`・`PATCH /parts/{part_id}` の検証 |
| REQ-012 | `GET`・`PATCH /checklists/...`、カテゴリ・項目の各エンドポイント |
| REQ-013 | `GET /files/{file_id}`（フロントで印刷用のレイアウトを組み立てる）、`GET /parts/{part_id}/content`（画像） |
| REQ-014 | 画面対象外。失敗時の文言は、本文に内部理由を含まない（共通事項） |
| REQ-015〜018 | 対象外（移行プログラム。コマンドライン） |

## 未決事項

- なし

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-21 22:58 | 未承認 | 初版 |
| 2026-09-21 22:59 | 承認済み | 初版を承認 |
