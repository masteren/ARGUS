from robot_bridge import MockBridge
from paid_poller import poll_paid_commands

bridge = MockBridge()
poll_paid_commands(bridge)
