# robot_bridge.py
# 行走桥：把"动作"翻译成机器人命令。上层只认 send()，不管底层。

class RobotBridge:
    def send(self, action: str, **kwargs):
        raise NotImplementedError


# 开发用：不连实机，只打印
class MockBridge(RobotBridge):
    def send(self, action: str, **kwargs):
        print(f"🦿 [MOCK] robot <- {action} {kwargs}")
