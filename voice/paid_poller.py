# paid_poller.py —— 第2の入力経路：B のキューから課金動作を取り出し、同じ bridge に流す。
import requests, time

B_URL = "http://localhost:5001"   # 統合時には本物の B のアドレスに変更する

def poll_paid_commands(bridge, action_replies=None, interval=2):
    print("💰 課金ポーリング開始...")
    while True:
        try:
            cmds = requests.get(f"{B_URL}/commands", timeout=3).json()
            for c in cmds:
                action = c["action"]
                payer = c.get("payer_name", "誰か")
                print(f"💰 課金アクション: {payer} さん → {action}")
                bridge.send(action, paid=True)        # ロボットを動かす
                requests.post(f"{B_URL}/commands/{c['id']}/done", timeout=3)
        except Exception as e:
            print("[poll]", e)
        time.sleep(interval)
