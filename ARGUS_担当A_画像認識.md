# ARGUS プロジェクト — 担当A：画像認識（Vision）

> このドキュメントは日本語版とフランス語版を併記しています。
> Ce document contient une version japonaise et une version française.

---

## 🇯🇵 日本語版

### 📌 このドキュメントについて
これは、ARGUSプロジェクトで **あなたが担当する部分** をまとめた資料です。
- 中身: プロジェクトの紹介 → チームの分担 → あなたの担当範囲 → 開発の進め方 → スケジュール。
- **一番下に、あなた専用の「AIプロンプト」と、その使い方（AIに『プロジェクト』として登録すると毎回貼らずに済む）を用意しています。**
- ⚠️ **今回の更新点**: HEWの主題「お金が動くWebサービス」に合わせ、**「投げ銭で操作するAI監視ロボット」** という形に進化しました。観客が課金してロボットに **ミッション（例:「人を探せ」）** を出せます。あなたの検出は、そのミッションの成否を決める **見せ場** になります。

まず全体に目を通して、最後のプロンプトを自分のAIに設定してください。

> 💡 **この資料の細部は「叩き台」です。** モデル名・JSON項目・しきい値などは例にすぎません。**大きな方向性（＝検出してBへPOST、検出が課金ミッションの見せ場になる）が合っていれば、より良い設計・実装を自由に変えてOK**です。AIにもそう伝えてあります。

### 1. プロジェクト紹介
**ARGUS（アーガス）** は、6脚ロボット（Freenove Big Hexapod + Raspberry Pi 5）をベースにした **AI監視ロボット** です。カメラで周囲を見て人や物を検出し、その情報を遠隔のダッシュボードで監視でき、さらに音声でロボットと対話できます。

**HEW版のコンセプト**: 観客はスマホのWebページから **ライブ映像（あなたのAI検出オーバーレイ付き）** を見て、**課金（投げ銭）してロボットにアクションやミッションを出せます**。課金履歴はDBに残ります（HEW必須）。お金は実際には動かさず、Stripeテストモードか模擬データで想定します。

3層構成:
- **歩行層**: Freenove公式コード（既製・改変しない・全員で組立）
- **AI層（自作）**: 画像認識 ＋ 音声対話
- **IoT層（自作）**: Flaskバックエンド＋決済＋Webダッシュボード

### 2. チームの分担（3人）
- **担当A：画像認識（＝あなた）** — Pi 5上でYOLO/OpenCV。人物/物体を検出してバックエンドへ送る。
- **担当B：バックエンド＋ダッシュボード＋決済** — Flask+SQLite。検出を受信・保存、課金を受け取り取引を記録、課金→アクション発行、Web（観客向け公開ページ＋監視ダッシュボード）。
- **担当C：音声対話＋統合（任／リーダー）** — 音声でロボットと対話、課金アクション・音声意図を歩行層へ橋渡し、全体統合。機体はCが管理。

各モジュールは疎結合です。データは **B（バックエンド）を中心としたスター型** で流れます:
- **A（画像）→ B へ** 検出を送る（`POST /upload`）
- 観客（Web）→ B へ課金 → B が取引を記録＋アクションをキューに登録
- C（音声/統合）→ B から最新検出を読む（`GET /events`）＋ 課金アクションを取りに来る＋ 歩行層へコマンド
- **A と C は直接通信しません。** だから誰かの進捗が遅れても、他の人は止まりません。

あなたが意識するのは「**Bへ送る**」一方向だけです。

### 3. あなたの担当範囲（画像認識）
- Raspberry Pi 5 上での **YOLO / OpenCV ローカル推論**
- カメラ（Logitech C270）から映像取得・前処理
- 人物／物体を検出
- 検出ごとに **イベントを生成 → B の API へ HTTP POST**
- **【新・演出面】ライブ映像に検出オーバーレイ（bbox・ラベル）を描く** — これが観客の見る画面になる。検出の質＝課金体験の質。
- **【新・ミッション連動】** 観客が課金で出すミッション（例:「人を探せ」）の対象を検出したら、`type` にそれが分かる値（例: `mission_person`）を入れてBへ送ると、Bが **成功演出** に使える。

**成果物**: 推論コード、検出データ仕様、ライブ映像＋オーバーレイ

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
- ミッション連動時は `type` に対象が分かる値を入れる（例: `person` / `mission_target`）。命名は自由。
- このスキーマは暫定です。**確定を待たず、この仮の形で先に進めてOK。**

### 4.5. 具体例（すべて暫定・大方向が合えば自由に変更OK）
- **モデル**: まずは軽量なYOLOv8n（または同等）でPCで動かし、後でPi 5へ。種別は人物優先、余裕があれば物体も。
- **しきい値**: confidence 0.5前後から調整。誤検出が多ければ上げる。
- **オーバーレイ**: OpenCVでbbox＋ラベル＋信頼度を描画。観客に「AIが見ている」感が伝わるほど課金につながる。
- **送信頻度**: 毎フレームではなく、検出が出た時 or 数秒に1回など間引く（Bを詰まらせない）。

検出の種類・モデル・描画スタイルは自由。**外せないのは「検出してBへ送る」「ライブ映像に映る」の2点**だけです。

### 5. 並行開発のコツ（実機・他人を待たない）
- **ノートPC ＋ USBカメラだけで開発できます。** 実機（Pi 5）は不要。
- Bが未完成でも、検出結果を **ログ出力** または **localhostのスタブ** に出して検証可能。
- オーバーレイ付きライブ映像は、Bが無くても自分の画面で完成させられる。
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
- ⚠️ **Nouveauté** : pour coller au thème HEW « un service web où l'argent circule », le projet devient un **« robot de surveillance IA qu'on pilote en payant »**. Les spectateurs paient pour donner au robot des missions (ex. : « trouve une personne »). Tes détections sont le **moment fort** qui décide du succès de la mission.

Lis d'abord l'ensemble, puis configure le prompt final dans ton IA.

> 💡 **Les détails de ce document sont une « base de départ ».** Noms de modèle, champs JSON, seuils… ne sont que des exemples. **Tant que la grande direction est respectée (détecter puis POST vers B, et faire de la détection le moment fort de la mission payante), tu peux librement améliorer le design et l'implémentation.** L'IA en est informée aussi.

### 1. Présentation du projet
**ARGUS** est un **robot de surveillance assisté par IA**, basé sur un robot hexapode (Freenove Big Hexapod + Raspberry Pi 5). Il observe les alentours via une caméra, détecte personnes et objets, permet une surveillance à distance via un tableau de bord, et permet de dialoguer avec le robot par la voix.

**Concept HEW** : les spectateurs voient le **flux vidéo en direct (avec ta superposition de détections IA)** depuis leur téléphone, et **paient (pourboire) pour donner des actions ou des missions au robot**. L'historique des paiements est conservé en DB (obligatoire pour HEW). L'argent ne circule pas réellement : on simule via le mode test de Stripe ou des données fictives.

Architecture en 3 couches :
- **Couche locomotion** : code officiel Freenove (prêt à l'emploi, non modifié, assemblé par toute l'équipe)
- **Couche IA (développée par nous)** : reconnaissance d'image + dialogue vocal
- **Couche IoT (développée par nous)** : backend Flask + paiement + tableau de bord web

### 2. Répartition des rôles (3 personnes)
- **Responsable A : reconnaissance d'image (= toi)** — YOLO/OpenCV sur Pi 5. Détecter personnes/objets et les envoyer au backend.
- **Responsable B : backend + tableau de bord + paiement** — Flask+SQLite. Recevoir/stocker les détections, encaisser les paiements et enregistrer les transactions, émettre les actions payées, web (page publique pour les spectateurs + tableau de bord de supervision).
- **Responsable C : dialogue vocal + intégration (Nin / chef d'équipe)** — dialoguer par la voix, faire le pont entre actions payées / intentions vocales et la locomotion, intégration globale. C'est C qui gère le robot physique.

Les modules sont faiblement couplés. Les données circulent **en étoile, autour de B (le backend)** :
- **A (image) → B** : envoi des détections (`POST /upload`)
- Spectateurs (web) → B : paiement → B enregistre la transaction + place l'action dans la file
- C (voix/intégration) → lit les dernières détections depuis B (`GET /events`) + récupère les actions payées + envoie des commandes à la locomotion
- **A et C ne communiquent jamais directement.** Donc si quelqu'un prend du retard, les autres ne sont pas bloqués.

Tu n'as à gérer qu'un seul sens : **envoyer vers B**.

### 3. Ton périmètre (reconnaissance d'image)
- **Inférence locale YOLO / OpenCV** sur le Raspberry Pi 5
- Acquisition et prétraitement du flux de la caméra (Logitech C270)
- Détection de personnes / objets
- Pour chaque détection : **générer un événement → HTTP POST vers l'API de B**
- **[Nouveau · présentation] Dessiner la superposition de détection (bbox, label) sur le flux en direct** — c'est l'écran que voient les spectateurs. Qualité de détection = qualité de l'expérience payante.
- **[Nouveau · lien mission]** Quand tu détectes la cible d'une mission payée (ex. « trouve une personne »), mets dans `type` une valeur identifiable (ex. `mission_person`) pour que B déclenche une **animation de réussite**.

**Livrables** : code d'inférence, spécification des données de détection, flux en direct + superposition.

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
- Pour les missions, mets dans `type` une valeur identifiant la cible (ex. `person` / `mission_target`). Le nommage est libre.
- Ce schéma est provisoire. **N'attends pas la version finale : avance avec cette version temporaire.**

### 4.5. Exemples concrets (tous provisoires · libre de changer si la direction tient)
- **Modèle** : commence avec un YOLOv8n léger (ou équivalent) sur PC, puis porte-le sur Pi 5. Priorité aux personnes, objets si tu as de la marge.
- **Seuil** : confidence autour de 0,5 à ajuster. S'il y a trop de faux positifs, augmente.
- **Superposition** : dessine bbox + label + confiance avec OpenCV. Plus on « voit que l'IA regarde », plus ça incite à payer.
- **Fréquence d'envoi** : pas à chaque image — n'envoie qu'à la détection ou toutes les quelques secondes (n'engorge pas B).

Le type de détection, le modèle, le style d'affichage sont libres. **Les seuls points incontournables : « détecter et envoyer à B » et « apparaître dans le flux en direct ».**

### 5. Astuces pour le développement parallèle (sans attendre le matériel ni les autres)
- **Tu peux développer avec un simple ordinateur portable + une webcam USB.** Pas besoin du robot réel.
- Même si B n'est pas prêt, valide en écrivant les détections dans un **log** ou un **stub localhost**.
- Le flux en direct avec superposition peut être finalisé sur ton écran, sans B.
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

【プロジェクト】ARGUS — Raspberry Pi 5 + Freenove 6脚ロボットをベースにしたAI監視ロボット。3人チーム。3層構成（歩行層=Freenove既製 / AI層=自作 / IoT層=自作）。HEWの主題「お金が動くWebサービス」に合わせ、「投げ銭で操作するAI監視ロボット」にする。観客が課金してロボットにアクション/ミッション（例:「人を探せ」）を出せる。
【私の担当】画像認識。Pi 5上でYOLO/OpenCVのローカル推論。カメラ(Logitech C270)で人物/物体を検出し、検出イベント（JSON: timestamp, type, confidence, image）を生成して、チームのFlaskバックエンドへHTTP POSTする。ライブ映像に検出オーバーレイ（bbox・ラベル）を描く＝観客が見る画面。課金ミッションの対象を検出したら type にそれが分かる値を入れてBへ送り、成功演出に使ってもらう。
【全体構成】スター型。私（画像）→バックエンドへPOSTするだけ。音声・歩行などの他モジュールとは直接通信しない。
【開発方針】まずノートPC＋USBカメラだけで独立して開発する。バックエンドが無くてもログ出力やlocalhostスタブで検証する。実機（Pi 5）には後で載せる。
【技術スタック】Python3, OpenCV, YOLO, Raspberry Pi 5 (ARM)。
【期間】夏休み（7/24〜8月末）で完成。8月末締切。いつでも開始OK、誰も待たない。

この前提で、(1) 画像認識の実装手順、(2) ライブ映像への検出オーバーレイ描画、(3) Pi 5で動かす際のモデル選定・推論速度・消費電力の最適化、(4) 検出イベントのPOST送信（ミッション対象の種別付け含む）、について具体的なコードと手順で助けてください。まず何から着手すべきか提案してください。

※上記のモデル名・JSON項目・しきい値などはすべて「叩き台」です。大きな方向性（検出してBへPOST／検出が課金ミッションの見せ場になる）が合っていれば、より良い設計・実装を自由に提案・変更してかまいません。細部に縛られず、より良い案があれば積極的に提案してください。
```

### Prompt à coller (version française)
```
Tu es un assistant qui m'aide à développer mon « module de reconnaissance d'image ». Voici le contexte d'un projet robotique en équipe.

[Projet] ARGUS — un robot de surveillance par IA basé sur un Raspberry Pi 5 + un robot hexapode Freenove. Équipe de 3 personnes. Architecture en 3 couches (locomotion = Freenove prêt à l'emploi / couche IA = développée par nous / couche IoT = développée par nous). Pour coller au thème HEW « un service web où l'argent circule », on en fait un « robot de surveillance IA qu'on pilote en payant » : les spectateurs paient pour donner au robot des actions/missions (ex. « trouve une personne »).
[Mon rôle] Reconnaissance d'image. Inférence locale YOLO/OpenCV sur le Pi 5. Détecter des personnes/objets via une caméra (Logitech C270), générer un événement de détection (JSON : timestamp, type, confidence, image) et l'envoyer par HTTP POST au backend Flask de l'équipe. Dessiner la superposition de détection (bbox, label) sur le flux en direct = l'écran que voient les spectateurs. Quand je détecte la cible d'une mission payée, je mets une valeur identifiable dans `type` pour que le backend déclenche une animation de réussite.
[Architecture globale] En étoile. Moi (image) → j'envoie seulement des POST au backend. Je ne communique jamais directement avec les autres modules (voix, locomotion).
[Méthode de dev] Je développe d'abord en autonomie avec un simple portable + une webcam USB. Même sans le backend, je valide via des logs ou un stub localhost. Le portage sur le matériel réel (Pi 5) viendra plus tard.
[Stack technique] Python3, OpenCV, YOLO, Raspberry Pi 5 (ARM).
[Délai] À terminer pendant les vacances d'été (24/07 → fin août). Date limite : fin août. On peut commencer quand on veut, sans attendre personne.

Sur cette base, aide-moi avec du code et des étapes concrètes pour : (1) la mise en œuvre de la reconnaissance d'image, (2) le dessin de la superposition de détection sur le flux en direct, (3) le choix du modèle et l'optimisation de la vitesse d'inférence et de la consommation sur Pi 5, (4) l'envoi des événements de détection par POST (y compris le marquage du type pour les cibles de mission). Commence par me proposer par quoi démarrer.

※ Les noms de modèle, champs JSON, seuils ci-dessus ne sont qu'une « base de départ ». Tant que la grande direction tient (détecter puis POST vers B / faire de la détection le moment fort de la mission payante), tu peux librement proposer et changer le design et l'implémentation. Ne te limite pas aux détails : propose mieux si tu peux.
```
