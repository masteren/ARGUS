#!/usr/bin/env python3
# patch_freenove_server.py —— Freenove サーバー側に必要な修正を当てる。
#
# なぜこれが要るか：
#   ARGUS を動かすには Freenove 本家の Code/Server 側にも直しが要る。しかし
#   そのディレクトリは ARGUS リポジトリの外（＝バージョン管理されていない）。
#   Pi を再セットアップしたり、別の人が引き継いだ時点で修正が消えてしまうので、
#   「何をどう直すか」を実行可能な形でここに残す。
#
# 使い方（Pi の上で）：
#   python3 patch_freenove_server.py --dry-run     # 何が変わるか見るだけ
#   python3 patch_freenove_server.py               # 実際に当てる（.bak を作る）
#   python3 patch_freenove_server.py --check       # 当たっているかの確認だけ
#
# 何度実行しても安全（適用済みなら skip する）。
#
# ディレクトリは既定で ~/Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi/Code/Server。
# 違う場所なら --dir で渡す。

import argparse
import shutil
import sys
from pathlib import Path

DEFAULT_DIR = Path.home() / "Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi" / "Code" / "Server"


# (ファイル名, 説明, 適用済み判定, 置換前, 置換後)
PATCHES = [
    (
        "main.py",
        "tcp_flag → is_tcp_active（属性名の不一致）",
        # 直っていれば tcp_flag は消えている
        lambda s: "self.server.tcp_flag" not in s,
        "self.server.tcp_flag",
        "self.server.is_tcp_active",
    ),
    (
        "main.py",
        "終了待ちの while True: pass → sleep（1コア占有をやめる）",
        lambda s: "        while True:\n            pass\n" not in s,
        "        while True:\n            pass\n",
        "        while True:\n            time.sleep(1)\n",
    ),
    (
        "control.py",
        "停止判定に angle を含める（その場旋回が停止扱いされる問題）",
        lambda s: 'self.command_queue[5] == "0"' in s,
        '                if self.command_queue[2] == "0" and self.command_queue[3] == "0":\n',
        '                if (self.command_queue[2] == "0" and self.command_queue[3] == "0"\n'
        '                        and self.command_queue[5] == "0"):\n',
    ),
    (
        "control.py",
        "condition_monitor の無 sleep ループ（待機中だけ CPU を譲る）",
        lambda s: "if self.command_queue[0] == '':\n                time.sleep(0.005)" in s,
        "    def condition_monitor(self):\n        while True:\n",
        "    def condition_monitor(self):\n        while True:\n"
        "            # 待機中だけ CPU を譲る。命令の実行中は歩容のタイミングに\n"
        "            # 余計な遅延を足さないよう sleep しない。\n"
        "            if self.command_queue[0] == '':\n"
        "                time.sleep(0.005)\n",
    ),
    (
        "servo.py",
        "サーボ書き込みの I2C エラーでスレッドごと死なない（1回やり直し、駄目なら飛ばす）",
        lambda s: "def _set_servo_angle_raw(" in s,
        "    def set_servo_angle(self, channel, angle):\n",
        "    def set_servo_angle(self, channel, angle):\n"
        "        # [ARGUS] 電圧降下の瞬間に I2C 書き込みが OSError(121) を出すと、\n"
        "        # 呼んだスレッド（命令受信 receive_commands／歩容 condition_monitor）が\n"
        "        # そのまま死に、接続は残るのに以後の命令が一切効かなくなる（実機で2回）。\n"
        "        # 1回やり直し、それでも駄目ならこの1回だけ飛ばしてスレッドを生かす。\n"
        "        try:\n"
        "            self._set_servo_angle_raw(channel, angle)\n"
        "        except OSError:\n"
        "            time.sleep(0.005)\n"
        "            try:\n"
        "                self._set_servo_angle_raw(channel, angle)\n"
        "            except OSError as e:\n"
        "                self.i2c_errors = getattr(self, 'i2c_errors', 0) + 1\n"
        "                if self.i2c_errors % 100 == 1:   # 電圧降下中は大量に出るので間引く\n"
        "                    print('[ARGUS] servo I2C error (skipped, total %d): %s'\n"
        "                          % (self.i2c_errors, e), flush=True)\n"
        "\n"
        "    def _set_servo_angle_raw(self, channel, angle):\n",
    ),
]

# main.py は time を import していないので、sleep を使う前に足す
IMPORT_FIX = ("main.py", "import os\n", "import os\nimport time\n")


def describe():
    print("""
このスクリプトが当てる修正（すべて実機で問題を確認済み）:

 1. main.py : self.server.tcp_flag → self.server.is_tcp_active
    server.py が読んでいる属性名は is_tcp_active。main.py は tcp_flag に
    代入していたため、誰も読まない属性が増えるだけで is_tcp_active は
    False のままだった。その結果クライアント切断時に reset_server() へ
    入らず、受信ループが空文字を延々と処理して CPU を食い潰し、
    新しい接続も受け付けなくなる（画面に [''] が流れ続ける状態）。

 2. main.py : while True: pass → time.sleep(1)
    -n（GUI なし）で起動したときのメインループ。pass のままだと
    1コアを 100% 占有する。展示中は発熱と消費電力が無駄。

 3. control.py : 停止判定に angle を含める
    停止かどうかを x と y だけで見ていたため、その場旋回
    （x=0, y=0, angle≠0）が「停止」と判定されていた。その分岐は
    relax(False) を通らないので、脱力状態から旋回させても
    サーボが起きず動かない。run_gait 自体は x=y=0 でも angle≠0 なら
    正しく旋回できる。

 4. control.py : condition_monitor に sleep を入れる
    sleep 無しの while True で、待機中も 1コアを 100% 占有していた。
    命令の実行中は sleep しないので歩容のタイミングには影響しない。

 5. servo.py : set_servo_angle の I2C エラーでスレッドを殺さない
    電源が弱いと、歩行中やサーボを動かした瞬間に電圧が落ち、
    PCA9685 への書き込みが OSError: [Errno 121] Remote I/O error になる。
    本家はこれを捕まえないので、呼んだスレッドがそのまま死ぬ：
      ・命令受信（receive_commands）が死ぬと、接続は残ったまま誰も読まない
        → ARGUS からは繋がって見えるのに、何を押しても動かない
      ・歩容（condition_monitor）が死ぬと、命令は届くのに脚が動かない
    どちらもサービスを再起動するまで戻らない（2026-09-23, 09-25 に実機で発生）。
    1回だけやり直し、駄目ならその1回の書き込みを飛ばして続ける。
    起動時の PCA9685 初期化は変えていない（基板に電源が無ければ従来どおり
    起動に失敗し、systemd が5秒ごとに再起動を試みる）。
""")


def main():
    ap = argparse.ArgumentParser(description="Freenove サーバー側の修正を当てる")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                    help=f"Code/Server のパス（既定 {DEFAULT_DIR}）")
    ap.add_argument("--dry-run", action="store_true", help="変更せず結果だけ表示")
    ap.add_argument("--check", action="store_true", help="適用状況の確認だけ")
    ap.add_argument("--explain", action="store_true", help="何を直すのか説明する")
    args = ap.parse_args()

    if args.explain:
        describe()
        return 0

    if not args.dir.is_dir():
        print(f"✗ ディレクトリが見つかりません: {args.dir}")
        print("  --dir で Code/Server の場所を指定してください。")
        return 1

    print(f"対象: {args.dir}\n")

    contents = {}
    for name in {p[0] for p in PATCHES}:
        path = args.dir / name
        if not path.is_file():
            print(f"✗ {name} がありません")
            return 1
        contents[name] = path.read_text(encoding="utf-8")

    applied = skipped = failed = 0

    for name, desc, is_done, old, new in PATCHES:
        s = contents[name]
        if is_done(s):
            print(f"  = {name}: {desc}  （適用済み）")
            skipped += 1
            continue
        if old not in s:
            print(f"  ✗ {name}: {desc}")
            print("      対象のコードが見つかりません。Freenove 側が更新された可能性あり。")
            failed += 1
            continue
        contents[name] = s.replace(old, new)
        print(f"  + {name}: {desc}")
        applied += 1

    # sleep を使うなら import time が要る
    name, old, new = IMPORT_FIX
    if "time.sleep" in contents[name] and "\nimport time" not in contents[name]:
        if old in contents[name]:
            contents[name] = contents[name].replace(old, new, 1)
            print(f"  + {name}: import time を追加")
            applied += 1
        else:
            print(f"  ✗ {name}: import time を足す場所が見つかりません")
            failed += 1

    print()
    if args.check:
        print(f"未適用 {applied} 件 / 適用済み {skipped} 件 / 失敗 {failed} 件")
        return 1 if (applied or failed) else 0

    if failed:
        print("✗ 当てられない修正があるため、何も書き込みませんでした。")
        return 1

    if not applied:
        print("すべて適用済みです。変更はありません。")
        return 0

    if args.dry_run:
        print(f"[dry-run] {applied} 件の修正を当てられます。書き込みはしていません。")
        return 0

    for name in contents:
        path = args.dir / name
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(contents[name], encoding="utf-8")

    print(f"✓ {applied} 件の修正を当てました（元のファイルは .bak に退避）")
    print("\nサーバーを起動し直してください:")
    print("  sudo pkill -f main.py; sleep 2")
    print("  sudo python3 main.py -t -n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
