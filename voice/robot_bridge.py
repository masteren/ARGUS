# robot_bridge.py
# 歩行ブリッジ：「動作」を Freenove コマンドに変換する。上位層は send() だけを扱い、下位が Mock か実機かは意識しない。
# 【統合版】B のチケットアクション名（forward / turn_left / turn_right / bow / wave / search_person）を全てカバーする。
#   コマンド書式は Freenove 公式リポジトリ Code/Server/command.py・server.py・control.py と照合済み（2026-08）。
#   使える命令はこれだけ：CMD_MOVE / CMD_ATTITUDE(±15) / CMD_POSITION / CMD_HEAD / CMD_BUZZER / CMD_RELAX / CMD_BALANCE
#   （CMD_WAVE のような専用「動作」命令は存在しない → wave/bow はこれらを組み合わせたジェスチャで作る）

import os
import socket
import threading
import time


class RobotBridge:
    def send(self, action: str, **kwargs):
        raise NotImplementedError


# ① 開発用：実機に接続せず、ログ出力のみ
class MockBridge(RobotBridge):
    def send(self, action: str, **kwargs):
        print(f"🦿 [MOCK] robot <- {action} {kwargs}")

    def query_power(self, timeout=2.0):
        """実機なしでも電圧表示の経路を通せるよう、それらしい値を返す。"""
        return 7.6, 7.8


# ② 実機用：Freenove サーバー（ポート 5002）に接続し、公式コマンド文字列を送信する
class FreenoveBridge(RobotBridge):
    SPEED = 8          # 速度段階 2~10。8 は中速
    GAIT = "1"         # 歩容モード 1 または 2

    RECONNECT_MIN_INTERVAL = 2.0   # 失敗直後に毎回繋ぎ直しに行かないための間隔（秒）
    CONNECT_TIMEOUT = 3.0          # Pi が落ちているとき connect で長く固まらないように

    # ── 頭（カメラ）の上下 ──────────────────────────
    # カメラは頭に付いていて、頭の上下はサーボ 0 番（CMD_HEAD#0#角度）。
    # 範囲は公式クライアント Main.py のスライダーと同じ 50〜180、既定 90。
    # （Freenove の protocol.md は「0=水平, -90〜90」と書いているが、実際に動く
    #   Main.py と server.py は 0=上下・0〜180 の生角度。こちらに合わせる）
    # 6脚の低い視点では人の全身が入らず HOG が取れないので、上に向けて使う。
    # 接続のたびに ARGUS_HEAD_TILT の角度へ合わせ直す（Pi 再起動で 90 に戻るため）。
    HEAD_CHANNEL = 0
    HEAD_MIN, HEAD_MAX = 50, 180
    HEAD_STEP = 10
    # 角度を増やす = 上を向く（2026-09-23 実機で確認済み）。勝手に入れ替えないこと。
    HEAD_UP_SIGN = 1

    def __init__(self, host, port=5002):
        self.host = host
        self.port = port
        self.head_angle = self._clamp_head(int(os.environ.get("ARGUS_HEAD_TILT", "90")))
        self.lock = threading.Lock()   # 音声スレッド/チケットスレッドが同時に socket へ書き込む競合を防ぐ
        self.sock = None
        self._last_attempt = 0.0
        self._warned = False

        # 起動時に一度繋ぎに行くが、**失敗しても例外にしない**。
        # 以前はここで connect が落ちると C のプロセスごと死に、run_all.py が
        # 巻き添えで B まで止めていた（＝展示中に Pi が一瞬落ちると観客ページごと消える）。
        # 今は未接続のまま起動し、命令のたびに繋ぎ直す。
        self._ensure_connected()

    # ── 接続管理 ──────────────────────────────
    def _ensure_connected(self):
        """繋がっていれば True。切れていれば繋ぎ直しを試みる。"""
        if self.sock is not None:
            return True

        now = time.time()
        if now - self._last_attempt < self.RECONNECT_MIN_INTERVAL:
            return False          # 直前に失敗したばかり。毎回待たされないよう見送る
        self._last_attempt = now

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.CONNECT_TIMEOUT)
            sock.connect((self.host, self.port))   # host = Pi の wlan0 IP（同一機なら 127.0.0.1 でも可）
            sock.settimeout(None)
            self.sock = sock
            self._warned = False
            print(f"🦿 [REAL] robot 接続成功 {self.host}:{self.port}", flush=True)
            # 頭の角度を合わせ直す。失敗しても接続自体は生かす（次の命令で気づく）。
            try:
                sock.sendall(self._head_cmd().encode("utf-8"))
            except OSError:
                pass
            return True
        except OSError as e:
            if not self._warned:
                # 繋がらない間は毎回吠えない。復旧したら上の行が出る。
                print(
                    f"🦿 [REAL] robot に接続できません（{self.host}:{self.port} / {e}）。"
                    "Pi で `sudo python3 main.py -t -n` が動いているか確認してください。"
                    "接続できるまで命令は捨てられます（Bとページは動き続けます）。",
                    flush=True,
                )
                self._warned = True
            return False

    def _drop_socket(self):
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    # ── 低レベル送信 ──────────────────────────────
    def _raw(self, cmd: str):
        """送れたら True。未接続・送信失敗なら False（例外は投げない）。"""
        if not self._ensure_connected():
            return False
        try:
            self.sock.sendall(cmd.encode("utf-8"))
            return True
        except OSError as e:
            print(f"🦿 [REAL] 送信失敗（{e}）。次の命令で繋ぎ直します。", flush=True)
            self._drop_socket()
            return False

    def _move(self, x=0, y=0, angle=0):
        # CMD_MOVE#歩容#x#y#速度#旋回角  （control.py の run_gait 例と一致）
        return f"CMD_MOVE#{self.GAIT}#{x}#{y}#{self.SPEED}#{angle}\n"

    # ── 時間制限つき移動 ──────────────────────────
    # 【重要】Freenove の control.py は CMD_MOVE をキューに残したまま繰り返し実行する。
    # 公式クライアントは「キーを押している間だけ歩き、離したら停止コマンドを送る」
    # 前提なので、それで辻褄が合っている（Main.py の keyReleaseEvent）。
    # ARGUS は「チケット1枚＝コマンド1回」で"離す"操作が存在しないため、
    # 素直に送ると **止まらずに歩き続ける**（実機で確認済み）。
    # そこでここが「離す」役をやる：一定時間動かしてから停止コマンドを送る。
    # control.py 側は x=y=angle=0 を受けるとキューを空にするので、そこで止まる。
    MOVE_SECONDS = float(os.environ.get("ARGUS_MOVE_SECONDS", "2.0"))   # 前進・後退
    TURN_SECONDS = float(os.environ.get("ARGUS_TURN_SECONDS", "1.5"))   # 旋回

    MOVES = {
        "forward":    (dict(y=35),      MOVE_SECONDS),
        "back":       (dict(y=-35),     MOVE_SECONDS),
        # 符号は実機で確認済み（2026-09）。CMD_MOVE の angle は
        # 正 = 右回り / 負 = 左回り。CONTRACT.md の残タスク③はこれで解決。
        "turn_left":  (dict(angle=-10), TURN_SECONDS),
        "turn_right": (dict(angle=10),  TURN_SECONDS),
    }

    def _clamp_head(self, angle):
        return max(self.HEAD_MIN, min(self.HEAD_MAX, angle))

    def _head_cmd(self):
        return f"CMD_HEAD#{self.HEAD_CHANNEL}#{self.head_angle}\n"

    def _tilt_head(self, direction):
        """direction=+1 で上、-1 で下へ1段。新しい角度の CMD_HEAD を返す。"""
        self.head_angle = self._clamp_head(
            self.head_angle + direction * self.HEAD_UP_SIGN * self.HEAD_STEP)
        print(f"🦿 [REAL] カメラ角度 = {self.head_angle}"
              f"（次回から固定するなら ARGUS_HEAD_TILT={self.head_angle}）", flush=True)
        return self._head_cmd()

    # ── 単発コマンド（送って終わり）────────────────
    SIMPLE = {
        "stop":       lambda s: s._move(),            # すべて0 = 起立/停止
        "relax":      lambda s: "CMD_RELAX\n",
        "head_up":    lambda s: s._tilt_head(+1),
        "head_down":  lambda s: s._tilt_head(-1),
    }

    # ── ジェスチャ（複数コマンドの連続。lock を保持したまま実行し、途中で音声/チケット命令が割り込まないようにする）──
    def _gesture_bow(self):
        # お辞儀：体を前傾（pitch+）→ 戻す。CMD_ATTITUDE#roll#pitch#yaw、各±15。
        self._raw("CMD_ATTITUDE#0#12#0\n"); time.sleep(0.8)
        self._raw("CMD_ATTITUDE#0#0#0\n")

    def _gesture_wave(self):
        # 手を振る代わりに体を左右に振る（yaw を ±で往復）。腕は無いのでこれで「挨拶」を表現。
        for _ in range(2):
            self._raw("CMD_ATTITUDE#0#0#12\n");  time.sleep(0.4)
            self._raw("CMD_ATTITUDE#0#0#-12\n"); time.sleep(0.4)
        self._raw("CMD_ATTITUDE#0#0#0\n")

    # search_person の巡回：「少し回る → 止まって見る」を繰り返す。
    # 以前は 1秒×3回 回るだけで、実機では約45度しか向きが変わらず
    # 「押しても探していない」ように見えた（2026-09-23 実機）。
    # 実測でおよそ 15度/秒（angle=10, SPEED=8）。既定の 2秒×6回 で約180度。
    # 止まる時間を挟むのは、HOG が歩行中のブレた画では人を取れないのと、
    # サーボに休みを与えて電圧降下（Pi の Undervoltage）を和らげるため。
    SEARCH_STEPS = int(os.environ.get("ARGUS_SEARCH_STEPS", "6"))
    SEARCH_TURN_SECONDS = float(os.environ.get("ARGUS_SEARCH_TURN_SECONDS", "2.0"))
    SEARCH_LOOK_SECONDS = float(os.environ.get("ARGUS_SEARCH_LOOK_SECONDS", "1.5"))

    def _gesture_search(self, should_stop=None):
        # 【search_person ミッションの "移動" 部分】その場で旋回して周囲を見回す。
        # 成功判定は A と B が担う：A が `/mission/active` を見て人物を `mission_person` で
        # 上げ、B が missions を success にする（接続済み）。ここは C の巡回モーションのみ。
        #
        # should_stop() が True を返したら途中でやめる（人が見つかった／運営が停止を
        # 押した）。これが無いと巡回の間ずっと lock を握るので、停止ボタンが
        # 巡回の終わりまで効かない。
        for step in range(self.SEARCH_STEPS):
            if should_stop is not None and should_stop():
                print(f"🦿 [REAL] search_person 巡回を {step}/{self.SEARCH_STEPS} で終了",
                      flush=True)
                break
            self._raw(self._move(angle=10))
            time.sleep(self.SEARCH_TURN_SECONDS)
            self._raw(self._move())   # 止まって見る
            time.sleep(self.SEARCH_LOOK_SECONDS)
        self._raw(self._move())   # 停止

    GESTURES = {
        "bow":           _gesture_bow,
        "wave":          _gesture_wave,
        "search_person": _gesture_search,
    }

    def send(self, action: str, **kwargs):
        with self.lock:
            if action in self.MOVES:
                params, seconds = self.MOVES[action]
                cmd = self._move(**params)
                if not self._raw(cmd):
                    print(f"🦿 [SKIP] 未接続のため破棄: {action}", flush=True)
                    return
                print(f"🦿 [REAL] robot <- {action} :: {cmd.strip()} ({seconds}秒)",
                      flush=True)
                time.sleep(seconds)
                # ここが公式クライアントの「キーを離す」に相当する。
                # これを送らないと control.py がキューに命令を残したまま歩き続ける。
                self._raw(self._move())
                print(f"🦿 [REAL] robot <- stop :: {action} 終了", flush=True)
            elif action in self.SIMPLE:
                cmd = self.SIMPLE[action](self)
                # 送れたときだけ「送った」と出す。未接続なのに成功したように
                # 見えると、ロボットが動かない原因を追えなくなる。
                if self._raw(cmd):
                    print(f"🦿 [REAL] robot <- {action} :: {cmd.strip()}", flush=True)
                else:
                    print(f"🦿 [SKIP] 未接続のため破棄: {action}", flush=True)
            elif action in self.GESTURES:
                # ジェスチャは複数コマンドの連続。1発目が通らないなら諦める
                # （途中まで送って変な姿勢で止まるのを避ける）。
                if not self._ensure_connected():
                    print(f"🦿 [SKIP] 未接続のため破棄: {action}", flush=True)
                    return
                print(f"🦿 [REAL] robot <- {action} (gesture)", flush=True)
                if action == "search_person":
                    self._gesture_search(should_stop=kwargs.get("should_stop"))
                else:
                    self.GESTURES[action](self)
            else:
                print(f"[WARN] unknown action: {action}", flush=True)

    # ── 電圧の問い合わせ ──────────────────────────
    def query_power(self, timeout=2.0):
        """バッテリー電圧を聞く。(負荷側, Pi側) のタプル、取れなければ None。

        Freenove の server.py は CMD_POWER を受けると
            CMD_POWER#7.71#7.82\\n
        を返す（adc.read_battery_voltage の2値）。応答を返すコマンドは
        CMD_POWER と CMD_SONIC だけなので、ここで読めるのはほぼ電圧行だが、
        混ざっても困らないよう行ごとに見て CMD_POWER だけ拾う。

        送信と受信を lock の中でまとめて行う。そうしないと別スレッドの
        移動コマンドが間に割り込み、応答の対応関係が崩れる。
        """
        with self.lock:
            if not self._raw("CMD_POWER\n"):
                return None

            deadline = time.time() + timeout
            buf = ""
            try:
                self.sock.settimeout(timeout)
                while time.time() < deadline:
                    chunk = self.sock.recv(1024).decode("utf-8", errors="replace")
                    if not chunk:
                        self._drop_socket()
                        return None
                    buf += chunk
                    for line in buf.split("\n"):
                        parts = line.strip().split("#")
                        if parts[0] == "CMD_POWER" and len(parts) >= 3:
                            try:
                                return float(parts[1]), float(parts[2])
                            except ValueError:
                                pass
            except (OSError, socket.timeout):
                return None
            finally:
                try:
                    if self.sock is not None:
                        self.sock.settimeout(None)
                except OSError:
                    pass
        return None

    def close(self):
        self._drop_socket()


# ───────── 使い方 ─────────
# 開発期（現在）：
#   from robot_bridge import MockBridge
#   bridge = MockBridge()
#
# 実機の準備ができたら、環境変数を渡すだけ（コードの編集は不要）：
#   ARGUS_ROBOT_HOST=192.168.x.x python3 argus_voice.py   # Pi の wlan0 IP
# 上位の音声コードやチケットのポーリングコードは1行も変更不要。
