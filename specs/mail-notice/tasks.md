# タスク: mail-notice（メール通知）

## 概要

対象機能: `mail-notice`

ソース配置:

- フロントエンド: なし（`frontend` は置かない）
- バックエンド: `src/features/mail-notice/backend`
- テスト: `src/features/mail-notice/tests`

関連要件:

- REQ-001 〜 REQ-012

`portal` および `schedule` の Python は import しない。`public.users` と `schedule.schedules` は読むだけ（複製しない、列を増やさない）。通知済みはスキーマ `mail_notice`。FastAPI / uvicorn は使わない。機能マスタへは登録しない。

---

## タスク 1

### タイトル

バックエンドの venv とコンソール起動口、設定、ログ初期化を用意する

### 見積もり

2時間

### 関連要件

- REQ-001, REQ-006, REQ-007, REQ-011, REQ-012

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / モジュール構成（`app/main.py`, `app/__main__.py`, `app/config.py`, `app/logger.py`）
- `api-design.md` / 概要（HTTP API なし）
- `.cursor/rules/16-logging.mdc`

### 実装パス

- `src/features/mail-notice/backend/app/main.py`
- `src/features/mail-notice/backend/app/__main__.py`
- `src/features/mail-notice/backend/app/config.py`
- `src/features/mail-notice/backend/app/logger.py`
- `src/features/mail-notice/backend/.env`（ひな型: `docs/specs/templates/backend.env.example` に SMTP と判定用設定を足す）
- `src/features/mail-notice/backend/requirements.txt`

### 内容

venv を backend 配下に作成する。作業ディレクトリ `backend` で `python -m app` が起動できるようにする。FastAPI と uvicorn は入れない。`.env` から DB、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`、`NOTICE_LEAD_MINUTES`、`NOTICE_DAY_TIME`、`NOTICE_LOOKBACK_DAYS` を読む。未設定時の既定は余裕分数 3、日単位みなし時刻 `09:00`、遡及日数 30。正の整数でない余裕分数・遡及日数、`HH:MM` でない日単位みなし時刻は既定とし、判断をログに残す（本タスクでは設定の読み取りまで。判定本体は後続）。CORS、`SESSION_TIMEOUT_MINUTES`、`DEBUG_USER` は使わない。起動時に `log/` へサイズローテーションするロガーを初期化する。`portal` を import しない。秘密情報をソースに直書きしない。SMTP パスワードはログに出さない。この時点の `main` はログ初期化のあと終了してよい（判定の接続は後続タスク）。

### 完了条件

- [ ] `backend/venv` が存在する
- [ ] 作業ディレクトリ `backend` で `python -m app` が起動し、終了する
- [ ] FastAPI / uvicorn に依存しない
- [ ] 上記の設定を `.env` から読む。未設定時の既定が設計どおりである
- [ ] 秘密情報をソースに直書きしていない。SMTP パスワードがログに無い

---

## タスク 2

### タイトル

画面なし（フロントエンドを置かない）

### 見積もり

1時間

### 関連要件

- REQ-001

### 関連設計

- `design.md` / フロントエンド設計（画面なし）
- `ui-design.md` / 概要（画面なし）
- `api-design.md` / エンドポイントなし

### 実装パス

- なし（`src/features/mail-notice/frontend` は作らない）

### 内容

フロントエンドのディレクトリ、Vue、公開 URL、機能マスタ登録を作らない。

### 完了条件

- [ ] `src/features/mail-notice/frontend` が無い
- [ ] 機能マスタに `mail-notice` を登録していない

---

## タスク 3

### タイトル

スキーマ `mail_notice` の DDL を用意し、適用する

### 見積もり

2時間

### 関連要件

- REQ-003, REQ-009, REQ-010

### 関連設計

- `db-design.md` / `mail_notice.notified_schedules`
- `design.md` / バックエンド設計 / モジュール構成（`sql/`）
- `.cursor/rules/13-db.mdc`

### 実装パス

- `src/features/mail-notice/backend/sql/`

### 内容

スキーマ `mail_notice` と `notified_schedules` を作る SQL を置く。主キー、外部キー（`schedule.schedules.id`、ON DELETE RESTRICT）、`notified_at` の既定は `db-design.md` どおり。`public` と `schedule` の表は作らない・変更しない。`tstuser` がスキーマを使えるようにする。

### 完了条件

- [ ] `db-design.md` の表・制約が SQL にある
- [ ] `tstuser` で tstdb に適用できる
- [ ] `public` と `schedule` に列・表を増やしていない

---

## タスク 4

### タイトル

DB 接続とデータアクセスを実装する

### 見積もり

3時間

### 関連要件

- REQ-002, REQ-003, REQ-004, REQ-005, REQ-008, REQ-012

### 関連設計

- `design.md` / バックエンド設計 / データアクセス
- `db-design.md` / テーブル設計

### 実装パス

- `src/features/mail-notice/backend/app/db.py`
- `src/features/mail-notice/backend/app/repos.py`

### 内容

PostgreSQL へ接続する。`schedule.schedules` から、未削除・通知要・開始日が下限より後の行を読む。所有者の `public.users`（`email`、`is_deleted`）を読む。`notified_schedules` の有無確認と、送信成功後の追加（既にある `schedule_id` は追加しない）を実装する。スケジュールとユーザは更新しない。`schedule` / `portal` の Python は import しない。

### 完了条件

- [ ] 開始日が下限より後の未削除・通知要のスケジュールを取得できる
- [ ] 所有者のメールアドレスと論理削除を読める
- [ ] 通知済みの確認と追加ができる。既にある `schedule_id` は二重追加しない
- [ ] `schedule.schedules` と `public.users` を更新しない

---

## タスク 5

### タイトル

通知対象の判定を実装する

### 見積もり

4時間

### 関連要件

- REQ-004, REQ-005, REQ-006, REQ-008, REQ-010, REQ-012

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `design.md` / バックエンド設計 / モジュール構成（`notice_service`）

### 実装パス

- `src/features/mail-notice/backend/app/services/notice_service.py`

### 内容

日本標準時の判定時刻からしきい時刻を算出し、開始日時を粒度に応じて決める。TODO は未実施も条件にする。予定は実施状態を見ない。通知済み、開始日時がしきい時刻と同じまたはそれ以降、開始日が下限以前は対象にしない。所有者論理削除またはメールアドレス空は送らず、通知済みにしない。日時の基準は日本標準時。送信そのものは次タスク。

### 完了条件

- [ ] TODO / 予定の対象条件が設計どおりである
- [ ] 日単位は日単位みなし時刻、時間単位は開始時刻を使う
- [ ] 遡及日数の下限より前（同じ日を含む）は対象にしない
- [ ] メール空・所有者論理削除は対象として送らず、通知済みにしない

---

## タスク 6

### タイトル

SMTP によるメール送信を実装する

### 見積もり

2時間

### 関連要件

- REQ-007, REQ-009

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック（SMTP、件名・本文）
- `design.md` / バックエンド設計 / モジュール構成（`mail_service`）

### 実装パス

- `src/features/mail-notice/backend/app/services/mail_service.py`

### 内容

`.env` の SMTP 設定で 1 通送る。宛先は所有者のメールアドレス。送信元は `SMTP_FROM`。件名に種別（予定または TODO）とタイトル。本文にタイトルと開始日時。日単位の開始日時は開始日に日単位みなし時刻を付けて書く。認証パスワードはログに出さない。失敗は呼び出し元が判断できる例外または戻り値にする。

### 完了条件

- [ ] SMTP 設定でメールを 1 通送れる
- [ ] 件名と本文にタイトルと開始日時がある
- [ ] SMTP パスワードがログに無い

---

## タスク 7

### タイトル

1 回の判定・送信を起動口に繋ぎ、ログを出す

### 見積もり

3時間

### 関連要件

- REQ-001, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011

### 関連設計

- `design.md` / バックエンド設計 / 起動
- `design.md` / バックエンド設計 / 業務ロジック（1 件ずつ、失敗しても次件、成功時のみ記録）
- `api-design.md` / エンドポイントなし

### 実装パス

- `src/features/mail-notice/backend/app/main.py`
- `src/features/mail-notice/backend/app/services/notice_service.py`

### 内容

`python -m app` で、対象を順に見て条件に合うものへ 1 件 1 通送り、一巡したら終了する。送信成功したときだけ `notified_schedules` に追加する。失敗した件は記録せず次へ進む。同時起動で既に記録がある件は送らない。判定開始、設定値、対象件数、各件の成否、送らない理由をログに出す。SMTP パスワードとセッション ID は出さない。プロセス内で待ち続けない。

### 完了条件

- [ ] `python -m app` が判定と送信を 1 回行い終了する
- [ ] 成功した件だけ通知済みになる。失敗した件は次回対象になり得る
- [ ] ある件の失敗が他件を止めない
- [ ] ログに入力・判断・失敗理由があり、SMTP パスワードが無い

---

## タスク 8

### タイトル

判定と送信のテストを実装する

### 見積もり

4時間

### 関連要件

- REQ-004, REQ-005, REQ-006, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012

### 関連設計

- `design.md` / バックエンド設計 / 業務ロジック
- `db-design.md` / `notified_schedules`

### 実装パス

- `src/features/mail-notice/tests/`

### 内容

`backend` の venv で pytest を実行する。SMTP は実送信せず差し替える。TODO / 予定の条件、日単位みなし時刻、余裕分数、遡及日数、通知済みの再送なし、メール空・論理削除で送らない、送信失敗時は記録しない、ログにパスワードが無いことを確認する。HTTP API テストは作らない。

### 完了条件

- [ ] `src/features/mail-notice/tests/` にテストがある
- [ ] SMTP を差し替えて、対象条件と通知済み記録を確認できる
- [ ] 送信失敗時に `notified_schedules` が増えない
- [ ] uvicorn / HTTP クライアントに依存しない

---

## テスト

### 単体テスト

- [ ] `src/features/mail-notice/tests/` に配置する
- [ ] 開始日時の算出（日単位 / 時間単位）、しきい時刻、遡及日数の下限を確認する
- [ ] TODO と予定の対象条件、通知済み除外を確認する

### 結合テスト

- [ ] DB 上の `schedules` / `users` / `notified_schedules` を使った判定（SMTP は差し替え）
- [ ] 操作ログ（入力・判断・失敗理由、SMTP パスワード非出力）

### 受け入れテスト

- [ ] requirements.md の受け入れ条件を満たす

## 承認

現在の状態: 承認済み

| 日時 | 状態 | 変更概要 |
|------|------|----------|
| 2026-08-31 23:37 | 未承認 | 初版 |
| 2026-08-31 23:38 | 承認済み | 初版を承認 |
