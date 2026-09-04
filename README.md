# ARGUS — 統合ツリー / 整合树

3モジュールを実際に対話できるよう、契約を B に揃えて整合したもの。
`frontend-argus` ブランチ（B後端＋A検測＋C語音が同居）をベースに、対接ミスを修正した。

## 構成

```
ARGUS_backend/        担当B：Flask+SQLite 後端＋決済＋Web（変更なし・正本）
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

## 動かし方（統合テスト・全部同じPCでOK）

```bash
# 1) B（後端＋Web＋video_feed）
cd ARGUS_backend && python3 app.py            # → http://localhost:5000
# macOS で 5000 が AirPlay に取られている場合： PORT=5001 python3 app.py
#   （A の detection_webcam.py と C の paid_poller.py も同じ PORT を読む）

# 2) A（検出。Bのカメラを共有）
cd vision && python3 detection_webcam.py

# 3) C（音声＋課金ポーリング）
cd voice && python3 argus_voice.py
```

実機（Pi）へ移すとき：`voice/argus_voice.py` の `bridge = MockBridge()` を
`bridge = FreenoveBridge("<PiのIP>")` に差し替える1行だけ。

## main へのマージ手順（case: あなたが review 後に push）

```bash
git checkout frontend-argus
# このツリーの3ファイルを反映（backend は変更なし）
#   vision/detection_webcam.py, voice/{argus_voice,paid_poller,robot_bridge}.py
#   ＋ CONTRACT.md, README.md
git add -A && git commit -m "integrate: align A/C to B contract, fix /upload+/events+/commands, add wave/bow"
# 全線で1回通ったら：
git checkout main && git merge frontend-argus
```

`voice/fake_backend.py` は本物のBに置き換わったので統合ツリーからは外した
（オフライン単体テスト用に voice ブランチには残してよい）。
