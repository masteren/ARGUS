# ARGUS インターフェース契約（正本 / canonical）

> **基準 = 担当B の実装（`ARGUS_backend/app.py`）。** A と C はこれに合わせる。
> 実装済みの B が最も完全なので、B の形を「叩き台」ではなく「正本」に昇格させた。
> 変更するときは、この表を先に更新してから3モジュールを直す。

## エンドポイント（すべて B が提供 / port 5000）

| メソッド | パス | 誰が呼ぶ | リクエスト | レスポンス |
|---|---|---|---|---|
| POST | `/upload` | A → B | `{timestamp, type, confidence, image}` (+任意 `bbox`,`frame_wh`) | `{"ok":true, "detection_id":N, "mission_success":bool, "mission_id":N\|null}` |
| GET  | `/events` | C, ダッシュボード | — | `{"ok":true, "events":[...]}` |
| POST | `/pay` | 観客Web → B | `{action, payer_name, message}` | `{"ok":true, ...}` / 未定義 action・長すぎる入力は **400** / 連打・キュー飽和は **429** |
| POST | `/control` | 運営ダッシュボード → B | `{action}` | `{"ok":true, "command_id":N, "action_label":"…", "flushed":N}` / 未定義 action は **400** / 権限なしは **403** |
| POST | `/battery` | C → B | `{load, pi}` | `{"ok":true}` / 数値でなければ **400** |
| GET  | `/battery` | 公開ページ | — | `{"ok":true, "available":bool, "load", "pi", "level":0-100, "status":"good"\|"low"\|"critical", "age_sec"}` |
| GET  | `/commands` | C → B | — | `{"ok":true, "commands":[...]}` |
| POST | `/commands/{id}/done` | C → B | — | `{"ok":true}` |
| GET  | `/ranking`, `/api/ranking` | 公開ページ | — | ランキング |
| GET  | `/api/transactions` | 公開ページ | `?limit=5` | `{"ok":true, "transactions":[...]}` 直近の取引 |
| GET  | `/video_feed` | 公開ページ, **A** | — | MJPEG ストリーム |
| GET  | `/mission/active` | 公開ページ, C | — | `{"ok":true, "active":bool, "mission":{...}\|null}` |
| GET  | `/mission/latest` | 公開ページ | — | `{"ok":true, "mission":{...}\|null, "status":"active"\|"success"\|null}` |
| GET  | `/overlay` | 公開ページ | — | `{"ok":true, "bbox":[x1,y1,x2,y2]\|null, "frame_wh":[w,h]\|null, "type", "confidence", "age_sec"}` |
| GET  | `/health` | 全員 | — | `{"ok":true}` |

> エラー応答は全経路で `{"ok":false, "error":"..."}`。未捕捉の例外も 500 でこの形に揃える。

### 環境変数

| 変数 | 既定 | 用途 |
|---|---|---|
| `PORT` | `5000` | B・A・C が同じ変数を読む。macOS の結合試験だけ `5001` に逃がす |
| `ARGUS_DB` | `ARGUS_backend/argus.db` | 使い捨てDBを指せる（スモークテスト用） |
| `ARGUS_DEBUG` | `0`（OFF） | 開発中だけ `1`。**展示では必ず OFF**（同一LANにデバッガを晒さない） |
| `ARGUS_PAY_MIN_INTERVAL` | `1.5` | 同一IPからの `/pay` の最短間隔（秒）。連打対策 |
| `ARGUS_ROBOT_HOST` | 未設定 | **実機のIP。B と C が同じ変数を読む。** C = 命令(5002)の送信先、B = カメラを Freenove の映像(8002)に切り替え＝ロボット一人称。未設定なら C は MockBridge、B はローカルUSBカメラ（どちらも実機なしで通る） |
| `ARGUS_ROBOT_VIDEO_PORT` | `8002` | Freenove の映像ポート。通常変えない |
| `ARGUS_STAFF_TOKEN` | 未設定 | `/control`（運営の直接操作）を別端末から使うための合言葉。未設定なら localhost のみ |
| `ARGUS_MOVE_SECONDS` | `2.0` | 前進・後退が続く秒数。この後 bridge が自動で停止を送る |
| `ARGUS_TURN_SECONDS` | `1.5` | 旋回が続く秒数。会場の広さに合わせて調整する |
| `ARGUS_SEARCH_STEPS` | `6` | search_person の巡回で「回る→止まって見る」を繰り返す回数。人が見つかるか運営が停止を押せば途中で終わる |
| `ARGUS_SEARCH_TURN_SECONDS` | `2.0` | 巡回1回あたり回る秒数。実測約15度/秒なので既定で1回約30度・全体で約180度 |
| `ARGUS_SEARCH_LOOK_SECONDS` | `1.5` | 巡回1回あたり止まって見る秒数（HOG は歩行中のブレた画では人を取れない） |
| `ARGUS_HEAD_TILT` | `90` | カメラ（頭）の上下角度。C が Pi に繋ぐたびにこの角度へ合わせる。50〜180 |
| `ARGUS_BATTERY_INTERVAL` | `10` | C がロボットに電圧を聞きに行く間隔（秒） |
| `ARGUS_MISSION_ACCEPT_MOTION` | 未設定 | `1` にすると動体検出でも search_person を成功にする。**人が居なくても完了しうる**ので、HOG がどうしても取れないときの最後の手段 |

### ポート（契約は 5000 のまま。環境変数で逃がせるだけ）

B の `app.py`、A の `detection_webcam.py`、C の `paid_poller.py` は同じ環境変数
`PORT` を読む（未設定なら **5000＝契約どおり**）。macOS は AirPlay レシーバーが
5000 を掴むので、ローカル結合試験だけ `PORT=5001` で逃がす。
B は `ARGUS_DB` で使い捨てDBも指定できる（未設定なら `ARGUS_backend/argus.db`）。

### DBのテーブル（4つ）

`detections`（`bbox`,`frame_wh` 列を追加）/ `transactions` / `command_queue` / `missions`

> ⚠️ **落とし穴（実際に起きていた不一致）**
> - `/events` と `/commands` は **`{"ok":true, "events/commands":[...]}` で包まれている**。裸のリストではない。C の旧コードは裸リスト前提で **クラッシュしていた** → 修正済み。
> - A の旧コードは `/detection`（存在しない）に `similarite` を送っていた → `/upload` + `confidence` に修正済み。

## アクション名（B のチケットメニュー ↔ C の bridge を一致させる）

| action | B のメニュー | C の bridge 実装 | 使う命令（Freenove 照合済み） |
|---|---|---|---|
| `forward` | ✓ | ✓ 時間制限つき | `CMD_MOVE#1#0#35#8#0` → 2秒後 `CMD_MOVE#1#0#0#8#0` |
| `turn_left` | ✓ | ✓ 時間制限つき | `CMD_MOVE#1#0#0#8#-10` → 1.5秒後 停止 |
| `turn_right` | ✓ | ✓ 時間制限つき | `CMD_MOVE#1#0#0#8#10` → 1.5秒後 停止 |
| `bow` | ✓ | ✓ ジェスチャ | `CMD_ATTITUDE#0#12#0`→戻す |
| `wave` | ✓ | ✓ ジェスチャ | `CMD_ATTITUDE#0#0#±12` 往復 |
| `search_person` | ✓ | △ 巡回のみ | `CMD_MOVE` 旋回（下記ミッション参照）|

（`back`, `stop`, `relax` は観客メニューには出さない。音声と**運営の直接操作**から使う）

> ⚠️ **移動系は「一定時間動いて自動停止」。** Freenove の `control.py` は CMD_MOVE を
> キューに残したまま繰り返し実行する設計で、公式クライアントは「キーを離したら
> 停止コマンドを送る」ことで止めている（`Main.py` の `keyReleaseEvent`）。
> ARGUS は "チケット1枚＝コマンド1回" で"離す"操作が無いため、そのまま送ると
> **永久に歩き続ける**（実機で確認済み）。`robot_bridge.py` が「離す」役を引き受け、
> `ARGUS_MOVE_SECONDS` / `ARGUS_TURN_SECONDS` 秒後に `CMD_MOVE#1#0#0#8#0` を送る。
>
> また `control.py` の停止判定は **x, y, angle の3つとも 0** で見ること。x,y だけで
> 判定すると、その場旋回（x=0,y=0,angle≠0）が停止扱いになり `relax(False)` を
> 通らず、脱力したまま動かない。実機のコードは修正済み。
>
> Freenove 側に必要な修正は `tools/patch_freenove_server.py` にまとめてある
> （Code/Server は ARGUS リポジトリ外なので、そこが唯一の記録）。

### 運営の直接操作 `/control`（展示の現場用）

観客の `/pay` とは別経路。**チケットを消費せず、transactions にもランキングにも
載らない**（`command_queue` に `source='staff'`、`transaction_id=NULL` で積むだけ）。
C から見れば `/commands` に出てくる普通の命令なので、**C と A は変更不要**。

使える action：`forward` `back` `turn_left` `turn_right` `stop` `relax` `bow` `wave` `head_up` `head_down`

`head_up` / `head_down` はカメラ（頭のサーボ 0 番）を10度ずつ上下させる（`CMD_HEAD#0#角度`、50〜180）。
低い視点では人の全身が入らず search_person が成功しないので、現場で合わせてから
C のログに出る角度を `ARGUS_HEAD_TILT` に設定すると、次回から接続時にその角度になる。

- **`stop` は未実行キューを空にしてから停止する。** そうしないと溜まった前進が
  後から動き出し、止めたはずのロボットが暴れる。緊急停止として使えるようにした。
- **C 側も協力が要る。** C は `GET /commands` で複数件をまとめて受け取るため、
  その一覧は DB と切り離される。停止で DB を書き換えても手元のバッチは止まらない
  ので、`paid_poller` は 2件目以降を送る直前に「まだ pending か」を確認し、
  取り消されていたら残りを破棄してすぐ再取得する。
  **ここを外すと緊急停止が効かなくなる**（Codex の指摘で発覚）。
  なお、送信済みの1件目は取り消せない（ロボットには既に届いている）。
- 権限：**localhost は常に許可**。運営が操作するのはそこなので、ここを塞ぐと
  ダッシュボードのボタンが全部 403 になる（ブラウザの fetch はトークンを
  送らないため）。別端末から操作したいときだけ `ARGUS_STAFF_TOKEN` を設定し、
  同じ値を `X-Staff-Token` ヘッダで送る。未設定なら外部からは一切操作できない。
- UI は `/dashboard` の「直接操作（運営用）」。

## やりたいこと（未着手）

### ⓪ 公式クライアントと ARGUS の同時接続（TCP 中継プロキシ）
**現状：できない。** Freenove の `server.py` は `receive_commands` / `transmit_video` の
どちらも `accept()` を一度しか呼ばないため、5002 も 8002 も**クライアント1つ限り**。
公式クライアント `Main.py` を開くと ARGUS が繋げず、逆もまた同じ。
そのため今は「調整するときは ARGUS を止めて公式クライアント、展示のときは逆」という
切り替え運用になっている。姿勢調整・キャリブレーション・LED・ブザー・超音波は
公式クライアントにしか無いので、調整のたびに切り替えるのが面倒。

**やるなら**：Pi の上に中継プロキシを置く。

```
公式クライアント Main.py ──┐
                            ├──→ プロキシ(5002/8002) ──→ 実サーバー(15002/18002)
ARGUS の B と C         ──┘
```

- **命令(5002)**：複数クライアントからの命令をまとめて実サーバーへ。
  実サーバーからの応答（CMD_POWER の電圧など）は全クライアントへ配る。
- **映像(8002)**：`[4バイト長][JPEG]` を**フレーム単位で解析してから**各クライアントへ
  複製する。バイト列をそのまま流すと、途中から繋いだクライアントがフレームの
  途中から受け取って壊れる。解析コードは `ARGUS_backend/freenove_camera.py` に
  あるものが流用できる。
- 実サーバー側は `server.py` の `start_server()` でポートを 15002/18002 に変える（2行）。

**規模**：プロキシ 200行程度 ＋ server.py 2行。**展示直前には入れないこと**
（動いている経路に新しい部品を挟む変更なので、試す時間が取れるときに）。

## 残タスク（統合で3方が少しずつ足す）

### ① `search_person` ミッション閉ループ（¥500 の目玉）
- **B（実装済み）**：`/pay action=search_person` で `missions` に `status='active'` の行を作る。
  `type` が `mission_` で始まる `/upload` を受けたら、最新の active ミッションを `success` にして
  `/upload` のレスポンスに `mission_success:true` を返す。状態は `/mission/active`・`/mission/latest`。
- **C（実装済み）**：巡回モーション ＋ 完了を `/commands/{id}/done`。
- **A（実装済み）**：`GET /mission/active` を2秒間隔で確認し、active の間に人物を検出したら
  `type="mission_person"` で即 `/upload`（throttle をかけない・1ミッション1回だけ）。
  **`/commands` ではなく `/mission/active` を見る**：C が数秒でコマンドを `done` にするため、
  `/commands` を見ていると A が起動トリガを取り逃がす。ミッションは成功するまで active のまま。
- **公開ページ（TODO）**：`/mission/latest` を見て成功演出＋チケットを使った人へ通知。

> ⚠️ **成功にできるのは「人」と判定できたときだけ。** B は `mission_` で始まる
> `/upload` を無条件で成功扱いにするので、検出側で絞らないと歯止めが無い。
> `detection_lite.py` の motion（背景差分）は動いた塊を返すだけで人とは限らず、
> カメラの揺れやロボット自身の移動でも出る。これで成功にすると**人が居なくても
> ¥500 のミッションが完了してしまう**（Codex の指摘で発覚）。
> したがって `label == "person"` のときだけ `mission_person` を送る。
> motion しか使えない環境では search_person は自動成功しない。
> どうしても演出として成立させたい場合だけ `ARGUS_MISSION_ACCEPT_MOTION=1`。

データ閉ループ（A の起動トリガを除く）は `bash tools/smoketest.sh` で回帰確認できる。

### ② ブラウザ HUD オーバーレイ（決済2=選択1の残り）
A は検出のたびに `bbox`,`frame_wh` を `/upload` に含める（実装済み）。
- **B（実装済み）**：`detections` に `bbox`,`frame_wh` を保存し、`GET /overlay` が最新の1件を返す。
  `/events` でも bbox はJSON文字列ではなくリストで返る。`/overlay` の `age_sec`（検出からの経過秒）を
  見れば「古い枠は消す」判断ができる。
- **公開ページ（実装済み）**：`templates/public.html` の `<canvas id="hud">` が `/overlay` を
  0.4秒間隔で読み、`object-fit: cover` と同じ座標変換で枠を描く。`age_sec > 1.5` の枠は描かず、
  古くなるほど薄くしてちらつきを抑える。

### ③ 左右の符号確認 — **完了（2026-09 実機で確認）**
実機では最初 **左右が逆だった**ので `robot_bridge.py` で入れ替え済み。
確定した対応：**`CMD_MOVE` の angle は 正 = 右回り / 負 = 左回り。**

```
turn_left  → CMD_MOVE#1#0#0#8#-10
turn_right → CMD_MOVE#1#0#0#8#10
```

## バッテリー表示（2026-09 追加）

ロボットの電圧を知れるのは **C だけ**。5002 の TCP 接続を握っているのが C であり、
Freenove は `CMD_POWER` を受けると `CMD_POWER#<負荷側>#<Pi側>` を返す仕様のため。
B は自力では電圧を取れないので、経路はこうなる：

```
C: bridge.query_power() ──CMD_POWER──→ Freenove
                        ←─7.71/7.82──
C: POST /battery ──→ B（メモリに最新値だけ保持。瞬時値なので DB には残さない）
                        ←── GET /battery ── 公開ページ（5秒ごと）
```

- **2系統ある**：`load` = サーボ側、`pi` = ラズパイ側。どちらか低い方で判定する。
- **しきい値**：`good` ≥ 7.2V / `low` ≥ 6.6V / `critical` < 6.6V。
  Freenove 自体のブザー警告は 負荷<5.5V・Pi<6V なので、**それより手前**で色を変える。
  展示の途中で落ちるより、早めに気づいて交換したい。
- **`age_sec` を必ず見ること**。C が落ちると値が更新されなくなる。公開ページは
  60秒より古い値を「---」に戻す（古い電圧を正しい値として見せない）。
- `query_power()` は bridge の lock を取る。前進コマンドは2秒 sleep するので、
  その間は電圧取得が待たされる。既定の10秒間隔なら実用上の問題は無い。
