# ARGUS インターフェース契約（正本 / canonical）

> **基準 = 担当B の実装（`ARGUS_backend/app.py`）。** A と C はこれに合わせる。
> 実装済みの B が最も完全なので、B の形を「叩き台」ではなく「正本」に昇格させた。
> 変更するときは、この表を先に更新してから3モジュールを直す。

## エンドポイント（すべて B が提供 / port 5000）

| メソッド | パス | 誰が呼ぶ | リクエスト | レスポンス |
|---|---|---|---|---|
| POST | `/upload` | A → B | `{timestamp, type, confidence, image}` (+任意 `bbox`,`frame_wh`) | `{"ok":true, ...}` |
| GET  | `/events` | C, ダッシュボード | — | `{"ok":true, "events":[...]}` |
| POST | `/pay` | 観客Web → B | `{amount, action, payer_name}` | `{"ok":true, ...}` |
| GET  | `/commands` | C → B | — | `{"ok":true, "commands":[...]}` |
| POST | `/commands/{id}/done` | C → B | — | `{"ok":true}` |
| GET  | `/ranking`, `/api/ranking` | 公開ページ | — | ランキング |
| GET  | `/video_feed` | 公開ページ, **A** | — | MJPEG ストリーム |

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

### ① `search_person` ミッション閉ループ（¥500 の目玉・最後に接続）
現状：C の bridge は「巡回モーション」だけ実装。成功判定が未接続。
- **A**：`GET /commands` に `search_person` があればカメラ検出を開始し、人物を検出したら `type="mission_person"` で `/upload`。
- **B**：`mission_person` を受けたら該当ミッションを成功にし、公開ページで成功演出＋課金者へ通知。
- **C**：巡回モーション（実装済み）＋ 完了を `/commands/{id}/done`。

### ② ブラウザ HUD オーバーレイ（決済2=選択1の残り）
A は検出のたびに `bbox`,`frame_wh` を `/upload` に含める（実装済み）。
- **B（TODO）**：最新の bbox を公開ページに渡す口を作る（`/events` に bbox を含めるか、`/overlay` を新設）。
- **公開ページ（フロント）**：`/video_feed` の上に bbox を JS で描画。少し遅延するので ~1s 保持で滑らかに。

### ③ 左右の符号確認
`turn_left/right` の angle 符号は実機で反転が必要な場合あり。ベンチで1回確認。
