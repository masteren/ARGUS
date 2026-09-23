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


def _is_still_pending(command_id):
    """そのコマンドがまだ未実行のままか（＝取り消されていないか）を B に聞く。

    なぜ要るか：GET /commands で一度に複数件を受け取ると、その一覧は
    手元のメモリにあるだけで DB の状態とは切り離される。運営が
    /control の「停止」を押すと B は pending を done に書き換えるが、
    手元のバッチはそれを知らないので、停止したはずなのに残りの前進が
    次々に送られてしまう（＝緊急停止として機能しない）。
    実行の直前にここで確認することで、取り消された分を捨てる。
    """
    try:
        resp = requests.get(f"{B_URL}/commands", timeout=3).json()
        return command_id in {c["id"] for c in _extract_list(resp, "commands")}
    except Exception:
        return True      # 確認できないときは実行する。取りこぼすより良い


def poll_paid_commands(bridge, action_replies=None, interval=2):
    print("🎫 チケット命令のポーリング開始...")
    while True:
        cancelled = False
        try:
            resp = requests.get(f"{B_URL}/commands", timeout=3).json()
            cmds = _extract_list(resp, "commands")
            for index, c in enumerate(cmds):
                # 1件目は取得直後なので確認しない。2件目以降は、前の
                # コマンドを実行している間（前進なら2秒）に停止が押された
                # 可能性があるので、送る前に毎回確認する。
                if index > 0 and not _is_still_pending(c["id"]):
                    print("🎫 停止により取り消されました。残りのバッチを破棄します",
                          flush=True)
                    cancelled = True
                    break

                action = c["action"]
                label = c.get("action_label") or c.get("payer_name") or action
                print(f"🎫 チケット: {label} → {action}")
                bridge.send(action, paid=True)                       # ロボットを動かす
                requests.post(f"{B_URL}/commands/{c['id']}/done", timeout=3)  # 完了報告
        except Exception as e:
            print("[poll]", e)

        # 取り消しを検出したときは待たずに取りに行く。停止コマンド自身が
        # キューに入っているので、すぐ拾って実際に止まれるようにする。
        if not cancelled:
            time.sleep(interval)
