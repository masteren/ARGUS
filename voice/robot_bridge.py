# robot_bridge.py
# 歩行ブリッジ：「動作」を Freenove コマンドに変換する。上位層は send() だけを扱い、下位が Mock か実機かは意識しない。

class RobotBridge:
    def send(self, action: str, **kwargs):
        raise NotImplementedError


# ① 開発用：実機に接続せず、ログ出力のみ
class MockBridge(RobotBridge):
    def send(self, action: str, **kwargs):
        print(f"🦿 [MOCK] robot <- {action} {kwargs}")


# ② 実機用：Freenove サーバー（ポート 5002）に接続し、公式コマンド文字列を送信する
#    コマンド書式はリポジトリの Code/Server/command.py + server.py + control.py と照合済み。
import socket
import threading

class FreenoveBridge(RobotBridge):
    SPEED = 8          # 速度段階 2~10。8 は中速
    GAIT = "1"         # 歩容モード 1 または 2

    def __init__(self, host, port=5002):
        self.host = host
        self.port = port
        self.lock = threading.Lock()   # 音声スレッド/課金スレッドが同時に socket へ書き込んで競合するのを防ぐ
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))   # host = Pi の wlan0 IP（同一機での統合なら 127.0.0.1 でも可）

    def _move(self, x=0, y=0, angle=0):
        # CMD_MOVE#歩容#x#y#速度#旋回角
        return f"CMD_MOVE#{self.GAIT}#{x}#{y}#{self.SPEED}#{angle}\n"

    def _build(self, action):
        if action == "forward":    return self._move(y=35)
        if action == "back":       return self._move(y=-35)
        if action == "turn_left":  return self._move(angle=10)    # ※左右の符号は実機で入れ替えが必要な場合あり
        if action == "turn_right": return self._move(angle=-10)
        if action == "stop":       return self._move()            # すべて 0 = 起立/停止
        if action == "relax":      return "CMD_RELAX\n"
        if action == "bow":        return "CMD_HEAD#1#50\n"       # 頭部を下げ、「お辞儀」ジェスチャーの代わりとする
        if action == "buzzer_on":  return "CMD_BUZZER#1\n"
        if action == "buzzer_off": return "CMD_BUZZER#0\n"
        return None

    def send(self, action: str, **kwargs):
        cmd = self._build(action)
        if cmd is None:
            print(f"[WARN] unknown action: {action}")
            return
        with self.lock:
            self.sock.sendall(cmd.encode("utf-8"))
        print(f"🦿 [REAL] robot <- {action} :: {cmd.strip()}")

    def close(self):
        self.sock.close()


# ───────── 使い方 ─────────
# 開発期（現在）：
#   from robot_bridge import MockBridge
#   bridge = MockBridge()
#
# 実機の準備ができたら、argus_voice.py 内でこの1行を差し替えるだけ：
#   from robot_bridge import FreenoveBridge
#   bridge = FreenoveBridge("192.168.x.x")   # Pi の wlan0 IP を入力
# 上位の音声コードや課金ポーリングコードは1行も変更不要。
