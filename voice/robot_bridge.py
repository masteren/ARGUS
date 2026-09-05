# robot_bridge.py
# 歩行ブリッジ：「動作」を Freenove コマンドに変換する。上位層は send() だけを扱い、下位が Mock か実機かは意識しない。
# 【統合版】B のチケットアクション名（forward / turn_left / turn_right / bow / wave / search_person）を全てカバーする。
#   コマンド書式は Freenove 公式リポジトリ Code/Server/command.py・server.py・control.py と照合済み（2026-08）。
#   使える命令はこれだけ：CMD_MOVE / CMD_ATTITUDE(±15) / CMD_POSITION / CMD_HEAD / CMD_BUZZER / CMD_RELAX / CMD_BALANCE
#   （CMD_WAVE のような専用「動作」命令は存在しない → wave/bow はこれらを組み合わせたジェスチャで作る）

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


# ② 実機用：Freenove サーバー（ポート 5002）に接続し、公式コマンド文字列を送信する
class FreenoveBridge(RobotBridge):
    SPEED = 8          # 速度段階 2~10。8 は中速
    GAIT = "1"         # 歩容モード 1 または 2

    def __init__(self, host, port=5002):
        self.host = host
        self.port = port
        self.lock = threading.Lock()   # 音声スレッド/チケットスレッドが同時に socket へ書き込む競合を防ぐ
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))   # host = Pi の wlan0 IP（同一機での統合なら 127.0.0.1 でも可）

    # ── 低レベル送信 ──────────────────────────────
    def _raw(self, cmd: str):
        self.sock.sendall(cmd.encode("utf-8"))

    def _move(self, x=0, y=0, angle=0):
        # CMD_MOVE#歩容#x#y#速度#旋回角  （control.py の run_gait 例と一致）
        return f"CMD_MOVE#{self.GAIT}#{x}#{y}#{self.SPEED}#{angle}\n"

    # ── 単発コマンド ──────────────────────────────
    SIMPLE = {
        "forward":    lambda s: s._move(y=35),
        "back":       lambda s: s._move(y=-35),
        "turn_left":  lambda s: s._move(angle=10),    # ※左右の符号は実機で入れ替えが必要な場合あり
        "turn_right": lambda s: s._move(angle=-10),
        "stop":       lambda s: s._move(),            # すべて0 = 起立/停止
        "relax":      lambda s: "CMD_RELAX\n",
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

    def _gesture_search(self):
        # 【search_person ミッションの "移動" 部分】その場でゆっくり旋回して周囲を見回す。
        # 成功判定は A と B が担う：A が `/mission/active` を見て人物を `mission_person` で
        # 上げ、B が missions を success にする（接続済み）。ここは C の巡回モーションのみ。
        for _ in range(3):
            self._raw(self._move(angle=10)); time.sleep(1.0)
        self._raw(self._move())   # 停止

    GESTURES = {
        "bow":           _gesture_bow,
        "wave":          _gesture_wave,
        "search_person": _gesture_search,
    }

    def send(self, action: str, **kwargs):
        with self.lock:
            if action in self.SIMPLE:
                cmd = self.SIMPLE[action](self)
                self._raw(cmd)
                print(f"🦿 [REAL] robot <- {action} :: {cmd.strip()}")
            elif action in self.GESTURES:
                print(f"🦿 [REAL] robot <- {action} (gesture)")
                self.GESTURES[action](self)
            else:
                print(f"[WARN] unknown action: {action}")

    def close(self):
        self.sock.close()


# ───────── 使い方 ─────────
# 開発期（現在）：
#   from robot_bridge import MockBridge
#   bridge = MockBridge()
#
# 実機の準備ができたら、環境変数を渡すだけ（コードの編集は不要）：
#   ARGUS_ROBOT_HOST=192.168.x.x python3 argus_voice.py   # Pi の wlan0 IP
# 上位の音声コードやチケットのポーリングコードは1行も変更不要。
