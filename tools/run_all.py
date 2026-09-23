#!/usr/bin/env python3
# run_all.py —— ARGUS をまとめて起動する。「Webページを開くだけ」にするための入口。
#
# これが解決すること：
#   従来は端末を3つ開いて B / A / C を手で起動し、さらに Freenove 公式クライアント
#   （Code/Client/Main.py）も別に立ち上げる必要があった。ARGUS が公式クライアントの
#   仕事（5002=命令・8002=映像）を両方引き受けたので、公式クライアントはもう要らない。
#   このスクリプトが残りの B / A / C をまとめて面倒を見る。
#
# 前提（Pi 側）：Freenove サーバーが無画面で起動していること。
#   python3 main.py -t -n        （-t=TCP開始, -n=GUIなし）
#   docs/DEPLOY_ROBOT.md の systemd 設定を入れておけば電源を入れるだけで立ち上がる。
#
# 使い方：
#   python3 tools/run_all.py --robot 192.168.0.14            # B + C（Web操作のみ）
#   python3 tools/run_all.py --robot 192.168.0.14 --vision   # + A（search_person に必要）
#   python3 tools/run_all.py --robot 192.168.0.14 --voice    # C を音声版にする
#   python3 tools/run_all.py                                 # 実機なし（Mock）で経路確認
#
# Ctrl+C で全部まとめて落とす。

import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

procs = []


def start(name, script, cwd, env, critical=False):
    """子プロセスを1つ起動して記録する。

    critical=True は「これが死んだら全部畳む」もの（＝B だけ）。
    C や A が死んでも B は生かす：展示中にロボットが一瞬落ちただけで
    観客のページまで消えるのは最悪なので。
    """
    print(f"▶ {name} を起動: {script.relative_to(ROOT)}", flush=True)
    p = subprocess.Popen([sys.executable, str(script)], cwd=str(cwd), env=env)
    procs.append([name, p, critical])
    return p


def port_is_busy(port):
    """そのポートで既に誰かが待ち受けていないか。"""
    import socket

    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect(("127.0.0.1", int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def check_port(port):
    """塞がっていたら原因の見当を添えて教える。

    macOS は AirPlay レシーバーが 5000 を掴むので、Mac に移ったとたん
    「B が起動しない」とだけ言われて原因が分からない、という事故が起きる。
    """
    if not port_is_busy(port):
        return True

    print(f"！ ポート {port} は既に使われています。", flush=True)
    if sys.platform == "darwin" and str(port) == "5000":
        print("  macOS の AirPlay レシーバーが 5000 を使っている可能性が高いです。", flush=True)
        print("  → `--port 5001` で逃がすか、システム設定 > 一般 > AirDrop と Handoff で", flush=True)
        print("    「AirPlay レシーバー」をオフにしてください。", flush=True)
    else:
        print("  前回の ARGUS が残っているかもしれません。", flush=True)
        if sys.platform == "win32":
            print(f"  → 確認: netstat -ano | findstr :{port}", flush=True)
        else:
            print(f"  → 確認: lsof -i :{port}", flush=True)
        print("  → もしくは `--port <別の番号>` で逃がす", flush=True)
    return False


def wait_for_backend(url, timeout=25.0):
    """B の /health が応答するまで待つ。A と C はこれが上がってから繋ぐ。"""
    try:
        import requests
    except ImportError:
        print("！ requests が入っていません: pip install -r requirements.txt", flush=True)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        for _, p, _c in procs:
            if p.poll() is not None:
                return False          # B が落ちたなら待つ意味がない
        try:
            if requests.get(f"{url}/health", timeout=2).json().get("ok"):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def shutdown(*_):
    print("\n■ 終了します...", flush=True)
    for name, p, _c in reversed(procs):
        if p.poll() is None:
            print(f"  停止: {name}", flush=True)
            p.terminate()
    deadline = time.time() + 5
    for _, p, _c in procs:
        remaining = max(0, deadline - time.time())
        try:
            p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            p.kill()
    sys.exit(0)


def main():
    ap = argparse.ArgumentParser(description="ARGUS をまとめて起動する")
    ap.add_argument("--robot", metavar="IP",
                    help="Pi の IP。省略すると Mock（実機なし）で動く")
    ap.add_argument("--vision", action="store_true",
                    help="A（画像認識）も起動する。search_person ミッションに必要")
    ap.add_argument("--voice", action="store_true",
                    help="C を音声版にする（OPENAI_API_KEY とマイクが要る）")
    ap.add_argument("--port", default=os.environ.get("PORT", "5000"),
                    help="B のポート。既定 5000")
    ap.add_argument("--no-browser", action="store_true",
                    help="ブラウザを自動で開かない")
    args = ap.parse_args()

    env = os.environ.copy()
    env["PORT"] = str(args.port)
    if args.robot:
        # B はこれを見てカメラを Freenove の映像に切り替え、C は命令の送信先にする。
        env["ARGUS_ROBOT_HOST"] = args.robot

    # ヘルスチェックは 127.0.0.1 固定。localhost だと Windows で IPv6 を
    # 先に試して毎回2秒待たされ、起動判定が無駄に遅くなる。
    b_url = f"http://127.0.0.1:{args.port}"
    browser_url = f"http://localhost:{args.port}"   # 人が見る方は localhost で良い

    print("=" * 56)
    print("  ARGUS 統合起動")
    print(f"  ロボット : {args.robot or 'なし（Mock）'}")
    print(f"  カメラ   : {'ロボット一人称（Freenove 8002）' if args.robot else 'ローカルUSBカメラ'}")
    print(f"  C        : {'音声＋チケット' if args.voice else 'チケットのみ（音声なし）'}")
    print(f"  A        : {'起動する' if args.vision else '起動しない'}")
    print("=" * 56)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 先にポートを見る。塞がったまま起動しても B が死ぬだけで理由が分からない。
    if not check_port(args.port):
        return 1

    # ── B（後端＋Web＋映像配信）──
    start("B 後端", ROOT / "ARGUS_backend" / "app.py", ROOT / "ARGUS_backend", env,
          critical=True)

    if not wait_for_backend(b_url):
        print("！ B が起動しませんでした。上のログを確認してください。", flush=True)
        shutdown()

    print(f"✓ B 起動完了 → {b_url}", flush=True)

    # ── C（チケット命令 → ロボット）──
    c_script = "argus_voice.py" if args.voice else "paid_only.py"
    start("C ブリッジ", ROOT / "voice" / c_script, ROOT / "voice", env)

    # ── A（画像認識）──
    # ultralytics（YOLO）が入っていれば本命の detection_webcam.py、無ければ
    # OpenCV 内蔵の検出器で動く detection_lite.py に落とす。どちらも B から見た
    # 口は同じ（/video_feed を読んで /upload に bbox を送る）なので、
    # 公開ページの HUD はそのまま枠を描く。
    if args.vision:
        import importlib.util

        has_yolo = importlib.util.find_spec("ultralytics") is not None
        a_script = "detection_webcam.py" if has_yolo else "detection_lite.py"
        if not has_yolo:
            print("  （ultralytics 未導入のため軽量版 detection_lite.py を使います）",
                  flush=True)
        start("A 画像認識", ROOT / "vision" / a_script, ROOT / "vision", env)

    if not args.no_browser:
        time.sleep(1.5)
        webbrowser.open(browser_url)

    print()
    print(f"■ 観客用ページ : {browser_url}/")
    print(f"■ 管理ページ   : {browser_url}/dashboard")
    print("■ Ctrl+C で全部停止")
    print(flush=True)

    # 落ちたプロセスを見張る。ただし畳むのは B（critical）が落ちたときだけ。
    # C や A の死で観客ページまで消すと、展示中に復旧不能な事故になる。
    reported = set()
    try:
        while True:
            for name, p, critical in procs:
                if p.poll() is None:
                    continue

                if critical:
                    print(f"！ {name} が終了しました (exit={p.returncode})。"
                          "これが無いと何も動かないので全体を停止します。", flush=True)
                    shutdown()

                if name not in reported:
                    reported.add(name)
                    print("", flush=True)
                    print("！" * 28, flush=True)
                    print(f"！ {name} が終了しました (exit={p.returncode})", flush=True)
                    print("！ B と観客ページは動き続けています。", flush=True)
                    print("！ ロボットへの命令だけが止まっています。", flush=True)
                    print("！ Pi 側を確認したら、別の端末でこれだけ起動し直せます：",
                          flush=True)
                    print(f"！   cd {ROOT / 'voice'}", flush=True)
                    print(f"！   ARGUS_ROBOT_HOST={args.robot or '<PiのIP>'} "
                          f"{Path(sys.executable).name} {c_script}", flush=True)
                    print("！" * 28, flush=True)
                    print("", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    sys.exit(main() or 0)
