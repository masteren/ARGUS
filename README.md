# ARGUS — 体験チケット連動型 AI 監視ロボット

6脚ロボット（Freenove ＋ Raspberry Pi 5）を、観客が**体験チケット（模擬通貨）**で操作できる
展示作品。画像認識（A）・バックエンド＋Web（B）・音声＋実機ブリッジ（C）の3モジュールを、
**B の実装を契約の正本**として結線してある。要件は [要件定義書_ARGUS_Ver1.0.md](要件定義書_ARGUS_Ver1.0.md)、
インターフェースは [CONTRACT.md](CONTRACT.md) が正本。

## 構成

```
ARGUS_backend/        担当B：Flask+SQLite 後端＋取引処理＋Web（契約の正本）
  app.py
  templates/  static/
vision/               担当A：画像認識
  detection_webcam.py   ← 修正：/upload 対応、camera はBから取得、bbox付与
  test_camera.py  test_flux.py  test_yolo_image.py
voice/                担当C：音声＋歩行ブリッジ＋統合
  argus_voice.py        ← 修正：/events を {"events":[...]} で解析
  paid_poller.py        ← 修正：port 5000、/commands を {"commands":[...]} で解析
  robot_bridge.py       ← 強化：wave/bow/search_person をFreenove照合済み命令で実装
CONTRACT.md           正本の契約表＋残タスク（必読）
```

## 私（Claude）が決め打ちした箇所（review して翻せる）

1. **契約の正本 = B**。A と C を B に合わせた。
2. **決策1**：`wave` は保留し、体を振るジェスチャで実装。`search_person` は巡回モーションだけ実装し、成功判定は CONTRACT.md ①で TODO。
3. **決策2 = 選択1**：カメラは **B のみが開く**。A は `vision/detection_webcam.py` の `CAMERA_SOURCE = B_URL + "/video_feed"` でBから取得。ローカル単体テストは `CAMERA_SOURCE = 0` に戻す。

翻したいとき：決策2を選択2にするなら A を `VideoCapture(0)` に戻し B の `/video_feed` を止めて A が描画付きで serve する。

## まず通っているか確認する（1コマンド・依存なし）

```bash
bash tools/smoketest.sh
```

実機・マイク・カメラ・OpenAI キーなしで、**三モジュールのデータ閉ループ**だけを検証する
（音声 STT/TTS は対象外）。C は書き直したコピーではなく `voice/paid_poller.py` の
`poll_paid_commands` を **そのまま import して** 回すので、本物の接口を叩いている。

検証する経路：
`/pay` → `/commands` → C の bridge → `/commands/{id}/done` →
`/pay search_person` → `/mission/active` → `/upload type=mission_person` →
`mission_success` / `/mission/latest` / `/overlay` → `/api/ranking`

各ステップに ✓ / ✗ を出し、1つでも落ちれば終了コードは非0。終了時に B を停止し、
使い捨てDB（`ARGUS_backend/argus.smoketest.db`）を消すので、本番の `argus.db` は触らない。
既定ポートは **5001**（macOS の AirPlay レシーバーが 5000 を掴むため）。
5001 も塞がっていたら `PORT=5003 bash tools/smoketest.sh`。

## 準備（初回だけ）

```bash
pip install -r requirements.txt      # 自分の担当分だけで良ければ中のコメント参照
```

C（音声）を動かす人は `OPENAI_API_KEY` も設定する。B とスモークテストは Flask と
requests だけで動く（カメラ・マイク・APIキー不要）。

## 動かし方（統合テスト・全部同じPCでOK）

```bash
# 1) B（後端＋Web＋video_feed）
cd ARGUS_backend && python3 app.py            # → http://localhost:5000
# macOS で 5000 が AirPlay に取られている場合： PORT=5001 python3 app.py
#   （A の detection_webcam.py と C の paid_poller.py も同じ PORT を読む）
# 開発中にトレースバックが欲しいときだけ： ARGUS_DEBUG=1 python3 app.py
#   ※ 展示では必ず OFF。同一LANの全員に Werkzeug デバッガ（＝任意コード実行）が開く。

# 2) A（検出。Bのカメラを共有）
cd vision && python3 detection_webcam.py

# 3) C（音声＋課金ポーリング）
cd voice && python3 argus_voice.py
```

実機（Pi）へ移すとき：`voice/argus_voice.py` の `bridge = MockBridge()` を
`bridge = FreenoveBridge("<PiのIP>")` に差し替える1行だけ。

## 観客のスマホから開く（展示）

B は `0.0.0.0` で待ち受けるので、**同じ LAN なら他の端末から見える**。

```bash
ipconfig getifaddr en0        # 例: 192.168.0.2
# → スマホのブラウザで http://192.168.0.2:5000/
```

- 会場 WiFi は**クライアント隔離**が有効なことが多く、その場合スマホから PC に届かない。
  自前の携帯ルーター、またはスマホのテザリングに B を繋ぐのが確実。**当日ぶっつけは危険**。
- 展示は**運営が用意した1台のスマホ**を主端末にする想定。画面の自動ロックを切り、
  iOS はアクセスガイド／Android は画面固定でブラウザから出られないようにする。
- IP は DHCP で変わる。QRコードを作るなら当日に作り直すか、ルーターで固定する。
- `/video_feed` は MJPEG。同時視聴が増えるほどフレームレートが落ちるので、
  多数のスマホから同時に開かせる運用は事前に負荷を試すこと。

## ブランチ運用

`main` が唯一の統合先。`integration` と `voice` は main に取り込み済みのため削除した。

```bash
git checkout -b <feature-branch>     # 担当ごとの作業ブランチ
bash tools/smoketest.sh              # ALL GREEN を確認してから
# GitHub で main への Pull Request（または main に直接 merge）
```

作業前に `git pull` で main を最新にすること。`ImageRecognition/feature` は main と
共通の祖先を持たない独立ブランチなので、そのまま merge せず担当A と相談して取り込む。

`voice/fake_backend.py` は本物のBに置き換わったので削除済み
（オフライン単体テストが要るならモックを別途用意する）。
