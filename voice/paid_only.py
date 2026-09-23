# paid_only.py —— 音声なしの C。Web のチケット操作だけでロボットを動かす。
#
# argus_voice.py との違い：
#   argus_voice.py はモジュール先頭で OpenAI() を作り sounddevice を import するため、
#   APIキーとマイクが無いと起動しない。「展示はWebのチケット操作だけ」「マイクは使わない」
#   というときに、その二つを要求せずに同じ経路を回すのがこのファイル。
#
#   使う部品は argus_voice.py と全く同じ（robot_bridge + paid_poller）なので、
#   動作の中身が二重管理になることはない。
#
# 使い方：
#   ARGUS_ROBOT_HOST=<PiのIP> python3 paid_only.py     # 実機
#   python3 paid_only.py                                # Mock（実機なしで経路確認）

import os
import threading

from robot_bridge import MockBridge, FreenoveBridge
from paid_poller import poll_paid_commands, report_battery_loop, B_URL

ROBOT_HOST = os.environ.get("ARGUS_ROBOT_HOST")

if __name__ == "__main__":
    if ROBOT_HOST:
        print(f"🦿 bridge = FreenoveBridge({ROBOT_HOST})")
        bridge = FreenoveBridge(ROBOT_HOST)
    else:
        print("🦿 bridge = MockBridge（ARGUS_ROBOT_HOST 未設定＝実機なし）")
        bridge = MockBridge()

    print(f"🎫 B = {B_URL}")
    print("=== チケット命令のみ（音声なし）。Ctrl+C で終了 ===")

    # 電圧の報告はバックグラウンドで。ロボットの電圧を知れるのは
    # 5002 を握っている C だけなので、ここが B への唯一の供給源。
    threading.Thread(target=report_battery_loop, args=(bridge,),
                     daemon=True).start()

    try:
        poll_paid_commands(bridge)
    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        if hasattr(bridge, "close"):
            bridge.close()
