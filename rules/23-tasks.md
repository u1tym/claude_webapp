# タスク分解（日本語）

> 元Cursorルールでの適用範囲: `specs/**/tasks.md` を編集するとき

見出しと本文は日本語で書くこと。

`specs/templates/tasks-template.md` に従うこと。

タスクは1〜4時間程度で完了できる粒度に分解すること。

タスクごとに完了条件を記載すること。

タスクは要件および設計（`design.md` / `ui-design.md` / `db-design.md` / `api-design.md`）の節とのトレーサビリティを持つこと。

実装パス（`src/features/<feature-name>/{frontend,backend,tests}`）と所要時間（1〜4時間）を各タスクに記載すること。

ユーザが `design.md` / `ui-design.md` / `db-design.md` / `api-design.md` をすべて承認するまで、このファイルを作成しないこと。

承認欄は履歴形式とする（日時・状態・変更概要。詳細は `CLAUDE.md`）。
