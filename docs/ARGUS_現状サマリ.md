# ARGUS 現状サマリ（AI・新メンバー向けブリーフィング）

> このファイルは「いま何がどうなっているか」を1枚で渡すためのもの。
> 詳細の正本は [CONTRACT.md](../CONTRACT.md)（API）と
> [要件定義書_ARGUS_Ver1.0.md](要件定義書_ARGUS_Ver1.0.md)（要件）。
> 最終更新：2026年9月5日

## 1. 一言で

6脚ロボット（Freenove Big Hexapod ＋ Raspberry Pi 5）を、観客が**体験チケット（模擬通貨）**を
使って数十秒だけ操作できる展示作品。HEW の主題「お金が動く Web サービス」に対する回答が
Flask＋SQLite の取引処理レイヤで、そこに画像認識と音声対話を載せている。

**歩行制御は Freenove 公式コードを無改造で使用**。自作するのは AI レイヤと IoT レイヤの2層。

## 2. チーム（4人）

| 担当 | GitHub | 役割 | ディレクトリ |
| --- | --- | --- | --- |
| A | @Hochadamas（ベン） | 画像認識（YOLO / OpenCV） | `vision/` |
| B | @tsukky227 | バックエンド・Web・取引処理 | `ARGUS_backend/` |
| C | @masteren（任・リーダー） | 音声対話・実機ブリッジ・統合 | `voice/` |
| D | @chibayanki | 観客体験・Webデザイン・展示物・テスト | （コード無し） |

## 3. 用語（これで統一する）

| 使う言葉 | 使わない言葉 | 理由 |
| --- | --- | --- |
| 体験チケット（模擬通貨） | 課金・投げ銭・◯◯円 | 実際の金銭は動かない。紙のチケットを配り、重複使用は運営が目視で確認する |
| 相棒ロボット / AI COMPANION | 監視ロボット・surveillance | 観客の相棒であって、観客を見張るものではない |
| ミッション | — | `search_person` を消費すると発生し、人物発見で成功する状態付きタスク |

## 4. 構成（B を中心とするスター型）

```
観客スマホ ──POST /pay──┐
                        ▼
A vision ──POST /upload──▶  B backend (Flask + SQLite)  ──/video_feed──▶ 公開ページ
 (YOLO)                     transactions / command_queue ──/overlay ────▶ (HUD描画)
   ▲                        detections / missions        ──/api/ranking─▶ (ボード)
   └──/video_feed───────────┤
                            │ GET /commands ─┐ POST /commands/{id}/done
                            ▼                ▼
                     C voice / poller ──▶ robot_bridge ──TCP CMD_*──▶ 6脚ロボット
```

- **A と C は直接通信しない**。すべて B 経由。B の実装が API の正本。
- **カメラは B だけが開く**。A は B の `/video_feed` を読む（デバイス競合の回避）。

## 5. 実装状況

**動いている**（`bash tools/smoketest.sh` で毎回検証できる。実機・カメラ・マイク・APIキー不要）

- ライブ配信、YOLO 人物検出 → `/upload`（bbox 付き）
- チケット消費 → 取引記録 → 命令キュー → C が実行 → 完了報告（閉ループ）
- `search_person` ミッション：消費で active → A が `/mission/active` を見て `mission_person` を上げる → success
- 公開ページの HUD 検出枠、サポーターボード（ランキング＋直近の操作、5秒ごと更新）
- スマホ縦画面レイアウト、入力検証、連打対策（同一IP 1.5秒＋未実行10件上限）、統一エラー形式
- 音声対話（STT→LLM→TTS）、音声での直接操作

**未実装（Ver1.0 の残タスク）**

- ミッション成功時の演出／チケットを使った人への通知（`/mission/latest` は用意済み、公開ページ側が未着手）
- 券番号の発行とシステム側の使用済み判定（Ver1.0 は運営の目視確認で運用する方針）
- 実機での検証：`turn_left/right` の角度符号、`wave`/`bow` の姿勢幅

## 6. 決め打ち（翻すなら CONTRACT.md も直す）

1. **API の正本 = B の実装**。A と C を B に合わせた。
2. **`wave` / `bow` はジェスチャで代用**。Freenove に専用命令が無く、`CMD_ATTITUDE` の組み合わせ。
3. **カメラは B のみが開く**。翻すなら A を `VideoCapture(0)` に戻し B の `/video_feed` を止める。
4. **ミッションの起動トリガは `/mission/active`**。`/commands` は C が数秒で `done` にするため A が取り逃がす。

## 7. 動かし方

```bash
pip install -r requirements.txt

cd ARGUS_backend && python3 app.py     # B（PORT=5001 で逃がせる。macOS は AirPlay が5000を掴む）
cd vision && python3 detection_webcam.py
cd voice && ARGUS_ROBOT_HOST=<PiのIP> python3 argus_voice.py   # 未設定なら Mock

bash tools/smoketest.sh                # 三モジュールの閉ループを1コマンドで回帰確認
```

| 環境変数 | 既定 | 用途 |
| --- | --- | --- |
| `PORT` | 5000 | B・A・C 共通 |
| `ARGUS_DB` | `ARGUS_backend/argus.db` | 使い捨てDBを指せる |
| `ARGUS_DEBUG` | 0 | **展示では必ず OFF**（同一LANにデバッガを晒さない） |
| `ARGUS_PAY_MIN_INTERVAL` | 1.5 | 同一IPからの `/pay` 最短間隔 |
| `ARGUS_ROBOT_HOST` | 未設定 | 実機のIP。未設定なら Mock |

## 8. 展示運用の前提

- **会場ローカル LAN のみ**。インターネット公開はしない。
- 観客は**運営が用意した1台のスマホ**を主端末として使う（画面の自動ロックを切り、
  アクセスガイド／画面固定でブラウザから出られないようにする）。
- 会場 WiFi は**クライアント隔離**が有効なことが多く、その場合スマホから B に届かない。
  自前の携帯ルーターかテザリングを用意し、**当日ぶっつけ本番は避ける**。
- `/video_feed` は MJPEG。同時視聴が増えるほどフレームレートが落ちる。

## 9. ドキュメントの正本関係

| 種類 | ファイル | 状態 |
| --- | --- | --- |
| API 契約 | `CONTRACT.md` | **正本**。変更は先にここを直す |
| 要件 | `docs/要件定義書_ARGUS_Ver1.0.md` | **正本**（提出物） |
| 起動・運用 | `README.md` | 最新 |
| 担当別の役割メモ | `docs/roles/*.md` | **キックオフ時点の古い資料**。「投げ銭」「Stripe」など現状と食い違う記述が残っている。役割分担の把握用に留め、仕様としては信用しない |
| 加点方針 | `docs/ARGUS_受賞作分析_改善提案_4言語.md` | 過去受賞作の分析。方針の背景として有効 |
