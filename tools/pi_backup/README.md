# Pi 固有データのバックアップ

Pi の SD カードにしか無く、壊れたら作り直すしかないファイルの控え。
取得元は `~/Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi/Code/Server/`（2026-09-24 取得）。

| ファイル | 中身 | 失うと |
|---|---|---|
| `point.txt` | 6本の脚のサーボ校正値（脚ごとに x / y / z のずれ）。2026-09-08 に公式クライアントで合わせたもの。本家の既定値は全脚 `140 0 0` | 脚の角度がずれ、斜めに歩く・ふらつく。公式クライアントで6本とも校正し直すことになる |
| `params.json` | 基板と Pi の版（`Pcb_Version` / `Pi_Version`）。サーバー起動時に読まれる | 起動時に聞き直されるだけ。内容は2行 |

**この校正値はこの1台のロボット専用。** 別の個体に入れると脚がずれる。
脚を分解・組み直したり、公式クライアントで校正し直したりしたら、ここも取り直すこと：

```bash
scp pi:Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi/Code/Server/{point.txt,params.json} tools/pi_backup/
```

## SD カードを作り直したときの戻し方

Pi を再セットアップして Freenove のリポジトリを clone し直したあと（手順は
[docs/DEPLOY_ROBOT.md](../../docs/DEPLOY_ROBOT.md)）、PC の ARGUS から：

```bash
scp tools/pi_backup/point.txt tools/pi_backup/params.json \
    pi:Freenove_Big_Hexapod_Robot_Kit_for_Raspberry_Pi/Code/Server/
```

そのあと Pi で `python3 tools/patch_freenove_server.py`（本家への修正4つ）を当て、
systemd の `freenove.service` を登録すれば元どおりになる。
