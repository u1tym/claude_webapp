# バックエンド実装方式

> 元Cursorルールでの適用範囲: `src/features/**/backend/**/*.py` を編集するとき

バックエンドは、`src/features/<feature-name>/backend/`に置く

## 利用技術

- フレームワーク: **fastAPI**
- 言語: **python**（引数・戻り値に型ヒントを付ける）
```python
# ❌ BAD
def get_item(item_id):
    ...

# ✅ GOOD
def get_item(item_id: int) -> Item | None:
    ...
```
- 仮想環境は、**このディレクトリ配下** に `venv/` として作る。システム Python に直接依存しない。
- その venv を有効化し、このディレクトリをカレントにして **uvicorn** を起動する（例: `uvicorn app.main:app`）。
- 機能ごとに **別プロセスの FastAPI** として動く。他機能の Python モジュールを import しない。
- 機能ごとの `app` パッケージはプロセスが違うため名前は衝突しない。

## 設定値

この機能の `backend/.env` から取得する。コードに平文で埋め込まない。

設定値として、代表的なものは以下
- 接続先DBに関する情報
- 許可するフロントのオリジン
- デバッグ実行に関する設定
- セッション有効期間（`SESSION_TIMEOUT_MINUTES`。認証する場合）
- ログのローテーション（`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`。詳細は `rules/16-logging.md`）

### CORS（許可するフロントのオリジン）

- 許可オリジンは、`CORS_ORIGINS` で具体指定する。
- カンマ区切りを可とする。
- `*` は使用しない。
- 資格情報付きリクエストを許可する（Cookie 認証のため）。

### DEBUG（デバッグ実行）

- デバッグ実行時は、`DEBUG_USER` でユーザ名を指定することで、認証を行わず、指定されたユーザとして処理する。
- 本番では空にする。詳細は `rules/14-security.md`。
