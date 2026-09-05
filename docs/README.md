# ドキュメント一覧

コードの読み方は[リポジトリ直下の README](../README.md)、
モジュール間の API は [CONTRACT.md](../CONTRACT.md)（正本）を見ること。

## 正式ドキュメント

| ファイル | 内容 | いつ見るか |
| --- | --- | --- |
| [要件定義書_ARGUS_Ver1.0.md](要件定義書_ARGUS_Ver1.0.md) | Ver1.0 の要件定義（概要・機能要件・非機能要件） | 提出物。何を作る/作らないかで迷ったとき |
| [ARGUS_受賞作分析_改善提案_4言語.md](ARGUS_受賞作分析_改善提案_4言語.md) | 過去の金賞・銀賞作品の分析と改善提案（4言語併記） | 加点方針を決めるとき |

## 担当別の役割ドキュメント（[roles/](roles/)）

| ファイル | 担当 |
| --- | --- |
| [ARGUS_担当A_画像認識.md](roles/ARGUS_担当A_画像認識.md) | A：YOLO / OpenCV による画像認識 |
| [ARGUS_担当B_バックエンド.md](roles/ARGUS_担当B_バックエンド.md) | B：Flask + SQLite、Web、取引処理 |
| [ARGUS_担当C_音声統合.md](roles/ARGUS_担当C_音声統合.md) | C：音声対話、実機ブリッジ、統合 |
| [ARGUS_PersonD_AudienceExperience.md](roles/ARGUS_PersonD_AudienceExperience.md) | D：観客体験、展示物、テスト |

> 役割ドキュメントはキックオフ時点の分担メモであり、実装の最新状態は
> コードと `CONTRACT.md` が正。食い違ったらコード側を信じること。
