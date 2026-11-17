# ARGUS — 体験チケット連動型 AI 相棒ロボット

観客がスマホでログインし、体験チケット（模擬決済）を購入して、6脚ロボット（Freenove ＋ Raspberry Pi 5）を操作する展示作品。

- 要件：[docs/要件定義書_ARGUS_Ver1.0.md](docs/要件定義書_ARGUS_Ver1.0.md)
- API の正本：[CONTRACT.md](CONTRACT.md)
- 実機の接続・トラブル対応：[docs/DEPLOY_ROBOT.md](docs/DEPLOY_ROBOT.md)

## 構成

```
ARGUS_backend/   B：Flask + SQLite のバックエンドと Web 画面
vision/          A：画像認識
voice/           C：音声対話とロボットへの命令送信
tools/           起動スクリプトとスモークテスト
docs/            設計・課題のドキュメント
```

## 動かし方

```bash
pip install -r requirements.txt

bash tools/smoketest.sh                          # 実機・カメラ・APIキーなしで全体を確認

cd ARGUS_backend && PORT=5001 python3 app.py     # B だけ起動 → http://localhost:5001
python3 tools/run_all.py --robot <PiのIP> --vision   # 実機につないで全部起動
```

- macOS は AirPlay が 5000 番を使うので `PORT=5001` にする
- 実機に繋ぐときは Freenove 公式クライアント `Main.py` を閉じておく
- `ARGUS_DEBUG=1` は開発時だけ。展示では必ず OFF

## チーム

| 担当 | メンバー | 役割 | ディレクトリ |
| --- | --- | --- | --- |
| C | [@masteren](https://github.com/masteren)（リーダー） | 音声対話・ロボット連携・統合 | `voice/` |
| B | [@tsukky227](https://github.com/tsukky227) | バックエンド・Web | `ARGUS_backend/` |
| A | [@Hochadamas](https://github.com/Hochadamas) | 画像認識 | `vision/` |
| D | [@chibayanki](https://github.com/chibayanki) | 観客体験・デザイン・テスト | — |

作業はブランチを切り、`bash tools/smoketest.sh` が ALL GREEN になってから main へ Pull Request を出す。
