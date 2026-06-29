# paid_poller.py —— 第二路输入：从 B 的队列取课金动作，喂给同一个 bridge。
import requests, time

B_URL = "http://localhost:5001"   # 集成时改成真 B 的地址

def poll_paid_commands(bridge, action_replies=None, interval=2):
    print("💰 課金ポーリング開始...")
    while True:
        try:
            cmds = requests.get(f"{B_URL}/commands", timeout=3).json()
            for c in cmds:
                action = c["action"]
                payer = c.get("payer_name", "誰か")
                print(f"💰 課金アクション: {payer} さん → {action}")
                bridge.send(action, paid=True)        # 让机器人动
                requests.post(f"{B_URL}/commands/{c['id']}/done", timeout=3)
        except Exception as e:
            print("[poll]", e)
        time.sleep(interval)
