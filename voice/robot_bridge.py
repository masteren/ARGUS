# robot_bridge.py
# 行走桥：把"动作"翻译成 Freenove 命令。上层只认 send()，不管底层是 Mock 还是真机。

class RobotBridge:
    def send(self, action: str, **kwargs):
        raise NotImplementedError


# ① 开发用：不连实机，只打印
class MockBridge(RobotBridge):
    def send(self, action: str, **kwargs):
        print(f"🦿 [MOCK] robot <- {action} {kwargs}")


# ② 实机用：连 Freenove 服务器（端口 5002），发送官方命令字符串
#    命令格式已对照仓库 Code/Server/command.py + server.py + control.py 确认。
import socket
import threading

class FreenoveBridge(RobotBridge):
    SPEED = 8          # 速度档 2~10，8 是中速
    GAIT = "1"         # 步态模式 1 或 2

    def __init__(self, host, port=5002):
        self.host = host
        self.port = port
        self.lock = threading.Lock()   # 防止语音线/课金线同时写 socket 打架
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))   # host = Pi 的 wlan0 IP（本机集成可用 127.0.0.1）

    def _move(self, x=0, y=0, angle=0):
        # CMD_MOVE#步态#x#y#速度#转角
        return f"CMD_MOVE#{self.GAIT}#{x}#{y}#{self.SPEED}#{angle}\n"

    def _build(self, action):
        if action == "forward":    return self._move(y=35)
        if action == "back":       return self._move(y=-35)
        if action == "turn_left":  return self._move(angle=10)    # ※左右符号可能要在实机上对调
        if action == "turn_right": return self._move(angle=-10)
        if action == "stop":       return self._move()            # 全 0 = 站立/停
        if action == "relax":      return "CMD_RELAX\n"
        if action == "bow":        return "CMD_HEAD#1#50\n"       # 头部下点，权当"鞠躬"手势
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


# ───────── 用法 ─────────
# 开发期（现在）：
#   from robot_bridge import MockBridge
#   bridge = MockBridge()
#
# 实机就绪后，argus_voice.py 里只换这一行：
#   from robot_bridge import FreenoveBridge
#   bridge = FreenoveBridge("192.168.x.x")   # 填 Pi 的 wlan0 IP
# 上层语音代码、课金轮询代码一行都不用改。
