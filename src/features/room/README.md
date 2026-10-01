# ROOM（room）

自室の照明・スピーカー・玄関ドアの状態を図で確認し、そのまま切り替える機能です。機器の実体は SwitchBot 製品で、バックエンドが SwitchBot の Web API を呼んで操作します。毎日・曜日・祝日と時刻を指定した定期実行もできます。

仕様は `specs/room/`（`requirements.md`、`design.md`、`ui-design.md`、`db-design.md`、`api-design.md`、`tasks.md`）にあります。

## 構成

| 場所 | 内容 |
|------|------|
| `backend/` | FastAPI（ポート 8011）。状態取得、個別切替、一括切替、定期実行の管理の API。定期実行ジョブ（`python -m app.jobs`）も同じフォルダにある |
| `frontend/` | Vue（開発用ポート 5185）。公開 URL は `/portal_room/` |
| `tests/` | バックエンドのテスト（pytest）。フロントエンドのテストは `frontend/tests/`（vitest） |

認証は、`portal` が発行したセッション（Cookie）か、API キー（`Authorization: Bearer`）で行います。ログイン画面とメニュー画面は `portal` が担います。

## 開発環境のセットアップ

前提: 開発用 DB（`rules/13-db.md`）が起動していて、`portal` の DDL（スキーマ `public`）が適用済みであること。

### バックエンド

```powershell
cd src\features\room\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # 値を埋める（下の表）
.\venv\Scripts\python.exe sql\apply.py          # スキーマ room と表を作る（繰り返し実行してよい。既存の DB は最新の定義へ移行する）
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8011
```

`backend/.env` の主な項目（ひな型は `backend/.env.example`）:

| 項目 | 内容 |
|------|------|
| `Server`、`Port`、`Database`、`Username`、`Password` | 開発用 DB の接続情報 |
| `CORS_ORIGINS` | 許可するフロントのオリジン（開発では `http://localhost:5185`） |
| `SESSION_TIMEOUT_MINUTES` | セッションの有効期間。他機能と同じ値にする |
| `LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` | ログのローテーション（1 ファイルの上限バイト数と世代数。既定 10485760 と 5） |
| `DEBUG_USER` | 開発時だけ、認証せずにそのユーザとして処理する。本番では空にする |
| `SWITCHBOT_TOKEN`、`SWITCHBOT_SECRET` | SwitchBot Web API の認証情報（アプリの開発者向けオプションで取得） |
| `ROOM_DEVICE_INDIRECT_LIGHT_ID`、`ROOM_DEVICE_INDOOR_SPEAKER_ID`、`ROOM_DEVICE_BEDSIDE_SPEAKER_ID`、`ROOM_DEVICE_FRONT_DOOR_ID` | 各機器の SwitchBot の deviceId |
| `ROOM_SCHEDULE_GRACE_MINUTES` | 定期実行の起動遅れの猶予（分。既定 5） |
| `SWITCHBOT_TIMEOUT_SECONDS` | SwitchBot への呼び出しのタイムアウト（秒。既定 10） |
| `ROOM_SETTLE_SECONDS` | 機器を切り替えたあと、実機の反映を待って状態を取り直す最大の時間（秒。既定 5。0 は待たない）。実機は、指示してから反映されるまで少し時間がかかるため、1.5 秒おきに、目標の状態になるまで取り直す。切替の応答は、最大でこの時間だけ遅くなる |

`.env` は秘密情報を含むため、リポジトリに含めません（`backend/.gitignore` で除外済み）。

### フロントエンド

```powershell
cd src\features\room\frontend
npm install
copy .env.example .env      # VITE_API_ROOM_URL（既定 http://localhost:8011）
npm run dev                 # http://localhost:5185/portal_room/
```

## 機能マスタへの登録とメニュー割当

ROOM をメニューに出し、メニューから開けるようにするには、`portal` の運用コマンドで、機能マスタへの登録と、利用者への割当を行います。運用コマンドは Web を介さず DB を直接更新します。

実行する場所は `portal` のバックエンドです。

```powershell
cd src\features\portal\backend
```

### 1. 機能の登録

機能 ID は **`room` のままにします**。ROOM のバックエンドは、この ID の機能が利用者に割り当てられているかで、利用の可否を判定します。別の ID で登録すると、メニューに出ても、ROOM は「権限なし」になります。

```powershell
# 開発（フロントを npm run dev で動かすとき）
.\venv\Scripts\python.exe -m app.cli feature add room ROOM http://localhost:5185/portal_room/

# 本番（nginx で公開するとき。ホストは環境に合わせる）
.\venv\Scripts\python.exe -m app.cli feature add room ROOM https://example.com/portal_room/
```

- 引数は、順に、機能 ID、メニューに出すタイトル、遷移先 URL です。
- 遷移先 URL は、**末尾に `/` を付けた公開 URL** にします。末尾の `/` が無いと、nginx の 301（`/portal_room` → `/portal_room/`）でクエリが落ち、メニューが付けるキャッシュ回避のクエリ（`?a=…`）が消えます（`frontend/nginx.example.conf` の注記）。
- アイコンは省略できます（他の機能も多くは省略しています）。付けるときは、第 4 引数に、画像ファイル（png / jpg / gif / webp）のパスを渡します。画像はコマンドが DB へ格納するので、リポジトリに画像ファイルを置く必要はありません。
- 同じ機能 ID は、論理削除済みも含めて、二重に登録できません。

登録の内容を直すとき（URL の変更など）は、`update` を使います。

```powershell
.\venv\Scripts\python.exe -m app.cli feature update room --url https://example.com/portal_room/
.\venv\Scripts\python.exe -m app.cli feature update room --title ROOM --icon C:\path\to\icon.png
```

### 2. 利用者への割当

（`<` と `>` で囲んだ部分は、実際の値に書き換えて実行します。）

```powershell
# 登録済みのユーザを確認する
.\venv\Scripts\python.exe -m app.cli user list

# 割り当てる。最後の数字はメニューの表示順（小さいほど先）
.\venv\Scripts\python.exe -m app.cli menu assign <ユーザ名> room 10

# 解除する
.\venv\Scripts\python.exe -m app.cli menu unassign <ユーザ名> room
```

### 3. 確認する

1. ROOM の割当を受けたユーザで、`portal` にログインしてメニューを開く。メニューに「ROOM」が出ること。
2. 「ROOM」を選ぶと、`/portal_room/` が開き、部屋の図が表示されること。
3. ROOM を割り当てていないユーザで `/portal_room/` を開くと、内容は見えず、「この機能は利用できません」と、戻るボタンだけが出ること。

### 利用できなくなる場合

次のいずれかのとき、ROOM のバックエンドは、権限なし（403）を返し、画面は「この機能は利用できません」を示します。

- ユーザに ROOM が割り当てられていない（`menu unassign` した、または割り当てていない）。
- 機能 `room` を論理削除した（`feature delete room`）。
- ユーザを論理削除した。

## 既存の DB の移行（定期実行の改訂）

定期実行に「機器の個別切替」「祝日の扱い」「実行日の取り方」を足した版へ更新するときは、**API とジョブを入れ替える前に**、`sql\apply.py` を、もう一度実行します（本番の DB へも、同じ手順です）。

```powershell
cd src\features\room\backend
.\venv\Scripts\python.exe sql\apply.py
```

- 列の追加と、制約の付け替えを行います。**繰り返し実行してよく**、データは失われません。既存の定期実行は、「一括切替・指定した曜日のみ・当日」として、そのまま動きます。
- 従来の実行条件「祝日の指定」は廃止されました。該当する定期実行は、**無効にして、全曜日（月〜日）の「曜日の指定」へ変換されます**（意味が変わるため、勝手に動かないようにしています）。移行のあと、定期実行の画面で、内容（曜日、祝日の扱い）を見直して、有効に戻してください。「祝日だけ」に実行する条件は、新しい版では表せません。近い設定は、曜日を土・日、祝日の扱いを「祝日も実行」にした「土・日・祝日」です（平日の祝日にも実行されますが、土曜日と日曜日にも実行されます）。
- 古い API は、移行のあとも動き続けます。新しい機能は、API とジョブを入れ替えたあとから使えます。
- MCP サーバの定期実行のツールは、この版では、まだ、新しい項目に対応していません（後日対応します）。それまでは、実行条件に `holiday` を指定すると、400 になります。

## 運用

### API の起動・停止

```powershell
cd src\features\room\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8011      # 起動（開発では --reload を付けてよい）
```

- 停止は、起動した画面で Ctrl+C です。常駐させる方法（サービス化など）は、環境に合わせて決めます。
- 本番では、`.env` の `DEBUG_USER` を空にします。API を同一オリジンで中継するときは、`frontend/nginx.example.conf` の `/portal-room-api/` を使います。
- 設定値（`.env`）を変えたら、API を再起動します。

### 定期実行ジョブ

定期実行は、`python -m app.jobs` が、1 回だけ判定して終了する形です（待ち続けません）。タスクスケジューラで、**毎分**起動します。

動き:

- 有効な定期実行のうち、実行条件が予定の日付（実行日）に合い、指定時刻が、判定時刻の 5 分前（`ROOM_SCHEDULE_GRACE_MINUTES`）から判定時刻までの範囲にあるものを実行します。実行条件の判定は、次の節のとおりです。
- 実行内容は、一括切替（5 種）か、機器 1 つの個別切替（電灯、間接照明、屋内スピーカー、枕元スピーカーを ON / OFF）です。個別切替は、その機器だけに 1 回指示します（玄関ドアは対象外）。電灯は未実装のため、指示せず成功として記録します。個別切替の結果は、成功か失敗のみです。
- 同じ定期実行は、同じ日に 1 回だけ実行されます（実行記録で防ぎます）。ジョブが同時に 2 つ動いても、重複しません。
- 時刻の判定は日本標準時です。PC のタイムゾーンには左右されません。
- PC が止まっていて、猶予（5 分）を超えた分は、実行されません。
- 終了コードは、正常が 0、想定外の失敗（DB に接続できないなど）が 1 です。

#### 定期実行の設定（実行条件の考え方）

実行条件は、**毎日**、または、**曜日の指定**です（「祝日だけ」の条件はありません）。曜日の指定には、2 つの選択を付けられます。

1. 曜日（月〜日）を選びます。
2. **祝日の扱い**で、基準日になる日を決めます。
   - 指定した曜日のみ（既定）: 選んだ曜日だけ。
   - 祝日も実行: 選んだ曜日 **または** 祝日。
   - 祝日は実行しない: 選んだ曜日のうち、祝日を除く。
3. **実行日の取り方**で、実行する日を決めます。
   - 当日（既定）: 基準日に実行します。
   - の前の日: 基準日の前日に実行します（翌日が基準日である日）。
   - の次の日: 基準日の翌日に実行します（前日が基準日である日）。

例:

| 設定 | 実行する日 |
|------|------------|
| 月〜金、祝日は実行しない、当日 | 平日のうち祝日でない日 |
| 土・日、祝日も実行、の前の日 | 土曜・日曜・祝日の前日（金曜の夜、祝日の前日など） |
| 月〜金、祝日は実行しない、の前の日 | 翌日が、祝日でない平日である日（日曜〜木曜のうち、翌日が祝日でない日） |

実行日そのものは、曜日や祝日で絞りません（「の前の日」で、実行日が祝日や日曜日でも、翌日が基準日なら実行します）。祝日は、国民の祝日と振替休日です（会社の休日などは含みません）。

手動で 1 回だけ実行するとき:

```powershell
cd src\features\room\backend
.\venv\Scripts\python.exe -m app.jobs
```

> 注意: いま実行すべき定期実行があると、**実機が実際に動きます**（照明・スピーカーの切替）。玄関ドアは、定期実行の対象に含まれません。

#### タスクスケジューラへの登録

PowerShell で実行します。`$wd` は、環境に合わせて書き換えます。`pythonw.exe` を使うと、毎分の起動で黒い画面が出ません（ログはファイルに出ます）。

```powershell
$wd       = "D:\claude_code\claude_webapp\src\features\room\backend"
$action   = New-ScheduledTaskAction -Execute "$wd\venv\Scripts\pythonw.exe" -Argument "-m app.jobs" -WorkingDirectory $wd
$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "room-jobs" -Action $action -Trigger $trigger -Settings $settings `
              -Description "ROOM の定期実行ジョブ（毎分）"
```

- 作業フォルダ（`-WorkingDirectory`）は必須です。`app` パッケージを、そこから探すためです。
- この登録では、**ログオンしている間だけ**動きます。ログオンしていなくても動かすときは、タスクスケジューラの画面で、タスクのプロパティの「ユーザーがログオンしているかどうかにかかわらず実行する」を選びます（パスワードが必要です）。
- `-StartWhenAvailable` により、PC が止まっていて起動できなかった分は、PC が使えるようになったあとに、すぐ起動されます（ただし、猶予を超えた定期実行は、実行されません）。

確認・停止・削除:

```powershell
Get-ScheduledTask -TaskName room-jobs | Get-ScheduledTaskInfo     # LastRunTime と LastTaskResult（0 が正常）
Disable-ScheduledTask -TaskName room-jobs                          # 一時停止
Enable-ScheduledTask  -TaskName room-jobs                          # 再開
Unregister-ScheduledTask -TaskName room-jobs -Confirm:$false       # 削除
```

登録したら、ログ（下）に、毎分、`[job] 定期実行の判定開始` が出ていることを確認します。

同じ日に、実行済みの定期実行を、もう一度実行したいとき（実行記録を消します）:

```sql
DELETE FROM room.schedule_runs WHERE schedule_id = <定期実行の識別子> AND run_date = '<YYYY-MM-DD>';
```

### ログ

| 項目 | 内容 |
|------|------|
| 場所 | `backend/log/room.log`（API とジョブで共通。行の `[api]` と `[job]` で区別する） |
| 形式 | `日時 区分 [出力元] メッセージ`。区分は INF（正常）、WRN（想定内の失敗）、ERR（想定外の失敗）、DBG（判定の詳細） |
| ローテーション | `LOG_MAX_BYTES`（既定 10MB）を超えたら、`LOG_BACKUP_COUNT`（既定 5）世代まで残す |
| 出ない情報 | SwitchBot のトークン・シークレット、機器の識別子、セッション ID、API キー全体とそのハッシュ（API キーは、識別用の先頭 12 文字だけ） |

```powershell
Get-Content backend\log\room.log -Tail 50 -Wait -Encoding UTF8      # 流し見する
Select-String '\[job\]' backend\log\room.log | Select-Object -Last 20   # ジョブの記録だけ
```

### トラブルの切り分け

まず、`backend/log/room.log` を見ます。

| 症状 | ログの手がかりと原因 | 対処 |
|------|--------------------|------|
| 画面が「状態を取得できませんでした。」 | ブラウザの通信エラー。API が起動していない、`VITE_API_ROOM_URL` の誤り、`CORS_ORIGINS` に画面のオリジンが無い | API の起動、`frontend/.env`、`CORS_ORIGINS` を確認する |
| 全機器が「取得できません」 | `SwitchBot の認証情報が未設定`、`機器の識別子が未設定`、`HTTP エラー status=401`（トークン・シークレットの誤り）、`通信失敗 type=…` | `backend/.env` の `SWITCHBOT_TOKEN`、`SWITCHBOT_SECRET`、機器の識別子を確認して、API を再起動する |
| 一部の機器だけ「取得できません」 | `状態取得失敗 device=<機器> 理由=…`。`API エラー statusCode=161` はデバイスがオフライン、`171` は Hub がオフライン、`190` はデバイス内部エラー | SwitchBot アプリで、その機器の接続を確認する |
| 玄関ドアだけ「取得できません」 | `施錠の状態が想定外の値`（施錠が不完全な状態など） | ドアの状態を、アプリで確認する |
| 切替の直後に「状態が変わっていません」と出るが、少しあとに実機は反映されている | 実機の反映が、`ROOM_SETTLE_SECONDS`（既定 5 秒）より遅い。ログの `機器切替成功 … 取得回数=N` と、`機器切替の結果が目標と異なる` で分かる | `ROOM_SETTLE_SECONDS` を増やして、API を再起動する（特に、玄関ドアの施錠・開錠は遅い）。MCP の `WEBAPP_TIMEOUT_SECONDS`（既定 10）も、これより長くしておく |
| 切替が失敗する | `機器切替失敗 device=<機器> target=… 理由=…`（理由は上の行と同じ） | 同上。SwitchBot は 1 日 10,000 リクエストまで（超えると `HTTP エラー status=429`） |
| 「この機能は利用できません」 | `認可失敗 username=… 理由=権限なし` | 前節「機能マスタへの登録とメニュー割当」で、機能 `room` の登録と、ユーザへの割当を確認する |
| ログイン画面へ戻される | `認証失敗 理由=未ログイン`。セッションの期限切れ | 再ログインする。期間は `SESSION_TIMEOUT_MINUTES` |
| 定期実行が動かない | ① `Get-ScheduledTaskInfo` の `LastTaskResult` が 0 か。② ログに、毎分、`[job] 定期実行の判定開始` があるか。③ `判断=実行しない 理由=…` を見る | ①②が無ければ、タスクの登録・状態を確認する。③の理由は下の表 |
| ジョブの終了コードが 1 | `定期実行ジョブの失敗 理由=<例外名>`（DB に接続できないなど） | `Server`、`Port`、`Database`、`Username`、`Password` を確認する |

定期実行の「実行しない」の理由（`[job] 定期実行の判定 id=… 判断=実行しない 理由=…`）:

| 理由 | 意味 |
|------|------|
| `無効` | 定期実行が無効になっている（画面のスイッチ） |
| `時刻が範囲外` | 指定時刻が、判定時刻の 5 分前から判定時刻までの範囲に無い（正常。毎分、全件に出る） |
| `基準日でない（基準日 <日付>（<曜日>曜、祝日）は条件外 祝日の扱い=… 実行日の取り方=…）` | 実行条件に、その日が合わない。実行日から求めた基準日（「の前の日」は翌日、「の次の日」は前日）が、曜日と祝日の扱いの条件に合わない |
| `実行済み` | その日は、すでに実行している（重複の防止） |

実行したが失敗したとき（`定期実行の結果 … 結果=partial / failure 失敗した機器=[…]`。個別切替は、成功か失敗のみ）は、同じ時刻の `機器切替失敗 …` の行に、機器ごとの理由があります。画面の定期実行の一覧にも、最終実行の結果と失敗した機器が出ます。

## テスト

```powershell
# バックエンド（開発用 DB に接続する。SwitchBot はモックなので、実機は動かない）
cd src\features\room
backend\venv\Scripts\python.exe -m pytest tests

# フロントエンド
cd src\features\room\frontend
npm test            # vitest
npm run build       # 型検査（vue-tsc）とビルド
```

- バックエンドのテストは、開発用 DB にテスト用のユーザなどを作り、実行の最後に、その実行で作った分を削除します。
- 機能マスタに `room` が無いときは、テストが `room` を登録します。登録の URL は開発用（`http://localhost:5185/portal_room/`）です。実際の登録は、上の「機能の登録」で行ってください。テストは `room` を削除しません。
