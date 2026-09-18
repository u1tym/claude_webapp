# SPEC開発ルール（Claude Code版）

このファイルは、Cursor用ルール（`.cursor/rules/*.mdc`）をClaude Code用に書き換えたものです。

Cursorの `globs` / `alwaysApply` によるファイル種別ごとの自動読み込みは、Claude Codeには存在しない。そのため、元々グロブで条件付き読み込みされていたルールも含め、以下すべてを本ファイルから常時インポートする。各ルールの冒頭には、元のCursorルールでの適用範囲（参考情報）を残している。

## ルール一覧

- @rules/02-project.md — フォルダ構成
- @rules/11-frontend.md — フロントエンド実装方式
- @rules/12-backend.md — バックエンド実装方式
- @rules/13-db.md — DB方式
- @rules/14-security.md — セキュリティ方式
- @rules/15-ui-style.md — 画面の見た目（共通の画面分割とナビ）
- @rules/16-logging.md — ログ出力方針
- @rules/17-nginx-deploy.md — nginxデプロイ時の公開URLとディスク配置
- @rules/21-requirements.md — 要件作成
- @rules/22-design.md — 全体設計作成
- @rules/22a-ui-design.md — UI設計作成
- @rules/22b-db-design.md — DB設計作成
- @rules/22c-api-design.md — API設計作成
- @rules/23-tasks.md — タスク分解

## SPEC開発

実装前に以下の順で成果物を作る。

1. requirements.md
2. design.md
3. ui-design.md
4. db-design.md
5. api-design.md
6. tasks.md

- 作成時はテンプレートを用いる。テンプレートの格納先フォルダ・作成した成果物の格納先フォルダは `rules/02-project.md` を参照する。
- SPEC（requirements.md / design.md / ui-design.md / db-design.md / api-design.md / tasks.md）は**見出しも本文も日本語**で書く。
- ファイル名、ディレクトリ名、コードパス、環境変数名、API パス、要件 ID（`REQ-001`）は英語のままでよい。

### Requirements Phase

- requirements.md を最初に作成する
- テンプレート: `requirements-template.md`
- 要件は EARS の意味を保ち、日本語の文で記述する
- 受け入れ条件を必須とする
- 詳細は `rules/21-requirements.md`

### Design Phase

requirements.md のユーザ承認後に、次の順で作成する。
直前のファイルが承認されるまで、次を作成しない。

1. `design.md`（全体構成）
   - テンプレート: `design-template.md`
   - 画面毎の部品配置と画面遷移は書かない（`ui-design.md`）
   - API のパス・要求・応答・エラーは書かない
   - テーブル定義と ER 図は書かない
   - 詳細は `rules/22-design.md`
2. `ui-design.md`（UI 設計。`design.md` のユーザ承認後）
   - テンプレート: `ui-design-template.md`
   - 画面毎の部品配置と画面遷移を書く
   - 起動・モジュール構成、API の契約、テーブル定義は書かない
   - 詳細は `rules/22a-ui-design.md`
3. `db-design.md`（ER 図とテーブル設計。`ui-design.md` のユーザ承認後）
   - テンプレート: `db-design-template.md`
   - 詳細は `rules/22b-db-design.md`
4. `api-design.md`（エンドポイントの契約。`db-design.md` のユーザ承認後）
   - テンプレート: `api-design-template.md`
   - 詳細は `rules/22c-api-design.md`

要件に存在しない機能を追加しない。

### Tasks Phase

- tasks.md を作成する（`design.md` / `ui-design.md` / `db-design.md` / `api-design.md` がすべて承認された後）
- テンプレート: `tasks-template.md`
- 4 つの設計書を元にタスクへ分解する
- タスクは実装可能な粒度にする
- 実装は、ユーザが tasks.md を承認した後に開始する
- 詳細は `rules/23-tasks.md`

### Implementation Phase

- tasks.md に記載されたタスクのみ実装する
- 実装前に requirements.md と 4 つの設計書を確認する
- 要件と設計にない機能を勝手に追加しない
- コードは `src/features/<feature-name>/{frontend,backend,tests}` に置く
- 実装方式は `rules/11-frontend.md`（フロントエンド）、`rules/12-backend.md`（バックエンド）、`rules/13-db.md`（DB）、`rules/14-security.md`（セキュリティ）、`rules/15-ui-style.md`（画面の見た目）、`rules/16-logging.md`（ログ）、`rules/17-nginx-deploy.md`（デプロイ）に従う

## レビューと承認

### レビュー

- **レビューとは、ユーザがその成果物を承認することである。**
- Claude は承認を推測しない。ユーザが対象成果物を承認する旨を明示するまで、次フェーズに進まない。「このファイルを承認する」「承認」「OK」は有効。対象ファイルが不明なときは確認する。
- 各成果物末尾の `承認` は **履歴** とする。行を消したり、過去行の日時・状態・変更概要を書き換えたりしない。
- **現在の状態** は表の最終行の状態と一致させる。ユーザ承認後にだけ、承認済みの行を追記する。

### 承認

承認欄の形式:

```
## 承認

現在の状態: 未承認

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-22 08:42 | 未承認 | 初版 |
```

- 日時は日本時間 `YYYY-MM-DD HH:mm`（日付しか分からない過去分は `YYYY-MM-DD` 可）。
- 状態は `未承認` または `承認済み`。
- 変更概要は、その行が指す改訂の内容（初版、何を変えたか、何を承認したか）。

追記のタイミング:

- 新規作成: 未承認の行を 1 件（変更概要は「初版」）。
- 承認済みファイルの本文を変える: 未承認の行を追記し、現在の状態を未承認にする。
- ユーザが承認した: 承認済みの行を追記し、現在の状態を承認済みにする。

### 承認済みSPECの改訂

承認済みの成果物を変えるときは、変更を当該ファイルに反映し、承認欄へ未承認の行を追記する。ユーザが再承認するまで、後続成果物の更新や実装に進まない。影響する後続ファイルも更新し、再承認を得る。
