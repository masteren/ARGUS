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
#  ・ホストは "localhost" ではなく "127.0.0.1"。Windows では localhost が先に
#    IPv6(::1) へ解決され、IPv4 で待ち受けている B への接続が一度失敗してから
#    retry するので、1リクエストあたり約2秒待たされる（実測 7ms → 2050ms）。
#    ポーリングのたびに2秒足されると、観客がボタンを押してからロボットが
#    動くまでが目に見えて遅くなる。
#    別マシンの B を見るときは ARGUS_B_HOST で上書きする。
B_HOST = os.environ.get("ARGUS_B_HOST", "127.0.0.1")
B_URL = "http://%s:%s" % (B_HOST, B_PORT)

def _extract_list(payload, key):
    """B は {"ok":true, key:[...]} 形式、偽サーバーは [...] 形式。両方を許容する。"""
    if isinstance(payload, dict):
        return payload.get(key, [])
    if isinstance(payload, list):
        return payload
    return []

def report_battery_loop(bridge, interval=None):
    """定期的にロボットの電圧を聞いて B に報告する。別スレッドで回す。

    電圧を取れるのは 5002 の TCP を握っている C だけなので、B は自力では
    知りようがない。ここが唯一の供給源。

    query_power は bridge の lock を取るため、移動コマンドの実行中
    （前進は2秒 sleep する）は待たされる。展示中に電圧がそこまで速く
    変わるわけでもないので、間隔は長めで構わない。
    """
    interval = interval or float(os.environ.get("ARGUS_BATTERY_INTERVAL", "10"))
    while True:
        try:
            volts = bridge.query_power()
            if volts:
                requests.post(f"{B_URL}/battery",
                              json={"load": volts[0], "pi": volts[1]}, timeout=3)
        except Exception as e:
            print("[battery]", e, flush=True)
        time.sleep(interval)


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
