# ARGUS — 体験チケット連動型 AI 相棒ロボット

6脚ロボット（Freenove ＋ Raspberry Pi 5）を、観客が**体験チケット（模擬通貨）**で操作できる
展示作品。画像認識（A）・バックエンド＋Web（B）・音声＋実機ブリッジ（C）の3モジュールを、
**B の実装を契約の正本**として結線してある。要件は [docs/要件定義書_ARGUS_Ver1.0.md](docs/要件定義書_ARGUS_Ver1.0.md)、
インターフェースは [CONTRACT.md](CONTRACT.md) が正本。

## 構成

```
ARGUS_backend/        担当B：Flask+SQLite 後端＋取引処理＋Web（契約の正本）
  app.py
  freenove_camera.py    ← 追加：Freenove の映像(8002)を VideoCapture 互換で読むアダプタ
  templates/  static/
vision/               担当A：画像認識
  detection_webcam.py   ← 修正：/upload 対応、camera はBから取得、bbox付与
  detection_lite.py     ← 追加：YOLO無しで枠を出す軽量版（OpenCV内蔵の検出器）
  test_camera.py  test_flux.py  test_yolo_image.py
voice/                担当C：音声＋歩行ブリッジ＋統合
  argus_voice.py        ← 修正：/events を {"events":[...]} で解析
  paid_only.py          ← 追加：音声なしの C（APIキー・マイク不要。Web操作だけならこれ）
  paid_poller.py        ← 修正：port 5000、/commands を {"commands":[...]} で解析
  robot_bridge.py       ← 強化：wave/bow/search_person をFreenove照合済み命令で実装
tools/                結合スモークテスト
  run_all.py            ← 追加：B/A/C をまとめて起動しブラウザを開く
  patch_freenove_server.py ← 追加：Freenove 側に必要な修正（リポジトリ外なのでここに記録）
docs/                 設計・企画ドキュメント（→ docs/README.md）
  DEPLOY_ROBOT.md       ← 追加：実機接続の手順・systemd・トラブル対応
CONTRACT.md           正本の契約表＋残タスク（必読）
requirements.txt      依存パッケージ
```

## 統合時の決め打ち（review して翻せる）

3モジュールを繋ぐ際、どちらでも成立する分かれ道を以下のように決めた。
不都合があれば翻してよい。翻すときは CONTRACT.md も一緒に直すこと。

1. **契約の正本 = B**。実装がいちばん完全だったので B の形を基準にし、A と C を合わせた。
2. **`wave` / `bow` はジェスチャで代用**。Freenove 公式に専用命令が無いため、
   `CMD_ATTITUDE` の組み合わせで作っている（`voice/robot_bridge.py`）。
3. **カメラは B だけが開く**。A は `vision/detection_webcam.py` の
   `CAMERA_SOURCE = B_URL + "/video_feed"` で B の配信を読む。1つのカメラを2プロセスで
   奪い合わないための選択。**翻すなら**：A を `VideoCapture(0)` に戻し、B の `/video_feed`
   を止めて A が描画付きで serve する。A をローカル単体で試すだけなら `CAMERA_SOURCE = 0`。
   実機接続時はこの「B の1つのカメラ」の中身が **Freenove の映像(8002)** に差し替わる
   （`ARGUS_backend/freenove_camera.py`）。A から見た口は `/video_feed` のままなので
   **A は1行も変わらない**。
4. **`search_person` の起動トリガは `/mission/active`**。`/commands` は C が数秒で `done` に
   するので A が取り逃がす。ミッションは成功するまで active のままなので、そちらを見る。

## まず通っているか確認する（1コマンド・依存なし）

```bash
bash tools/smoketest.sh
```

実機・マイク・カメラ・OpenAI キーなしで、**三モジュールのデータ閉ループ**だけを検証する
（音声 STT/TTS は対象外）。C は書き直したコピーではなく `voice/paid_poller.py` の
`poll_paid_commands` を **そのまま import して** 回すので、本物のエンドポイントを叩いている。

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

# 3) C（音声＋チケット命令のポーリング）
cd voice && python3 argus_voice.py
```

## 実機（6脚ロボット）に繋いで動かす

**Freenove 公式クライアント（`Code/Client/Main.py`）は使わない。** その仕事＝命令(5002)と
映像(8002)を ARGUS が引き取ったので、**展示は ARGUS の Web ページだけで完結する**。
詳しい手順・systemd 設定・トラブル対応は **[docs/DEPLOY_ROBOT.md](docs/DEPLOY_ROBOT.md)**。

```bash
# Pi 側：GUI なしで起動（-t=TCP開始 -n=GUIなし）。systemd に入れれば電源だけで立ち上がる
sudo python3 Code/Server/main.py -t -n

# PC 側：B と C（と A）をまとめて起動し、ブラウザまで開く
python3 tools/run_all.py --robot <PiのIP> --vision
```

`ARGUS_ROBOT_HOST` を1つ決めると **B はカメラをロボット一人称に切り替え、C は命令の
送信先にする**。未設定なら B はローカルのUSBカメラ、C は Mock（実機なしで通しで動く）。

> ⚠️ Freenove サーバーは 5002 も 8002 も**一度しか accept しない**。公式クライアント
> `Main.py` を開いたままだと ARGUS が繋げない。必ず閉じること。

## 観客のスマホから開く（展示）

B は `0.0.0.0` で待ち受けるので、**同じ LAN なら他の端末から見える**。

```bash
ipconfig getifaddr en0        # 例: 192.168.0.2
# → スマホのブラウザで http://192.168.0.2:5000/
```

- 会場 WiFi は**クライアント隔離**が有効なことが多く、その場合スマホから PC に届かない。
  自前の携帯ルーター、またはスマホのテザリングに B を繋ぐのが確実。**当日ぶっつけ本番は避ける**。
- 展示は**運営が用意した1台のスマホ**を主端末にする想定。画面の自動ロックを切り、
  iOS はアクセスガイド／Android は画面固定でブラウザから出られないようにする。
- IP は DHCP で変わる。QRコードを作るなら当日に作り直すか、ルーターで固定する。
- `/video_feed` は MJPEG。同時視聴が増えるほどフレームレートが落ちるので、
  多数のスマホから同時に開かせる運用は事前に負荷を試すこと。

## チーム

| 担当 | 役割 | 主なファイル |
| --- | --- | --- |
| [@masteren](https://github.com/masteren)（任） | C：音声対話・実機ブリッジ・統合／リーダー | `voice/` |
| [@tsukky227](https://github.com/tsukky227) | B：バックエンド・Web・取引処理 | `ARGUS_backend/` |
| [@Hochadamas](https://github.com/Hochadamas)（ベン） | A：画像認識 | `vision/` |
| [@chibayanki](https://github.com/chibayanki) | D：観客体験・Webデザイン・展示物・テスト | `docs/roles/ARGUS_PersonD_AudienceExperience.md` |

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
