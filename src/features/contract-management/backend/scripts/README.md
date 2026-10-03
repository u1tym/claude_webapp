# password-management からの取り込み手順

`password-management` のパスワードエントリを、`contract-management` の「契約を伴わない契約」として取り込む手順です（REQ-010）。
統合の準備として、当面は両方の機能が同じ情報を持ちます。取り込み元（`password-management` のデータ）は変更しません。

## 取り込まれるもの

| 取り込み元（`password_management.entries`） | 取り込み先（`contract_management.contracts`） |
|---|---|
| タイトル | 名称（前後の空白を除く。200 文字以内） |
| ユーザ名 | ユーザ名（前後の空白を除く） |
| パスワード | パスワード（そのまま。空白・複数行も保つ） |
| サイトURL | ホームページ（空は未設定） |
| メモ | メモ（空は未設定） |
| （なし） | 契約を伴わない、ステータスは有効、区分は「その他」、ログイン方法はユーザ名とパスワード |

- 利用者ごとに、その利用者本人のエントリだけを、その利用者の契約として取り込みます。区分「その他」は、なければ利用者ごとに作ります。
- 論理削除済みのエントリと、論理削除済みの利用者のエントリは、取り込みません。
- 取り込み元のエントリの ID を、取り込み先に控えます。**何度実行しても、同じエントリは重複して取り込まれません。** 取り込んだあとに、取り込み元へ追加したエントリは、次の実行で取り込まれます。
- 取り込んだ契約を、画面で編集しても、再実行で上書きされません。

## 事前準備

1. 開発用 DB（または本番の DB）に、次が適用されていること。
   - `portal` の DDL（`public.users` など）と、`api-key-management` の DDL（`public.api_keys`）
   - `password-management` の DDL（`password_management.entries`）。**取り込み元の表がないと、取り込めません。**
   - `contract-management` の DDL: `backend` で `venv/Scripts/python sql/apply.py`
2. `backend/.env` が、取り込み先の DB を指していること（`DB_SERVER`、`DB_PORT`、`DB_DATABASE`、`DB_USERNAME`、`DB_PASSWORD`）。
   取り込み元は、取り込み先と**同じ DB** のスキーマ `password_management` を読みます。
3. 取り込み先の利用者が、`public.users` に存在すること（取り込み元の `user_id` は、同じ `public.users.id` を指しています）。

### 取り込み先を本番の DB にする場合

`backend/.env` を書き換えずに、環境変数 `CONTRACT_MANAGEMENT_ENV_FILE` に、別の設定ファイルを指定できます。

```powershell
$env:CONTRACT_MANAGEMENT_ENV_FILE = "D:\secure\contract-management.prod.env"
venv\Scripts\python scripts\import_password_management.py --dry-run
```

## 実行

`src/features/contract-management/backend` で実行します。

```powershell
# 1. ドライラン: 何も書き込まずに、結果（取り込む予定の件数、取り込めないエントリ）だけを表示する
venv\Scripts\python scripts\import_password_management.py --dry-run

# 2. 取り込み
venv\Scripts\python scripts\import_password_management.py
```

必ず、先にドライランで結果を確認してください。

## 結果の読み方

```
【取り込み完了】
対象のエントリ: 12 件
取り込み: 10 件
取り込み済みのためスキップ: 1 件
取り込めなかった: 1 件
論理削除済みの利用者のエントリ（対象外）: 2 件
  - 取り込み元のエントリ ID 34: 名称（タイトル）が 200 文字を超える
```

| 項目 | 意味 |
|---|---|
| 対象のエントリ | 取り込み元の、削除されていない（利用者も削除されていない）エントリの数 |
| 取り込み | 今回、新しく取り込んだ件数（ドライランでは「予定」） |
| 取り込み済みのためスキップ | 前回までに取り込み済みで、今回は何もしなかった件数 |
| 取り込めなかった | 登録に失敗したエントリ。取り込み元の ID と理由を表示する |
| 論理削除済みの利用者のエントリ | 対象に含めない |

- **終了コード**: 取り込めなかったエントリがなければ 0、あれば 1、実行できなかったとき（DB に接続できない、取り込み元の表がない）は 2。
- パスワード・ユーザ名・タイトルの値は、出力にも、ログ（`log/contract-management.log`）にも出しません。取り込めなかったエントリは、ID で特定します。
- 取り込めなかったエントリは、取り込み元を直して（たとえばタイトルを短くして）から、もう一度実行すると、取り込まれます。

## 取り込み後の確認

1. 画面（`/portal_contract_management/`）のアカウント一覧に、取り込んだエントリが並ぶこと。
2. パスワードの「表示」「コピー」で、元のパスワードが表示・コピーされること。
3. 契約一覧で、「契約を伴わない」に絞ると、取り込んだ契約が出ること。区分は「その他」です。必要なら、区分を作って、画面で付け替えてください。

## 注意

- この取り込みは、`password-management` を閉鎖するまでの移行用です。取り込み元のデータを変えないので、閉鎖の判断は、別途行います。
- 取り込み後は、両方の機能で、同じ情報を別々に編集できます。どちらかを正にして、編集の混乱を避けてください。
