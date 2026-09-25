# 実機接続（Freenove ＋ ARGUS）

ARGUS が Freenove 公式クライアント（`Code/Client/Main.py`）の仕事を引き継いだので、
**公式クライアントはもう起動しない**。展示の操作は ARGUS の Web ページだけで完結する。

## 何がどこに繋がるか

```
観客のスマホ ──► B (Flask :5000)  ARGUS_backend/app.py
                    │  /pay でチケット購入 → command_queue に積む
                    │
                    ├─ C  voice/paid_only.py   ──TCP :5002──► Freenove server.py ──► 脚のサーボ
                    │     （キューを2秒ごとに取り出し CMD_MOVE 等を送る）
                    │
                    └─ B のカメラ ◄──TCP :8002── Freenove server.py（ロボット一人称の映像）
                            │   ARGUS_backend/freenove_camera.py が独自形式を復号
                            ├─► /video_feed（観客ページ・ダッシュボード）
                            └─► A  vision/detection_webcam.py（YOLO）または
                                   detection_lite.py（OpenCV内蔵・依存ゼロ）→ /upload
```

公式クライアントが握っていた **5002（命令）と 8002（映像）を、C と B が分担して引き取った**
というのが今回の統合。プロトコル自体は Freenove のまま使っているが、
サーバー側にも5箇所の修正が要る（次節のパッチ）。

> ⚠️ **Freenove サーバーは 5002 も 8002 も一度しか `accept()` しない**
> （`Code/Server/server.py` の `receive_commands` / `transmit_video`）。
> 公式クライアント `Main.py` を開いたままだと ARGUS が繋げない。**必ず閉じること。**
> 逆に、ARGUS を動かしている間は公式クライアントは使えない（調整したいときは ARGUS を止める）。

## Pi 側：先に Freenove のコードへパッチを当てる

**この作業は Pi ごとに一度だけ必要。** ARGUS を動かすには Freenove 本家の
`Code/Server` にも直しが要るが、そこは ARGUS リポジトリの外なのでバージョン
管理されていない。何をどう直すかは `tools/patch_freenove_server.py` に
実行可能な形で残してある。

```bash
# 何を直すのかを読む
python3 tools/patch_freenove_server.py --explain

# 当たっているか確認するだけ
python3 tools/patch_freenove_server.py --check

# 実際に当てる（元のファイルは .bak に退避される）
python3 tools/patch_freenove_server.py
```

何度実行しても安全（適用済みなら何もしない）。当てる内容は5つ：

| 直すところ | 直さないと起きること |
|---|---|
| `main.py` の `tcp_flag` → `is_tcp_active` | 属性名が `server.py` と食い違っていて、切断検知が働かない。受信ループが空文字を延々処理して CPU を食い潰し、**新しい接続を受け付けなくなる**（画面に `['']` が流れ続ける） |
| `main.py` の `while True: pass` | `-n` 起動時に1コアを 100% 占有 |
| `control.py` の停止判定に `angle` を追加 | その場旋回（x=0,y=0,angle≠0）が「停止」扱いされ `relax(False)` を通らないので、**脱力状態から旋回させても動かない** |
| `control.py` の `condition_monitor` に sleep | 待機中も1コアを 100% 占有 |
| `servo.py` の `set_servo_angle` で I2C エラーを捕まえる | 電圧降下の瞬間の書き込み失敗で命令受信／歩容のスレッドが死に、**繋がっているのに何を押しても動かない**状態になる（サービス再起動まで戻らない） |

> **SD カードを作り直したときは、サーボ校正値も戻すこと。** 校正値（`point.txt`）は
> この1台専用で SD カードにしか無いので、控えを [tools/pi_backup/](../tools/pi_backup/) に
> 置いてある。戻し方はそこの README。

## Pi 側：画面を開かずに起動する

GUI（あの On / Off の小さい窓）は要らない。`-t`＝TCP開始、`-n`＝GUIなし。

```bash
cd ~/Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi/Code/Server
sudo python3 main.py -t -n
```

### 電源を入れるだけで立ち上がるようにする（展示ではこれを推奨）

当日 Pi に画面やキーボードを繋がなくて済む。

```bash
sudo tee /etc/systemd/system/freenove.service > /dev/null << 'EOF'
[Unit]
Description=Freenove Hexapod Server (ARGUS backend robot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/masteren/Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi/Code/Server
# 起動時に wlan0 の IP がまだ無いと server.py の get_interface_ip が落ちるが、
# main.py 自体は生き残るので active のままポートが開かない。IP が付くまで待つ（最大60秒）。
ExecStartPre=/bin/sh -c "for i in $(seq 60); do ip -4 addr show wlan0 | grep -q inet && exit 0; sleep 1; done; exit 1"
ExecStart=/usr/bin/python3 main.py -t -n
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now freenove.service
systemctl status freenove.service       # active (running) を確認
journalctl -u freenove.service -f       # ログを追う（CMD_MOVE が流れてくる）
```

`WorkingDirectory` は **必ず実際のパスに合わせる**。Freenove のコードは
`point.txt` などを相対パスで読むので、別のディレクトリから起動すると落ちる。

## PC 側：まとめて起動する

```bash
cd ARGUS
python3 tools/run_all.py --robot 192.168.0.14 --vision
```

- `--robot <IP>` … Pi の IP。**B（カメラ）と C（命令）の両方がここを向く**
- `--vision` … A も起動（`search_person` ミッションに必要）
- `--voice` … C を音声版（`argus_voice.py`）にする。`OPENAI_API_KEY` とマイクが要る
- 省略時は Mock。実機なしで経路だけ確かめられる

ブラウザが自動で開く。Ctrl+C で全部まとめて止まる。

手で1つずつ起動したいときは従来どおり：

```bash
ARGUS_ROBOT_HOST=192.168.0.14 PORT=5000 python3 ARGUS_backend/app.py
ARGUS_ROBOT_HOST=192.168.0.14 python3 voice/paid_only.py
python3 vision/detection_webcam.py
```

## 環境変数（追加分）

| 変数 | 既定 | 効果 |
|---|---|---|
| `ARGUS_ROBOT_HOST` | 未設定 | **B**: カメラを Freenove の映像に切り替える／**C**: 命令の送信先。未設定なら B はローカルUSBカメラ、C は Mock |
| `ARGUS_ROBOT_VIDEO_PORT` | `8002` | Freenove の映像ポート。通常変えない |

`ARGUS_ROBOT_HOST` を1つ決めれば B と C が同じ Pi を向く、という形にしてある。

## つまずいたら

| 症状 | 原因と対処 |
|---|---|
| ログに `robot に接続できません` / `[SKIP] 未接続のため破棄` | **Pi 側で Freenove サーバーが動いていない。** `sudo python3 main.py -t -n` を起動する。PC から `Test-NetConnection <PiのIP> -Port 5002`（PowerShell）が `True` になれば OK。ping は通るのに拒否される＝機械は生きていてサーバーだけ落ちている |
| Web は出るが映像が真っ黒 / 500 | 公式クライアント `Main.py` が 8002 を掴んでいる → 閉じる。Pi で `main.py -t -n` が動いているか確認 |
| 映像は出るが動かない | C が動いていない、または `ARGUS_ROBOT_HOST` 未設定で Mock になっている。C のログに `🦿 [REAL]` が出るか見る |
| その場旋回しない／脱力から復帰しない | `control.py` のパッチが当たっていない。`python3 tools/patch_freenove_server.py --check` で確認 |
| 前進が止まらず歩き続ける | C が古い。`robot_bridge.py` が動作後に停止コマンドを送る版か確認（`ARGUS_MOVE_SECONDS` 秒で自動停止する） |
| 命令は届くのに脚が動かない | ロボット側の問題。Pi で `sudo python3 test.py Servo`（サーボ単体）と `sudo python3 test.py ADC`（電圧、7V以上必要）を確認 |
| 途中から何を押しても動かなくなった（Pi のログに `OSError: [Errno 121] Remote I/O error`） | **電源不足でサーボドライバ（PCA9685）が I2C から落ちた。** 歩行中の電圧降下で起きる（`dmesg` に `Undervoltage detected!`）。`patch_freenove_server.py` の5つ目が当たっていれば一瞬の失敗は飛ばして動き続ける。それでも止まったままならロボットの電源スイッチを切って5秒待って入れ直す。サービスは5秒ごとに自動で再起動を試みるので、Pi には触らなくてよい。根本対策は 5V/5A アダプタと満充電 |
| `freenove.service` は active なのに繋がらない（Pi で `sudo ss -ltn` に 5002 が無い） | 起動時に WiFi の IP がまだ無かった（ログに `OSError: [Errno 99] Cannot assign requested address`）。`sudo systemctl restart freenove.service`。上のサービス定義の `ExecStartPre`（IP が付くまで待つ）が入っているか確認 |
| `freenove.service` が起動しない（`Unit ... could not be found`） | サービス未登録。上の「電源を入れるだけで立ち上がるようにする」を実行する |
| search_person が成功しない／枠が motion しか出ない | カメラが低すぎる。`/dashboard` の「▲ カメラを上に」で調整し、C のログに出る角度を `ARGUS_HEAD_TILT` に設定する。A のログに `[detection_lite] … fps` が出ていなければ A が落ちている（`opencv-python<5` か確認） |
| 映像がカクつく | `/video_feed` は MJPEG。同時視聴が増えるほど落ちる。観客端末は1台に絞る |
| B が 5000 を開けない | macOS は AirPlay が 5000 を使う → `--port 5001` |

## 展示中の操作（2つの経路）

| | 観客 | 運営（あなた） |
|---|---|---|
| ページ | `/`（公開ページ） | `/dashboard` の「直接操作（運営用）」 |
| 経路 | `/pay` → チケット消費 | `/control` → **チケット不要** |
| 記録 | 取引履歴・ランキングに載る | **載らない**（集計が汚れない） |
| 使える動作 | forward / turn_left / turn_right / bow / wave / search_person | ＋ **back / stop / relax / head_up / head_down** |
| 連打制限 | 1.5秒 | なし |

運営側は**開演前の動作確認・ロボットの立て直し・緊急停止**に使う。観客に買わせた
チケットの集計を汚さずに何度でも試せる。

- **`停止`（赤いボタン）は溜まった未実行命令も消してから止める。** 観客が連打して
  キューに前進が5件積まれた状態でも、押せばそこで打ち切れる。**緊急停止はこれ。**
- **`脱力`** はサーボの力を抜く。展示の終わりや、脚を手で直したいときに。

**B を動かしている端末（localhost）からは常に操作できる**（トークンを設定しても
塞がりません）。観客と同じ LAN に置く以上、外部からは既定で一切受け付けません。
スタッフのスマホから操作したいときだけ：

```bash
ARGUS_STAFF_TOKEN=<合言葉> python3 tools/run_all.py --robot <PiのIP> --vision
# 操作する側は X-Staff-Token ヘッダに同じ値を入れて POST /control
```

## 展示中にロボットが落ちたら

**何もしなくていい。ページは生き続ける。**

| | 起きること |
|---|---|
| Pi が落ちた瞬間 | C のログに `接続できません` が1回出る。B・観客ページ・映像ページはそのまま |
| その間の操作 | ボタンは押せるが `[SKIP] 未接続のため破棄` になる（＝反応しないだけ） |
| Pi が戻ったら | **C が自分で繋ぎ直す**。`robot 接続成功` が出て、次の命令から普通に動く |
| 映像 | `freenove_camera.py` も同じく自動で繋ぎ直す |

以前は Pi が落ちると C がその場で例外死し、`run_all.py` が道連れで B まで畳んでいた
（＝観客のページごと消えた）。今は **B が落ちたときだけ全体を停止**し、C と A の死は
警告を出して続行する。C だけ後から起動し直すこともできる（警告に手順が出る）。

## 展示前チェック

1. Pi 電源 → `systemctl status freenove.service` が active
2. 公式クライアント `Main.py` が**閉じている**
3. PC で `python3 tools/run_all.py --robot <IP> --vision`
4. ブラウザに**ロボット視点の映像**が出る（＝8002 の取り込み成功）
5. `forward` を1回買って脚が動く（＝5002 の送信成功）
6. `search_person` を買って、人の前で検出枠が出て成功演出まで行く
7. `ARGUS_DEBUG` が設定されていないこと（同一LANにデバッガを晒さない）
