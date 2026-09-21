# recipe-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。移行プログラム（REQ-011〜014）はコマンドラインで動くため、API は持たない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_RECIPE_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）。以降のパスは、ベース URL からの相対パス。

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `recipe-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

レシピは、ログイン中ユーザ本人のものだけが対象である。他ユーザのレシピは、存在しないものとして扱う（404）。材料・分量名称は、全利用者共通のものと、本人の独自のものだけが対象である。他ユーザの独自のものは、存在しないものとして扱う。

### データ形式

- 要求・応答は JSON（UTF-8）。
- 日時は ISO 8601（オフセット付き。例 `2026-09-21T13:00:00+09:00`）。
- 識別子は整数。応答の対象そのものの識別子は `id`、他の対象への参照は `ingredient_id` などとする。
- 文字列の必須項目は、前後の空白を除いた結果が空のときは入力不正とする。応答には、前後の空白を除いた値を返す。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正（型・必須・空白のみ） | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、削除済み、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 競合（重複） | 409、本文の `detail` は各エンドポイントに示す文言 |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表と各エンドポイントに示す文言だけを使う。以降の「エラー」の表は、共通のうち 401・403・500 を省き、各エンドポイント固有のものと、400・404 の条件だけを書く。

## エンドポイント一覧

| メソッド | パス | 認証 | 対応 REQ |
|----------|------|------|----------|
| GET | `/settings` | 不要 | 横断（未ログイン誘導・戻る先） |
| GET | `/ingredients` | 要 | REQ-008 |
| POST | `/ingredients` | 要 | REQ-008 |
| GET | `/measurements` | 要 | REQ-009 |
| POST | `/measurements` | 要 | REQ-009 |
| GET | `/recipes` | 要 | REQ-003 |
| POST | `/recipes` | 要 | REQ-005 |
| GET | `/recipes/{recipe_id}` | 要 | REQ-004 |
| PUT | `/recipes/{recipe_id}` | 要 | REQ-006 |
| DELETE | `/recipes/{recipe_id}` | 要 | REQ-007 |

## 共通のオブジェクト

### Ingredient（材料）

```json
{ "id": 3, "name": "塩", "kana": "しお", "is_system": true }
```

`is_system` は、全利用者共通の材料なら true。

### Measurement（分量名称）

```json
{ "id": 4, "name_bef": "大さじ", "name_aft": "", "ness_amount": true, "is_system": true }
```

`name_bef`（接頭語）・`name_aft`（接尾語）は、空文字を取り得る（両方が空になることはない）。`ness_amount` は、数量が必要か。`is_system` は、全利用者共通の分量名称なら true。

### RecipeBody（レシピの登録・更新の要求）

```json
{
  "name": "出汁巻き",
  "kana": "だしまき",
  "steps": [
    {
      "description": "卵を溶き、調味料を混ぜる。",
      "items": [
        { "ingredient_id": 9, "measurement_id": 7, "amount": "3" },
        { "ingredient_id": 2, "measurement_id": 8, "amount": "" }
      ]
    }
  ]
}
```

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | メニュー名 |
| `kana` | string | 必須 | メニューのかな |
| `steps` | object[] | 必須 | 工程。入力の順に、工程番号が 1 から付く。1 件以上 |
| `steps[].description` | string | 必須 | 工程の説明 |
| `steps[].items` | object[] | 必須 | 工程の材料の行。入力の順に、並びが 1 から付く。空配列も可 |
| `steps[].items[].ingredient_id` | integer | 必須 | 材料の識別子（共通または本人の独自） |
| `steps[].items[].measurement_id` | integer | 必須 | 分量名称の識別子（共通または本人の独自） |
| `steps[].items[].amount` | string | 必須 | 数量。分量名称が数量ありのときは、空・空白のみは入力不正。数量なしのときは、値にかかわらず、空として保存する |

### RecipeDetail（レシピの応答）

```json
{
  "id": 11,
  "name": "出汁巻き",
  "kana": "だしまき",
  "steps": [
    {
      "step_no": 1,
      "description": "卵を溶き、調味料を混ぜる。",
      "items": [
        {
          "item_no": 1,
          "ingredient": { "id": 9, "name": "卵", "kana": "たまご", "is_system": true },
          "measurement": { "id": 7, "name_bef": "", "name_aft": "個", "ness_amount": true, "is_system": false },
          "amount": "3"
        }
      ]
    }
  ],
  "created_at": "2026-09-21T13:00:00+09:00",
  "updated_at": "2026-09-21T13:00:00+09:00"
}
```

`steps` は `step_no` の昇順、各 `items` は `item_no` の昇順。

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

### GET `/ingredients`

対応 REQ: REQ-008

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 9, "name": "卵", "kana": "たまご", "is_system": true },
    { "id": 13, "name": "大根", "kana": "だいこん", "is_system": false }
  ]
}
```

処理概要: 全利用者共通の材料と、本人の独自の材料を、かなの昇順、同じなら識別子の昇順で返す。ページ分けしない。

エラー: 共通エラーのみ。

### POST `/ingredients`

対応 REQ: REQ-008

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | 材料名 |
| `kana` | string | 必須 | 材料のかな |

応答: 201（`Ingredient`。`is_system` は false）

エラー:

| 状況 | 応答 |
|------|------|
| `name` `kana` が無い、空・空白のみ | 400 |
| 同じ名前の材料が、共通、または本人の独自としてある | 409、`{ "detail": "同じ名前の材料があります" }` |

処理概要: 本人の独自の材料として登録する。

### GET `/measurements`

対応 REQ: REQ-009

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 2, "name_bef": "大さじ", "name_aft": "", "ness_amount": true, "is_system": true },
    { "id": 5, "name_bef": "", "name_aft": "g", "ness_amount": true, "is_system": false }
  ]
}
```

処理概要: 全利用者共通の分量名称と、本人の独自の分量名称を、接頭語の昇順、同じなら接尾語の昇順、それも同じなら識別子の昇順で返す。ページ分けしない。

エラー: 共通エラーのみ。

### POST `/measurements`

対応 REQ: REQ-009

要求（JSON）:

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name_bef` | string | 必須 | 接頭語。空文字も可。前後の空白は除く |
| `name_aft` | string | 必須 | 接尾語。空文字も可。前後の空白は除く |
| `ness_amount` | boolean | 必須 | 数量が必要か |

応答: 201（`Measurement`。`is_system` は false）

エラー:

| 状況 | 応答 |
|------|------|
| 必須項目が無い、型の不正、`name_bef` と `name_aft` が両方とも空（空白のみを含む） | 400 |
| 同じ接頭語と接尾語の組が、共通、または本人の独自としてある | 409、`{ "detail": "同じ分量名称があります" }` |

処理概要: 本人の独自の分量名称として登録する。

### GET `/recipes`

対応 REQ: REQ-003

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 2, "name": "出汁巻き", "kana": "だしまき" },
    { "id": 5, "name": "照り焼き", "kana": "てりやき" }
  ]
}
```

処理概要: 本人の、削除されていないレシピを、かなの昇順、同じなら識別子の昇順で返す。ページ分けしない。

エラー: 共通エラーのみ。

### POST `/recipes`

対応 REQ: REQ-005

要求: `RecipeBody`

応答: 201（`RecipeDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| `name` `kana` が空・空白のみ、`steps` が空または無い、工程の `description` が空・空白のみ、行の項目の欠落・型の不正、数量ありの分量名称で `amount` が空・空白のみ | 400 |
| `ingredient_id` `measurement_id` の材料・分量名称が存在しない、または他ユーザの独自のもの | 404 |
| `name` が、本人の削除されていないレシピと重複する | 409、`{ "detail": "同じメニュー名のレシピがあります" }` |

処理概要: 1 つのトランザクションで、レシピ、工程（工程番号は入力の順に 1 から）、工程の材料の行（並びは入力の順に 1 から）を登録する。失敗したときは、何も登録しない。数量なしの分量名称の行は、`amount` を空にして保存する。

### GET `/recipes/{recipe_id}`

対応 REQ: REQ-004

要求: なし

応答: 200（`RecipeDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| レシピが存在しない、削除済み、または他ユーザのもの | 404 |

### PUT `/recipes/{recipe_id}`

対応 REQ: REQ-006

レシピの内容を、要求の内容で置き換える（メニュー名・かな・工程・工程の材料の行のすべて）。

要求: `RecipeBody`

応答: 200（更新後の `RecipeDetail`）

エラー:

| 状況 | 応答 |
|------|------|
| `POST /recipes` と同じ入力不正 | 400 |
| レシピが存在しない、削除済み、または他ユーザのもの。材料・分量名称が存在しない、または他ユーザの独自のもの | 404 |
| `name` が、対象自身を除いた、本人の削除されていないレシピと重複する | 409、`{ "detail": "同じメニュー名のレシピがあります" }` |

処理概要: 1 つのトランザクションで、対象のレシピを行ロックで取得し、メニュー名・かなを更新し、既存の工程と工程の材料の行を削除して、要求の内容で作り直す。レシピの識別子と作成日時は変わらない。更新日時を更新する。失敗したときは、元の内容が残る。

### DELETE `/recipes/{recipe_id}`

対応 REQ: REQ-007

処理概要: 本人の削除されていないレシピを、論理削除する。工程と工程の材料の行は残る。削除後は、一覧・詳細・更新・削除の対象にならない。同じメニュー名で、新たに登録できる。

要求: なし

応答: 204（本文なし）

エラー:

| 状況 | 応答 |
|------|------|
| レシピが存在しない、既に削除済み、または他ユーザのもの | 404 |

## 要件トレーサビリティ

| 要件 | 設計 |
|------|------|
| REQ-001 | 共通事項の認証（401・403）、`GET /settings` を除く全エンドポイント |
| REQ-002 | 共通事項（本人のレシピのみ、他ユーザは 404、共通と本人の独自の材料・分量名称のみ） |
| REQ-003 | `GET /recipes` |
| REQ-004 | `GET /recipes/{recipe_id}`（`RecipeDetail`） |
| REQ-005 | `POST /recipes`、`GET /ingredients`・`GET /measurements`（選択肢） |
| REQ-006 | `PUT /recipes/{recipe_id}` |
| REQ-007 | `DELETE /recipes/{recipe_id}` |
| REQ-008 | `GET`・`POST /ingredients` |
| REQ-009 | `GET`・`POST /measurements` |
| REQ-010 | API 外（ログ）。失敗の本文は内部理由を含まない（共通エラー） |
| REQ-011〜014 | API 外（移行プログラム。コマンドライン） |

## 未決事項

- なし

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-09-21 21:20 | 未承認 | 初版 |
| 2026-09-21 21:22 | 承認済み | 初版を承認 |
