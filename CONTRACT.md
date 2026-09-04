# ARGUS インターフェース契約（正本 / canonical）

> **基準 = 担当B の実装（`ARGUS_backend/app.py`）。** A と C はこれに合わせる。
> 実装済みの B が最も完全なので、B の形を「叩き台」ではなく「正本」に昇格させた。
> 変更するときは、この表を先に更新してから3モジュールを直す。

## エンドポイント（すべて B が提供 / port 5000）

| メソッド | パス | 誰が呼ぶ | リクエスト | レスポンス |
|---|---|---|---|---|
| POST | `/upload` | A → B | `{timestamp, type, confidence, image}` (+任意 `bbox`,`frame_wh`) | `{"ok":true, "detection_id":N, "mission_success":bool, "mission_id":N\|null}` |
| GET  | `/events` | C, ダッシュボード | — | `{"ok":true, "events":[...]}` |
| POST | `/pay` | 観客Web → B | `{amount, action, payer_name}` | `{"ok":true, ...}` |
| GET  | `/commands` | C → B | — | `{"ok":true, "commands":[...]}` |
| POST | `/commands/{id}/done` | C → B | — | `{"ok":true}` |
| GET  | `/ranking`, `/api/ranking` | 公開ページ | — | ランキング |
| GET  | `/video_feed` | 公開ページ, **A** | — | MJPEG ストリーム |
| GET  | `/mission/active` | 公開ページ, C | — | `{"ok":true, "active":bool, "mission":{...}\|null}` |
| GET  | `/mission/latest` | 公開ページ | — | `{"ok":true, "mission":{...}\|null, "status":"active"\|"success"\|null}` |
| GET  | `/overlay` | 公開ページ | — | `{"ok":true, "bbox":[x1,y1,x2,y2]\|null, "frame_wh":[w,h]\|null, "type", "confidence", "age_sec"}` |
| GET  | `/health` | 全員 | — | `{"ok":true}` |

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

## 課金アクション名（B の menu ↔ C の bridge を一致させる）

| action | B の課金メニュー | C の bridge 実装 | 使う命令（Freenove 照合済み） |
|---|---|---|---|
| `forward` | ✓ | ✓ | `CMD_MOVE#1#0#35#8#0` |
| `turn_left` | ✓ | ✓ | `CMD_MOVE#1#0#0#8#10` |
| `turn_right` | ✓ | ✓ | `CMD_MOVE#1#0#0#8#-10` |
| `bow` | ✓ | ✓ ジェスチャ | `CMD_ATTITUDE#0#12#0`→戻す |
| `wave` | ✓ | ✓ ジェスチャ | `CMD_ATTITUDE#0#0#±12` 往復 |
| `search_person` | ✓ | △ 巡回のみ | `CMD_MOVE` 旋回（下記ミッション参照）|

（音声のみ：`back`, `stop`, `relax` も bridge にあり）

## 残タスク（統合で3方が少しずつ足す）

### ① `search_person` ミッション閉ループ（¥500 の目玉）
- **B（実装済み）**：`/pay action=search_person` で `missions` に `status='active'` の行を作る。
  `type` が `mission_` で始まる `/upload` を受けたら、最新の active ミッションを `success` にして
  `/upload` のレスポンスに `mission_success:true` を返す。状態は `/mission/active`・`/mission/latest`。
- **C（実装済み）**：巡回モーション ＋ 完了を `/commands/{id}/done`。
- **A（TODO）**：`GET /commands` に `search_person` があればカメラ検出を開始し、人物を検出したら
  `type="mission_person"` で `/upload`。← いまは A 側のこの起動トリガだけが未接続。
- **公開ページ（TODO）**：`/mission/latest` を見て成功演出＋課金者へ通知。

データ閉ループ（A の起動トリガを除く）は `bash tools/smoketest.sh` で回帰確認できる。

### ② ブラウザ HUD オーバーレイ（決済2=選択1の残り）
A は検出のたびに `bbox`,`frame_wh` を `/upload` に含める（実装済み）。
- **B（実装済み）**：`detections` に `bbox`,`frame_wh` を保存し、`GET /overlay` が最新の1件を返す。
  `/events` でも bbox はJSON文字列ではなくリストで返る。`/overlay` の `age_sec`（検出からの経過秒）を
  見れば「古い枠は消す」判断ができる。
- **公開ページ（フロント / TODO）**：`/video_feed` の上に bbox を JS で描画。少し遅延するので ~1s 保持で滑らかに。

### ③ 左右の符号確認
`turn_left/right` の angle 符号は実機で反転が必要な場合あり。ベンチで1回確認。
