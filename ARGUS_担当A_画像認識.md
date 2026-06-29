# ARGUS プロジェクト — 担当A：画像認識（Vision）

> このドキュメントは日本語版とフランス語版を併記しています。
> Ce document contient une version japonaise et une version française.

---

## 🇯🇵 日本語版

### 📌 このドキュメントについて
これは、ARGUSプロジェクトで **あなたが担当する部分** をまとめた資料です。
- 中身: プロジェクトの紹介 → チームの分担 → あなたの担当範囲 → 開発の進め方 → スケジュール。
- **一番下に、あなた専用の「AIプロンプト」と、その使い方（AIに『プロジェクト』として登録すると毎回貼らずに済む）を用意しています。**

まず全体に目を通して、最後のプロンプトを自分のAIに設定してください。

### 1. プロジェクト紹介
**ARGUS（アーガス）** は、6脚ロボット（Freenove Big Hexapod + Raspberry Pi 5）をベースにした **AI監視ロボット** です。カメラで周囲を見て人や物を検出し、その情報を遠隔のダッシュボードで監視でき、さらに音声でロボットと対話できます。3人チームで作る、チームの主力プロジェクトです。

3層構成:
- **歩行層**: Freenove公式コード（既製・改変しない・全員で組立）
- **AI層（自作）**: 画像認識 ＋ 音声対話
- **IoT層（自作）**: Flaskバックエンド＋Webダッシュボード

### 2. チームの分担（3人）
- **担当A：画像認識（＝あなた）** — Pi 5上でYOLO/OpenCV。人物/物体を検出してバックエンドへ送る。
- **担当B：バックエンド＋ダッシュボード** — Flask+SQLite。検出を受信・保存し、Webダッシュボードで遠隔監視。
- **担当C：音声対話＋統合（任／リーダー）** — 音声でロボットと対話、歩行層との連携、全体統合。機体はCが管理。

各モジュールは疎結合です。データは **B（バックエンド）を中心としたスター型** で流れます:
- **A（画像）→ B へ** 検出を送る（POST）
- C（音声）→ B から最新検出を読む ＋ 歩行層へコマンド
- **A と C は直接通信しません。** だから誰かの進捗が遅れても、他の人は止まりません。

あなたが意識するのは「**Bへ送る**」一方向だけです。

### 3. あなたの担当範囲（画像認識）
- Raspberry Pi 5 上での **YOLO / OpenCV ローカル推論**
- カメラ（Logitech C270）から映像取得・前処理
- 人物／物体を検出
- 検出ごとに **イベントを生成 → B の API へ HTTP POST**

**成果物**: 推論コード、検出データ仕様

### 4. インターフェース契約（暫定・後で全員確定）
検出イベントの JSON（暫定案）:
```json
{
  "timestamp": "2026-08-01T14:23:01",
  "type": "person",
  "confidence": 0.92,
  "image": "detections/img_0012.jpg"
}
```
- 送信先: **B の `POST /upload`**（正式なエンドポイント名は後で確定）
- このスキーマは暫定です。**確定を待たず、この仮の形で先に進めてOK。**

### 5. 並行開発のコツ（実機・他人を待たない）
- **ノートPC ＋ USBカメラだけで開発できます。** 実機（Pi 5）は不要。
- Bが未完成でも、検出結果を **ログ出力** または **localhostのスタブ** に出して検証可能。
- 実機（Pi 5）には **組立後** に載せる。それまでにPCで推論を完成させておく。
- ハードウェアの組立・配線・カメラ接続は **全員共通作業** です。

### 6. スケジュール（夏休みスプリント）
**開発期間 = 夏休み（7/24 〜 8月末）。締切は8月末。**
**開始はいつでもOK。実機・他モジュール・誰かを待つ必要はありません。**
- **今すぐ着手OK**: 暫定のインターフェース契約があるので、自分のモジュールはすぐ始められる。PC＋mockで進めれば、実機もBackendも待たなくていい。
- **早めに一度すり合わせ**: インターフェース契約の最終確定だけ、都合のいいタイミングで全員一度（半日）。それまでは暫定で進める。
- **8月中〜下旬**: ハードウェア組立（全員）＋実機へ移行・3モジュール統合・テスト
- **8月末**: 完成・締切

---

## 🇫🇷 Version française

### 📌 À propos de ce document
Voici le document qui résume **la partie dont tu es responsable** dans le projet ARGUS.
- Contenu : présentation du projet → répartition des rôles → ton périmètre → méthode de développement → calendrier.
- **Tout en bas, tu trouveras un « prompt IA » dédié, ainsi que la façon de l'utiliser (en l'enregistrant comme un « projet » dans ton IA, tu n'auras plus à le recoller à chaque fois).**

Lis d'abord l'ensemble, puis configure le prompt final dans ton IA.

### 1. Présentation du projet
**ARGUS** est un **robot de surveillance assisté par IA**, basé sur un robot hexapode (Freenove Big Hexapod + Raspberry Pi 5). Il observe les alentours via une caméra, détecte personnes et objets, permet une surveillance à distance via un tableau de bord, et permet de dialoguer avec le robot par la voix. C'est le projet principal de notre équipe de 3 personnes.

Architecture en 3 couches :
- **Couche locomotion** : code officiel Freenove (prêt à l'emploi, non modifié, assemblé par toute l'équipe)
- **Couche IA (développée par nous)** : reconnaissance d'image + dialogue vocal
- **Couche IoT (développée par nous)** : backend Flask + tableau de bord web

### 2. Répartition des rôles (3 personnes)
- **Responsable A : reconnaissance d'image (= toi)** — YOLO/OpenCV sur Pi 5. Détecter personnes/objets et les envoyer au backend.
- **Responsable B : backend + tableau de bord** — Flask+SQLite. Recevoir et stocker les détections, surveillance à distance via un tableau de bord web.
- **Responsable C : dialogue vocal + intégration (Nin / chef d'équipe)** — dialoguer avec le robot par la voix, lien avec la couche locomotion, intégration globale. C'est C qui gère le robot physique.

Les modules sont faiblement couplés. Les données circulent **en étoile, autour de B (le backend)** :
- **A (image) → B** : envoi des détections (POST)
- C (voix) → lit les dernières détections depuis B + envoie des commandes à la locomotion
- **A et C ne communiquent jamais directement.** Donc si quelqu'un prend du retard, les autres ne sont pas bloqués.

Tu n'as à gérer qu'un seul sens : **envoyer vers B**.

### 3. Ton périmètre (reconnaissance d'image)
- **Inférence locale YOLO / OpenCV** sur le Raspberry Pi 5
- Acquisition et prétraitement du flux de la caméra (Logitech C270)
- Détection de personnes / objets
- Pour chaque détection : **générer un événement → HTTP POST vers l'API de B**

**Livrables** : code d'inférence, spécification des données de détection.

### 4. Contrat d'interface (provisoire, à finaliser ensemble plus tard)
JSON de l'événement de détection (proposition provisoire) :
```json
{
  "timestamp": "2026-08-01T14:23:01",
  "type": "person",
  "confidence": 0.92,
  "image": "detections/img_0012.jpg"
}
```
- Destination : **`POST /upload` de B** (le nom exact sera fixé plus tard)
- Ce schéma est provisoire. **N'attends pas la version finale : avance avec cette version temporaire.**

### 5. Astuces pour le développement parallèle (sans attendre le matériel ni les autres)
- **Tu peux développer avec un simple ordinateur portable + une webcam USB.** Pas besoin du robot réel.
- Même si B n'est pas prêt, valide en écrivant les détections dans un **log** ou un **stub localhost**.
- Le portage sur le matériel réel (Pi 5) se fera **après l'assemblage**. D'ici là, termine l'inférence sur PC.
- L'assemblage, le câblage et le branchement de la caméra sont des **tâches communes à toute l'équipe**.

### 6. Calendrier (sprint des vacances d'été)
**Période = vacances d'été (24/07 → fin août). Date limite : fin août.**
**Tu peux commencer quand tu veux. Pas besoin d'attendre le matériel, les autres modules, ni qui que ce soit.**
- **Commence dès maintenant** : grâce au contrat d'interface provisoire, tu peux démarrer ton module tout de suite. Avec PC + mock, tu n'attends ni le matériel ni le backend.
- **Une mise au point rapide, tôt** : il suffit de fixer une fois ensemble la version finale du contrat d'interface (une demi-journée), quand ça arrange tout le monde. D'ici là, on avance avec la version provisoire.
- **Mi-août → fin août** : assemblage matériel (toute l'équipe) + portage sur le matériel réel, fusion des 3 modules, tests
- **Fin août** : achèvement, date limite

---

## ▼ AIの準備：プロジェクト機能を使うと便利 / Préparer ton IA : utilise la fonction « Projet »

### 🇯🇵 毎回プロンプトを貼らずに済む方法
ClaudeとChatGPTには「**プロジェクト**」機能があり、最初に一度プロンプトを登録すれば、そのプロジェクト内のすべての会話に自動で背景が読み込まれます。毎回コピペする必要がなくなります。

**Claudeの場合**（無料プランでも可、最大5プロジェクト）:
1. 左メニューの「プロジェクト」→「＋ 新規プロジェクト」
2. 名前を付ける（例: `ARGUS 画像認識`）
3. プロジェクトの「カスタム指示（instructions）」に、下のプロンプトを貼り付け
4. （任意）この資料ファイルをプロジェクトにアップロード（ナレッジ）
→ 以降、このプロジェクト内で会話を始めれば、毎回自動で背景が効く。

**ChatGPTの場合**（無料・有料いずれも可）:
1. 左メニューの「プロジェクト（Projects）」→「新規（New）」
2. 名前を付ける
3. プロジェクト右上の「…（三点）」→「プロジェクト設定」を開き、「指示（instructions）」に下のプロンプトを貼り付け
4. （任意）プロジェクトのチャットにこの資料ファイルをドラッグしてアップロード
→ 以降、このプロジェクト内のどの会話にも自動で適用される。

### 🇫🇷 Pour ne plus recoller le prompt à chaque fois
Claude et ChatGPT ont une fonction « **Projet** » : tu enregistres le prompt une seule fois, et il s'applique automatiquement à toutes les conversations de ce projet. Plus besoin de le recoller.

**Avec Claude** (possible même en gratuit, jusqu'à 5 projets) :
1. Menu de gauche → « Projects » → « + New Project »
2. Donne un nom (ex. : `ARGUS reconnaissance d'image`)
3. Colle le prompt ci-dessous dans les « instructions » du projet
4. (facultatif) Téléverse ce document dans la base de connaissances du projet
→ Ensuite, chaque conversation dans ce projet aura le contexte automatiquement.

**Avec ChatGPT** (gratuit ou payant) :
1. Menu de gauche → « Projects » → « New »
2. Donne un nom
3. En haut à droite du projet → « … » → « Project settings », colle le prompt ci-dessous dans les « instructions »
4. (facultatif) Glisse ce document dans une conversation du projet pour le téléverser
→ Ensuite, toutes les conversations du projet l'appliquent automatiquement.

---

### 貼り付け用プロンプト（日本語版）
```
あなたは、私が担当する「画像認識モジュール」の開発を手伝うアシスタントです。以下はチーム開発中のロボットプロジェクトの背景です。

【プロジェクト】ARGUS — Raspberry Pi 5 + Freenove 6脚ロボットをベースにしたAI監視ロボット。3人チーム。3層構成（歩行層=Freenove既製 / AI層=自作 / IoT層=自作）。
【私の担当】画像認識。Pi 5上でYOLO/OpenCVのローカル推論。カメラ(Logitech C270)で人物/物体を検出し、検出イベント（JSON: timestamp, type, confidence, image）を生成して、チームのFlaskバックエンドへHTTP POSTする。
【全体構成】スター型。私（画像）→バックエンドへPOSTするだけ。音声・歩行などの他モジュールとは直接通信しない。
【開発方針】まずノートPC＋USBカメラだけで独立して開発する。バックエンドが無くてもログ出力やlocalhostスタブで検証する。実機（Pi 5）には後で載せる。
【技術スタック】Python3, OpenCV, YOLO, Raspberry Pi 5 (ARM)。
【期間】夏休み（7/24〜8月末）で完成。8月末締切。いつでも開始OK、誰も待たない。

この前提で、(1) 画像認識の実装手順、(2) Pi 5で動かす際のモデル選定・推論速度・消費電力の最適化、(3) 検出イベントのPOST送信、について具体的なコードと手順で助けてください。まず何から着手すべきか提案してください。
```

### Prompt à coller (version française)
```
Tu es un assistant qui m'aide à développer mon « module de reconnaissance d'image ». Voici le contexte d'un projet robotique en équipe.

[Projet] ARGUS — un robot de surveillance par IA basé sur un Raspberry Pi 5 + un robot hexapode Freenove. Équipe de 3 personnes. Architecture en 3 couches (locomotion = Freenove prêt à l'emploi / couche IA = développée par nous / couche IoT = développée par nous).
[Mon rôle] Reconnaissance d'image. Inférence locale YOLO/OpenCV sur le Pi 5. Détecter des personnes/objets via une caméra (Logitech C270), générer un événement de détection (JSON : timestamp, type, confidence, image) et l'envoyer par HTTP POST au backend Flask de l'équipe.
[Architecture globale] En étoile. Moi (image) → j'envoie seulement des POST au backend. Je ne communique jamais directement avec les autres modules (voix, locomotion).
[Méthode de dev] Je développe d'abord en autonomie avec un simple portable + une webcam USB. Même sans le backend, je valide via des logs ou un stub localhost. Le portage sur le matériel réel (Pi 5) viendra plus tard.
[Stack technique] Python3, OpenCV, YOLO, Raspberry Pi 5 (ARM).
[Délai] À terminer pendant les vacances d'été (24/07 → fin août). Date limite : fin août. On peut commencer quand on veut, sans attendre personne.

Sur cette base, aide-moi avec du code et des étapes concrètes pour : (1) la mise en œuvre de la reconnaissance d'image, (2) le choix du modèle et l'optimisation de la vitesse d'inférence et de la consommation sur Pi 5, (3) l'envoi des événements de détection par POST. Commence par me proposer par quoi démarrer.
```
