# contract-management API設計

> テーブル定義と ER 図は書かない（`db-design.md` を参照）。画面レイアウト・部品配置は書かない（`ui-design.md`）。Vue コンポーネント構成は `design.md`。

## 概要

この機能の FastAPI が公開する HTTP API の契約。`requirements.md` の該当 REQ を満たすことだけを書く。ログイン・ログアウトの API は持たない（`portal` が担う）。他機能向けの利用可否判定 API は提供しない。

関連ドキュメント:

- 全体設計: `design.md`
- UI設計: `ui-design.md`
- DB設計: `db-design.md`

## 共通事項

### ベース URL

`VITE_API_CONTRACT_MANAGEMENT_URL`（フロントの環境変数。詳細は `rules/11-frontend.md`）

### 認証

Cookie ベースのセッション認証を用いる。セッションの発行は `portal` が行う。本機能は Cookie を検証する。加えて、外部システム向けに API キー認証を受け付ける（後述）。

- Cookie 名: `session_id`。値はセッション ID。HttpOnly、SameSite=Lax。本番では Secure。
- セッション ID は URL、レスポンス本文、`localStorage` に置かない。
- フロントは Cookie を送る（credentials）。
- 有効期間は `SESSION_TIMEOUT_MINUTES` 分。認証が必要な要求のたびに期限を延ばす。
- 期限切れ、行が無い、対象ユーザが論理削除済みは、いずれも未ログイン（401）。
- ログイン中でも、識別子 `contract-management` の機能が割り当てられていない、または本機能が論理削除済みなら権限なし（403）。
- `DEBUG_USER` があるときだけ、Cookie がなくてもそのユーザ名として処理する。本番では空にする。その場合も本機能の割当を判定する。

GET `/settings` だけ認証不要。それ以外の全エンドポイントは認証を要する。

#### API キーによる認証（REQ-013）

- `Authorization: Bearer <API キー>` で受け取る（スキーム名は大文字小文字を区別しない。キーの前後の空白は除く）。URL では受け取らない。Cookie は不要。
- `Authorization` ヘッダがあるときは API キーだけで判定し、失敗しても Cookie・`DEBUG_USER` には戻らない。無いときは従来どおり。
- `Bearer` 方式でない、キーが空、一致する API キーが無い、失効済み、有効期限切れ、持ち主が論理削除済み: 401。持ち主に本機能が割り当てられていない、または本機能が論理削除済み: 403。
- 許可したときは、持ち主をログイン中ユーザとして処理し、`last_used_at` を更新する。セッションの期限は延ばさない。
- 契約の詳細は `specs/api-key-management/api-design.md` の「対象機能の API キー認証」と同じ。
- **API キーで使えるエンドポイントは、エンドポイント一覧の「API キー」列が「可」のものだけ**。それ以外は、API キーでは 403（権限がありません）とする。
- API キーでは、パスワードの値を、受け取らず、返さない。契約の登録・更新の要求に `password` が含まれていたら、400 とし、何も保存しない。

### パスワードの扱い

- パスワードの値は、`GET /contracts/{contract_id}/password` の応答にだけ含める。それ以外のどの応答にも含めない（一覧、アカウント一覧、詳細、解約順、登録・更新の応答を含む）。
- 応答には、パスワードの値の代わりに、設定されているか（`has_password`）と、「パスワード未設定」か（`password_unset`。ログイン方法にユーザ名とパスワードを含み、パスワードが未設定）を含める。
- 登録・更新の要求の `password` は、Cookie（または `DEBUG_USER`）による認証のときだけ受け付ける。更新で `password` が無いとき、保存済みのパスワードは変えない。`password` は、空文字にできない（空白のみ・複数行は可）。パスワードを消す操作は無い。

### エラー（共通）

| 状況 | 応答 |
|------|------|
| 入力不正（型・必須・形式・値の範囲・項目の組み合わせ、他ユーザの ID の指定を含む） | 400、本文 `{ "detail": "入力が不正です" }` |
| 未ログイン | 401、本文 `{ "detail": "未ログイン" }` |
| 権限なし（API キーで許可しない操作を含む） | 403、本文 `{ "detail": "権限がありません" }` |
| 対象なし（他人の行、削除済み、存在しない ID を含む） | 404、本文 `{ "detail": "対象がありません" }` |
| 競合（区分の名称が重複、依存の循環、使用中の区分の削除、「その他」の変更・削除など） | 409、本文 `{ "detail": "保存できませんでした" }` |
| 未処理例外 | 500、本文 `{ "detail": "サーバエラーです" }`。内部情報を本文に含めない |

失敗の内部理由はログにだけ残す。本文には上表の文言だけを使う。

### 契約の表現（Contract）

契約を返す応答（`/contracts` の一覧・詳細・登録・更新）は、次の形の契約を返す。契約を伴わない契約では、「契約を伴う契約だけの項目」が、`null`（配列は `[]`）になる。

```json
{
  "id": 12,
  "name": "ネット動画サービス",
  "has_contract": true,
  "category": { "id": 3, "name": "動画配信", "is_financial": false },
  "status": "active",
  "homepage": "https://example.com",
  "memo": null,
  "login_methods": ["password", "2fa_mail"],
  "twofa_mail_address": "me@example.com",
  "twofa_tel_number": null,
  "username": "taro",
  "has_password": true,
  "password_unset": false,
  "registered_email": "me@example.com",
  "fee_amount": 990,
  "fee_cycle": "monthly",
  "renewal_date": "2026-11-05",
  "contract_date": "2020-04",
  "contract_date_precision": "month",
  "trial_end_date": null,
  "end_date": null,
  "auto_renewal": true,
  "holder_name": "山田 太郎",
  "member_number": "A-123456",
  "cancel_notice_days": 7,
  "cancellation_fee": "なし",
  "min_term_months": 12,
  "contact_phone": "0120-000-000",
  "contact_email": "support@example.com",
  "contact_hours": "平日 10:00-18:00",
  "cancellation_method": "マイページの設定から解約する",
  "depends_on": [{ "id": 8, "name": "プロバイダ" }],
  "payment_contract": { "id": 5, "name": "Aカード" },
  "depended_by": [],
  "payment_for": []
}
```

| 項目 | 説明 |
|------|------|
| `login_methods` | `password`（ユーザ名とパスワード）、`passkey`（パスキー）、`2fa_mail`（2段階認証（メール））、`2fa_tel`（2段階認証（TEL））の配列（重複なし） |
| `status` | `active`（有効）、`paused`（休止中）、`cancelled`（解約） |
| `fee_amount` / `fee_cycle` | 維持費。0 以上の整数と、`yearly`（年間）または `monthly`（月額）。どちらも無いか、どちらも有る |
| `contract_date` | 精度に応じた形式の文字列。`day` は `YYYY-MM-DD`、`month` は `YYYY-MM`、`year` は `YYYY`。`unknown` または無いときは `null` |
| `contract_date_precision` | `day` / `month` / `year` / `unknown` / `null`（契約日を持たないとき） |
| `auto_renewal` | `true`（あり）、`false`（なし）、`null`（未設定） |
| `depends_on` | 依存契約（削除されていないものだけ）。`id` と名称 |
| `payment_contract` | 支払方法として選んだ契約（削除されていないときだけ）。無いときは `null` |
| `depended_by` | この契約に依存している契約（削除されていないものだけ） |
| `payment_for` | この契約を支払方法としている契約（削除されていないものだけ） |

日付（`renewal_date`、`trial_end_date`、`end_date`）は `YYYY-MM-DD`。

### 契約の入力（登録・更新）

POST と PATCH は、同じ形式の本文を受け取る。PATCH は、`password` 以外の全項目を送る（送らなかった任意項目は、空（`null`、配列は `[]`）に更新される）。

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | 名称。前後の空白を除いて、空でなく、200 文字以内 |
| `has_contract` | boolean | 任意 | 契約を伴うか。既定 `true` |
| `category_id` | integer | 任意 | 区分。本人の削除されていない区分。無いときは「その他」 |
| `status` | string | 任意 | `active` / `paused` / `cancelled`。既定 `active` |
| `homepage`、`memo`、`username`、`registered_email` | string / null | 任意 | 前後の空白を除く。空文字は `null` として扱う |
| `login_methods` | string[] | 任意 | 上表の値。既定 `[]` |
| `twofa_mail_address` | string / null | 任意 | `login_methods` に `2fa_mail` があるときだけ指定できる |
| `twofa_tel_number` | string / null | 任意 | `login_methods` に `2fa_tel` があるときだけ指定できる |
| `password` | string | 任意 | Cookie 認証のときだけ。空文字は不可。API キーでは指定できない（400） |
| `fee_amount` / `fee_cycle` | integer / string | 任意 | 契約を伴うときだけ。どちらも指定するか、どちらも指定しない |
| `renewal_date`、`trial_end_date` | string / null | 任意 | 契約を伴うときだけ。`YYYY-MM-DD` |
| `contract_date_precision` / `contract_date` | string / string | 任意 | 契約を伴うときだけ。精度が `day`・`month`・`year` のときは、その形式の `contract_date` が必須。`unknown` のとき、または無いとき、`contract_date` は指定しない |
| `end_date` | string / null | 任意 | 契約を伴うかつ `status` が `cancelled` のときだけ |
| `auto_renewal` | boolean / null | 任意 | 契約を伴うときだけ |
| `holder_name`、`member_number`、`cancellation_fee`、`contact_phone`、`contact_email`、`contact_hours`、`cancellation_method` | string / null | 任意 | 契約を伴うときだけ |
| `cancel_notice_days`、`min_term_months` | integer / null | 任意 | 契約を伴うときだけ。0 以上 |
| `depends_on_ids` | integer[] | 任意 | 契約を伴うときだけ。依存契約。本人の削除されていない他の契約（自分以外、重複なし） |
| `payment_contract_id` | integer / null | 任意 | 契約を伴うときだけ。支払方法。本人の削除されていない他の契約のうち、金融機関の区分の契約 |

検査（いずれも違反は 400。依存の循環と、区分変更の制限は 409）:

- 契約を伴わない（`has_contract` が `false`）のとき、「契約を伴うときだけ」の項目に値を指定すると 400。
- `payment_contract_id` が、自分自身、他ユーザの契約、削除済みの契約、金融機関でない区分の契約のときは 400。
- `depends_on_ids` に、自分自身、他ユーザの契約、削除済みの契約、重複があるときは 400。更新の結果、依存の関係が循環するときは 409。
- 更新で、契約の区分を、金融機関の区分から金融機関でない区分に変えるとき、その契約が他の契約の支払方法になっていれば 409。
- 契約を伴うから伴わないへ更新したとき、契約を伴う契約だけの項目は消える（解約順の対象からも外れる）。

## エンドポイント一覧

| メソッド | パス | 認証 | API キー | 対応 REQ |
|----------|------|------|----------|----------|
| GET | `/settings` | 不要 | - | 横断（未ログイン誘導・戻る先） |
| GET | `/accounts` | 要 | 不可 | REQ-007、REQ-014 |
| GET | `/contracts` | 要 | 可 | REQ-004、REQ-014、REQ-013 |
| GET | `/contracts/{contract_id}` | 要 | 可 | REQ-005、REQ-013 |
| GET | `/contracts/{contract_id}/password` | 要 | 不可 | REQ-005、REQ-007 |
| POST | `/contracts` | 要 | 可（`password` なし） | REQ-001、REQ-013 |
| PATCH | `/contracts/{contract_id}` | 要 | 可（`password` なし） | REQ-002、REQ-013 |
| DELETE | `/contracts/{contract_id}` | 要 | 不可 | REQ-003 |
| GET | `/categories` | 要 | 可 | REQ-006、REQ-013 |
| POST | `/categories` | 要 | 不可 | REQ-006 |
| PATCH | `/categories/{category_id}` | 要 | 不可 | REQ-006 |
| DELETE | `/categories/{category_id}` | 要 | 不可 | REQ-006 |
| GET | `/cancellation-plan` | 要 | 可 | REQ-008、REQ-009、REQ-013 |
| GET | `/cancellation-plan/candidates` | 要 | 不可 | REQ-008 |
| PUT | `/cancellation-plan` | 要 | 不可 | REQ-008 |

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

### GET `/accounts`

対応 REQ: REQ-007、REQ-014

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `keyword` | 任意 | 名称・ユーザ名・ホームページ・メモのいずれかに、大文字小文字を区別しない部分一致で絞り込む。無い、または空・空白のみのときは全件 |

応答: 200

```json
{
  "total": 2,
  "items": [
    {
      "id": 12,
      "name": "ネット動画サービス",
      "username": "taro",
      "homepage": "https://example.com",
      "has_password": true,
      "password_unset": false
    }
  ]
}
```

`items` は、本人の削除されていない契約のうち、ユーザ名またはパスワードを持つものを、登録順（ID 昇順）で返す（契約を伴うか、ステータスは問わない）。パスワードの値は含めない。

### GET `/contracts`

対応 REQ: REQ-004、REQ-014、REQ-013

要求: クエリ

| 名前 | 必須 | 説明 |
|------|------|------|
| `keyword` | 任意 | 名称・ホームページ・登録メールアドレス・ユーザ名・メモのいずれかに、大文字小文字を区別しない部分一致で絞り込む（パスワードは対象外）。無い、または空・空白のみのときは絞り込まない |
| `category_id` | 任意 | 区分で絞り込む |
| `status` | 任意 | `active` / `paused` / `cancelled` で絞り込む |
| `has_contract` | 任意 | `true`（契約を伴う）/ `false`（契約を伴わない）で絞り込む |
| `password_unset` | 任意 | `true` のとき、「パスワード未設定」の契約だけに絞り込む |

応答: 200

```json
{
  "total": 1,
  "items": [ { "...": "契約の表現（Contract）" } ]
}
```

`items` は、本人の削除されていない契約を、登録順（ID 昇順）で返す。条件を組み合わせたときは、すべてに合うものを返す。

エラー:

| 状況 | 応答 |
|------|------|
| `status`・`has_contract`・`password_unset` が不正な値、`category_id` が整数でない | 400 |

### GET `/contracts/{contract_id}`

対応 REQ: REQ-005、REQ-013

要求: なし

応答: 200（契約の表現（Contract））

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない契約でない | 404 |

### GET `/contracts/{contract_id}/password`

対応 REQ: REQ-005、REQ-007

要求: なし

応答: 200

```json
{ "password": "string または null" }
```

パスワードが未設定のときは `null`。複数行の値は、改行を保って返す。

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない契約でない | 404 |
| API キーによる要求 | 403 |

処理概要: パスワードの値を 1 件ずつ返す。操作の記録には、契約の ID だけを残し、値は残さない。

### POST `/contracts`

対応 REQ: REQ-001、REQ-013

要求: 「契約の入力」の本文

応答: 201（登録した契約の表現（Contract））

エラー:

| 状況 | 応答 |
|------|------|
| 契約の入力の検査に違反 | 400 |
| API キーによる要求で `password` を含む | 400（何も保存しない） |

処理概要: 契約を登録する。API キーで登録した契約は、パスワードが未設定になる。契約を伴うとき、ステータスの既定は `active`。同じ名称の契約も登録できる。

### PATCH `/contracts/{contract_id}`

対応 REQ: REQ-002、REQ-013

要求: 「契約の入力」の本文（`password` 以外の全項目を送る）

応答: 200（更新後の契約の表現（Contract））

エラー:

| 状況 | 応答 |
|------|------|
| 契約の入力の検査に違反 | 400 |
| API キーによる要求で `password` を含む | 400（何も保存しない） |
| 本人の削除されていない契約でない | 404 |
| 依存の循環、金融機関の区分から金融機関でない区分への変更の制限 | 409 |

処理概要: 契約を更新する。`password` が無いとき、保存済みのパスワードは変えない。ステータスが `cancelled` になった契約、契約を伴わないに更新した契約は、解約順の対象から外す。ステータスが `cancelled` でなくなったとき、契約終了日は消える。

### DELETE `/contracts/{contract_id}`

対応 REQ: REQ-003

要求: なし

応答: 204

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない契約でない | 404 |
| API キーによる要求 | 403 |

処理概要: 契約を論理削除する。解約順の対象から外す。他の契約の依存契約・支払方法として参照されていても、削除できる（参照していた側の表示からは外れる）。

### GET `/categories`

対応 REQ: REQ-006、REQ-013

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 1, "name": "その他", "is_default": true, "is_financial": false },
    { "id": 3, "name": "動画配信", "is_default": false, "is_financial": false },
    { "id": 4, "name": "銀行・カード", "is_default": false, "is_financial": true }
  ]
}
```

`items` は、本人の削除されていない区分を返す。「その他」を先頭に、続いて ID 昇順。「その他」がまだ無いときは、作ってから返す。

### POST `/categories`

対応 REQ: REQ-006

要求: JSON

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `name` | string | 必須 | 区分の名称。前後の空白を除いて、空でなく、100 文字以内 |
| `is_financial` | boolean | 任意 | 金融機関の区分か。既定 `false` |

応答: 201（作成した区分。`GET /categories` の `items` の要素と同じ形）

エラー:

| 状況 | 応答 |
|------|------|
| 入力の検査に違反 | 400 |
| 同じ利用者の削除されていない区分と、名称が重複 | 409 |
| API キーによる要求 | 403 |

### PATCH `/categories/{category_id}`

対応 REQ: REQ-006

要求: POST `/categories` と同じ形式（`name` と `is_financial` を送る）

応答: 200（更新後の区分）

エラー:

| 状況 | 応答 |
|------|------|
| 入力の検査に違反 | 400 |
| 本人の削除されていない区分でない | 404 |
| 名称が重複、「その他」の変更、金融機関の指定を外せない（その区分の契約が、他の契約の支払方法になっている） | 409 |
| API キーによる要求 | 403 |

処理概要: 区分の名称と金融機関の指定を更新する。名称の変更は、その区分を使っている契約の表示に反映される。

### DELETE `/categories/{category_id}`

対応 REQ: REQ-006

要求: なし

応答: 204

エラー:

| 状況 | 応答 |
|------|------|
| 本人の削除されていない区分でない | 404 |
| 「その他」、またはその区分を使っている削除されていない契約がある | 409 |
| API キーによる要求 | 403 |

処理概要: 区分を論理削除する。

### GET `/cancellation-plan`

対応 REQ: REQ-008、REQ-009、REQ-013

要求: なし

応答: 200

```json
{
  "items": [
    {
      "position": 1,
      "contract_id": 12,
      "name": "ネット動画サービス",
      "cancellation_method": "マイページの設定から解約する",
      "depends_on": [{ "id": 8, "name": "プロバイダ" }]
    }
  ],
  "warnings": [
    {
      "contract_id": 12,
      "name": "ネット動画サービス",
      "depends_on_contract_id": 8,
      "depends_on_name": "プロバイダ"
    }
  ]
}
```

`items` は、解約の対象を、解約順（`position` の昇順）に返す。対象としての条件を満たさなくなった契約（ステータスが解約、削除、契約を伴わない）は、含めない。`cancellation_method` が未入力のときは `null`。パスワード、ユーザ名、登録メールアドレスは含めない。`warnings` は、ある契約が依存している契約が、その契約より先に解約順に並んでいるときの、組を返す（無いときは `[]`）。解約手順の PDF 出力は、この応答を使う。

### GET `/cancellation-plan/candidates`

対応 REQ: REQ-008

要求: なし

応答: 200

```json
{
  "items": [
    { "id": 15, "name": "ジム", "category_name": "その他", "has_cancellation_method": false }
  ]
}
```

`items` は、本人の削除されていない契約のうち、契約を伴うもので、ステータスが `active` または `paused` で、まだ解約順に入っていないものを、ID 昇順で返す。

### PUT `/cancellation-plan`

対応 REQ: REQ-008

要求: JSON

| 項目 | 型 | 必須 | 説明 |
|------|----|----|------|
| `contract_ids` | integer[] | 必須 | 解約の対象の契約を、解約する順に並べた ID の配列。空配列も可（対象なし） |

応答: 200（保存後の解約順。`GET /cancellation-plan` と同じ形）

エラー:

| 状況 | 応答 |
|------|------|
| `contract_ids` が配列でない、重複がある | 400 |
| 本人の削除されていない契約でない ID、契約を伴わない契約、ステータスが `cancelled` の契約を含む | 400 |
| API キーによる要求 | 403 |

処理概要: 本人の解約順を、要求の順に置き換える（`position` は 1 から連番）。警告があっても保存できる。

## 要件トレーサビリティ

| 要件 | API |
|------|-----|
| REQ-001 | POST `/contracts` |
| REQ-002 | PATCH `/contracts/{contract_id}` |
| REQ-003 | DELETE `/contracts/{contract_id}` |
| REQ-004 | GET `/contracts` |
| REQ-005 | GET `/contracts/{contract_id}`、GET `/contracts/{contract_id}/password` |
| REQ-006 | GET・POST `/categories`、PATCH・DELETE `/categories/{category_id}` |
| REQ-007 | GET `/accounts`、GET `/contracts/{contract_id}/password` |
| REQ-008 | GET・PUT `/cancellation-plan`、GET `/cancellation-plan/candidates` |
| REQ-009 | GET `/cancellation-plan`（PDF はフロントが出力） |
| REQ-010 | API なし（取り込みスクリプト） |
| REQ-011 | API なし（ログ） |
| REQ-012 | すべてのエンドポイントが、本人の分だけを対象にする |
| REQ-013 | 「API キーによる認証」、エンドポイント一覧の「API キー」列 |
| REQ-014 | `password_unset`、GET `/contracts` の `password_unset` の絞り込み、GET `/accounts` |

## 未決事項

- なし

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-10-03 11:08 | 未承認 | 初版 |
| 2026-10-03 11:10 | 承認済み | 初版を承認 |
