# paid_poller.py —— 第2の入力経路：B のキューからチケット動作を取り出し、同じ bridge に流す。
#
# ── 統合時の変更点（2026 統合）─────────────────────────────────
#  ・B_URL を本物の B（ポート5000）に変更（旧: 5001 の偽サーバー）。
#  ・B の /commands は {"ok": true, "commands": [...]} を返す（偽サーバーは裸のリストだった）。
#    どちらの形でも動くよう _extract_list() で吸収する。
#  ・B の /commands の1件は {id, action, action_label, source, status, created_at, ...}。
#    payer_name は含まれないので、表示用に action_label を優先で使う。
# ──────────────────────────────────────────────────────────
import os
import requests, time

#  ・ポートは環境変数 PORT で上書きできる（B の app.py と同じ変数）。既定は契約どおり 5000。
#    macOS は AirPlay Receiver が 5000 を掴むので、ローカル結合試験は PORT=5001。
B_PORT = os.environ.get("PORT", "5000")
B_URL = "http://localhost:%s" % B_PORT   # 実機/集成で別ホストなら、ここを B のアドレスに変える

def _extract_list(payload, key):
    """B は {"ok":true, key:[...]} 形式、偽サーバーは [...] 形式。両方を許容する。"""
    if isinstance(payload, dict):
        return payload.get(key, [])
    if isinstance(payload, list):
        return payload
    return []

def poll_paid_commands(bridge, action_replies=None, interval=2):
    print("🎫 チケット命令のポーリング開始...")
    while True:
        try:
            resp = requests.get(f"{B_URL}/commands", timeout=3).json()
            cmds = _extract_list(resp, "commands")
            for c in cmds:
                action = c["action"]
                label = c.get("action_label") or c.get("payer_name") or action
                print(f"🎫 チケット: {label} → {action}")
                bridge.send(action, paid=True)                       # ロボットを動かす
                requests.post(f"{B_URL}/commands/{c['id']}/done", timeout=3)  # 完了報告
        except Exception as e:
            print("[poll]", e)
        time.sleep(interval)
