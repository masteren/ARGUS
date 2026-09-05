# ARGUS — 受賞作分析にもとづく改善提案（最終版）
# ARGUS — Improvement Proposal Based on Award-Winning Projects (Final)
# ARGUS — 基于往届获奖作品的改进提案（最终版）
# ARGUS — Proposition d'amélioration d'après les projets primés (finale)

> **4言語併記 / Four languages / 四语对照 / Quatre langues** — 🇯🇵 日本語 → 🇬🇧 English → 🇨🇳 中文 → 🇫🇷 Français
> 担当の目安 / Owner hint: 🇯🇵=担当B・全体 / 🇬🇧=Person D / 🇨🇳=任(C) / 🇫🇷=担当A

---

## 🇯🇵 日本語版

### 0. この提案の考え方
本書は、昨年の **金賞作**（楽曲EC＋SNSプラットフォーム。正式な要件定義書＋厚い取引テーブルが強み）と **銀賞作**（Project Hologram / Inside The Cocoon。3DモデルEC。アクセス制御アーキテクチャが強み）を分析し、ARGUSに **足すべき点** をまとめたものです。

要点はひとつ:

- **金賞から** … 「ドキュメントの規範性」と「取引テーブルの深さ」
- **銀賞から** … 「アクセス制御（entitlement）の設計」
- ARGUSは **技術的難易度では既に上**（実機・多モーダルAI・課金→物理動作→フィードバックのリアルタイム閉ループ）。足りないのは、HEWの主題そのものである **「お金が動くWebサービス層」の深さと文書化** です。

**方針: 彼らの「機能一覧」ではなく「厳密さ」を借りる。** 🔴印はすべて 7/24 kickoff で定稿します。

### 優先度・担当一覧

| # | 項目 | 由来 | 担当 | 優先度 |
|---|------|------|------|--------|
| A | 授権モデル（entitlement） | 銀 | B＋任 | 🔴 必須 |
| B | 取引テーブルの深化＋支払い→実行の閉ループ | 金＋ARGUS独自 | B | 🔴 必須 |
| C | 正式な要件定義書 | 金 | 任（全員が素材持参） | 🔴 必須 |
| D | セキュリティ / 非機能要件 | 金＋銀 | B | 🟡 推奨 |
| E | ER図＋シーケンス/状態遷移図 | 金 | D＋B | 🟡 推奨 |
| F | バージョン付き変更履歴 | 金 | D／任 | 🟡 推奨 |
| G | 細かい加点（レシート・ランキング窓） | 金＋銀 | B＋D | 🟢 任意 |

### A. 🔴 授権モデル（entitlement）― 最大の穴
**現状の問題**: 同一LAN内なら誰でも任意の `payer_name` で `/pay` を叩け、誰でも `/commands` をポーリングできる。**「お金を払った人だけが操作できる」という仕組みが存在しない。**

**修正（銀賞の preview/access 分離 ＋ entitlement）**:
- **ライブ映像を見る＝無料・公開**（銀の `/preview` に相当）。
- **ロボットを操作する＝課金・要授権**（銀の `/access` に相当）。
- `/pay` 成立時に **操作権（grant / トークン）を発行**（短命・一回きり）。
- `/commands` は **有効な grant に紐づくアクションだけ** を返す／受け付ける。
- `payer_name` は **表示専用**（ランキング用）。**授権キーには絶対に使わない。**
- 外部・クライアント由来のIDを信用せず、サーバ側で内部IDに解決する（銀の `clerk_user_id → 内部UUID` の教訓）。

**⚠️ 銀賞の反面教師**: 彼らはデモのために entitlement 判定を **コメントアウト**していた（`// if (!isAllowed)…`）。私たちの場合、お金は模擬でよいが、**「課金者だけが操作できる」授権ロジックは展示中も必ずONのままにする** ―― それ自体が見どころだから。

### B. 🔴 取引テーブルの深化＋支払い→実行の閉ループ
金賞の `PURCHASE` は `price_at_buy, currency, payment_status, payment_tx_id, purchased_at` を持っていた。ARGUSの `transactions(id, timestamp, amount, action, payer_name, status)` には次が欠けている:

1. **`payment_tx_id`** … Stripeテストモードが返す payment_intent の ID を保存 → 「お金が確かに動いた（監査できる）」という主題の中核証拠。
2. **明確な status ライフサイクル** … `pending → succeeded → failed / refunded`（模擬でもよい）。
3. **`currency`（JPY）／`amount`** の明示。

**閉ループ（ARGUS独自の強み）**: `transactions → command_queue → 実行` を連結し、`executed_at` / `result` を追加。課金者に **「あなたの指示は HH:MM に実行されました」** というレシートを返す。これは純粋なECより **面白い** 部分。捨てないこと。

### C. 🔴 正式な要件定義書
金賞の要件定義書は、shall文（〜しなければならない）、FR-01〜08／NFR／BR、Given/When/Then の受入条件、そして **根拠（実装ファイル・エンドポイントへの追跡可能性）** を備えていた。

ARGUS版: 統合後、各FRをエンドポイント／モジュールに対応づけて書く（例: 「FR: 課金後にロボットが動作する」→ `POST /pay` → `command_queue` → `paid_poller.py`）。

**最も可視性が高く、最も低コストな加点。** kickoff（7/24）に叩き台を持参すれば、そのまま **インターフェース契約の定稿ベース** になる。

### D. 🟡 セキュリティ / 非機能要件
金賞のNFR: 認証ガード（401/403）、入力検証、パストラバーサル防止、統一エラー形式。

ARGUSの滥用面: 展示会場で観客の手机が同一LANから `/pay` を叩く ―― 連打や `action` への異常文字列注入がありうる。具体策:
- **`action` のホワイトリスト検証**（三方の `ACTION_MAP` 統一と同じ作業）。
- **統一エラーレスポンス**。
- `/pay` への **基本的なレート制限**。
- `payer_name` 長など **入力検証**。

### E. 🟡 ER図＋シーケンス/状態遷移図
金賞は正式なER図＋画面遷移図を成果物にしていた。ARGUS版: ER図（`detections / transactions / command_queue ＋ grant テーブル`）と、**支払い→grant→command→実行→done→レシート** の閉ループを表すシーケンス／状態遷移図。作図はDが主導、スキーマはBが提供。

### F. 🟡 バージョン付き変更履歴
金賞は Ver 0.5 / 1.0 / 1.5 のリリースノート（新機能／バグ修正／UX改善）を維持していた ―― プロジェクト管理力の証明。夏休みスプリント中、同じ形式の changelog を維持する。低コスト・好印象。担当はD／任。

### G. 🟢 細かい加点
- レシート／支払い履歴ページ（金賞の購入履歴に相当）。
- ランキングの時間窓（本日 / 累計）。

### ⛔ 真似しないもの
- **金賞から**: follow / like / comment / DAW などのSNS機能 ―― ロボット操作ページには蛇足で、8月末締切前の時間食い。
- **銀賞から**: Unity / WebGL / 3Dビューア / SNS / DM / 通知 ―― 主題外で規模が巨大。
- **原則**: 彼らの **厳密さ**（規格書・取引・アクセス制御）を借り、**機能一覧** は借りない。

### ✅ 私たちが既に優っている点（自信を持つ）
実機統合、多モーダルAI（YOLO視覚 ＋ STT/LLM/TTS音声）、課金→物理動作→フィードバックのリアルタイム閉ループ、検出オーバーレイ付きMJPEGライブ配信。金賞・銀賞のどちらにも **活体推論も実機もない。** 差は野心ではなく、**Web／金流層を堅く作り、文書化すること** だけ。

### 📅 7/24 kickoff に持ち込む定稿項目
1. **ポート統一**（任=5001 ↔ Bのドキュメント=5000）。
2. **`ACTION_MAP` 命名の三方統一**（任 ↔ Bの `/pay` の `action` ↔ Freenove `Command.py`）。
3. **grant / トークン設計**（`/pay` がどう `/commands` を授権するか）。
4. **取引スキーマ最終版**（＋ `payment_tx_id`, `status`, `currency`）。
5. **エンドポイント名の最終確定**。
6. **`action` ホワイトリスト**（唯一の正）。

---

## 🇬🇧 English Version

### 0. The idea behind this proposal
This document analyzes last year's **gold-prize project** (a music EC + SNS platform — strong on its formal requirements spec and a deep transaction table) and the **silver-prize project** (Project Hologram / Inside The Cocoon, a 3D-model marketplace — strong on its access-control architecture), and lists **what ARGUS should add**.

One core idea:
- **From gold** → documentation regularity + transaction-table depth.
- **From silver** → access-control (entitlement) design.
- ARGUS already leads on **technical difficulty** (real hardware, multimodal AI, a real-time pay→physical-action→feedback loop). What's missing is the depth and documentation of the **"web service where money moves" layer** — which is the HEW theme itself.

**Principle: borrow their rigor, not their feature lists.** Every 🔴 item gets locked at the 7/24 kickoff.

### Priority & owner table

| # | Item | Source | Owner | Priority |
|---|------|--------|-------|----------|
| A | Authorization model (entitlement) | Silver | B + Nin | 🔴 Must |
| B | Transaction depth + pay→execute closed loop | Gold + ARGUS-unique | B | 🔴 Must |
| C | Formal requirements spec | Gold | Nin (all bring input) | 🔴 Must |
| D | Security / non-functional requirements | Gold + Silver | B | 🟡 Should |
| E | ER + sequence/state diagrams | Gold | D + B | 🟡 Should |
| F | Versioned changelog | Gold | D / Nin | 🟡 Should |
| G | Minor polish (receipt, ranking windows) | Gold + Silver | B + D | 🟢 Nice |

### A. 🔴 Authorization model (entitlement) — the biggest hole
**Current problem:** anyone on the same LAN can POST `/pay` with any `payer_name`, and anyone can poll `/commands`. **There is no mechanism enforcing "only the payer may control the robot."**

**Fix (from silver's preview/access split + entitlement):**
- **Watching the live stream = free & public** (like silver's `/preview`).
- **Controlling the robot = paid & authorized** (like silver's `/access`).
- On `/pay` success, **issue a control grant / token** (short-lived, single-use).
- `/commands` only returns/accepts actions **backed by a valid grant**.
- `payer_name` is **display-only** (for ranking). **Never the authorization key.**
- Don't trust external/client-supplied IDs; resolve to an internal ID server-side (silver's `clerk_user_id → internal UUID` lesson).

**⚠️ Silver's cautionary tale:** they **commented out** the entitlement check for their demo (`// if (!isAllowed)…`). For us, the money can be simulated, but the **"only payers can control" authorization logic must stay ON during the exhibition** — that logic *is* the attraction.

### B. 🔴 Transaction depth + pay→execute closed loop
Gold's `PURCHASE` had `price_at_buy, currency, payment_status, payment_tx_id, purchased_at`. ARGUS's `transactions(id, timestamp, amount, action, payer_name, status)` is missing:

1. **`payment_tx_id`** — store the Stripe test-mode payment_intent id → "money genuinely moved (auditable)," the core evidence for the theme.
2. **An explicit status lifecycle** — `pending → succeeded → failed / refunded` (even if simulated).
3. **`currency` (JPY) / `amount`** made explicit.

**Closed loop (ARGUS's signature):** link `transactions → command_queue → executed`, add `executed_at` / `result`, and give the payer a receipt: **"your command was executed at HH:MM."** This is what makes us cooler than a plain shop — don't waste it.

### C. 🔴 Formal requirements spec
Gold's spec used shall-statements, FR-01–08 / NFR / BR, Given/When/Then acceptance criteria, and **traceability (根拠) to real files/endpoints.**

ARGUS version: after integration, map each FR to an endpoint/module (e.g., "FR: robot acts after payment" → `POST /pay` → `command_queue` → `paid_poller.py`).

**Highest-visibility, lowest-cost win.** Bring a draft to the 7/24 kickoff so it doubles as the **basis for finalizing the interface contract.**

### D. 🟡 Security / non-functional requirements
Gold's NFR: auth guard (401/403), input validation, path-traversal prevention, unified error format.

ARGUS abuse surface: exhibition visitors' phones hitting `/pay` on the same LAN — spamming, or injecting odd strings into `action`. Concrete steps:
- **Action whitelist validation** (same work as the three-way `ACTION_MAP` unification).
- **Unified error responses.**
- **Basic rate limiting** on `/pay`.
- **Input validation** (e.g., `payer_name` length).

### E. 🟡 ER + sequence/state diagrams
Gold delivered a formal ER diagram + page-transition diagram. ARGUS version: an ER diagram (`detections / transactions / command_queue + grant table`) and a sequence/state diagram of the **pay → grant → command → execute → done → receipt** loop. D leads the drawing; B provides the schema.

### F. 🟡 Versioned changelog
Gold maintained Ver 0.5 / 1.0 / 1.5 release notes (features / bug fixes / UX). It signals project-management maturity. Maintain the same format across the summer sprint. Cheap, good optics. Owner: D / Nin.

### G. 🟢 Minor polish
- Receipt / payment-history page (≈ gold's purchase history).
- Ranking time windows (today / cumulative).

### ⛔ Do NOT copy
- **From gold:** follow / like / comment / DAW social features — clutter on a robot-control page and a time sink before the end-of-August deadline.
- **From silver:** Unity / WebGL / 3D viewer / SNS / DM / notifications — off-theme and huge in scope.
- **Principle:** borrow their **rigor** (spec, transactions, access control), not their **feature lists.**

### ✅ Where we already lead (be confident)
Real hardware integration; multimodal AI (YOLO vision + STT/LLM/TTS voice); a real-time pay→physical-action→feedback closed loop; MJPEG live streaming with a detection overlay. Neither winner had **live inference or a physical robot.** The gap isn't ambition — it's making the web/money layer solid and documented.

### 📅 Items to lock at the 7/24 kickoff
1. **Unify the port** (Nin = 5001 vs B's docs = 5000).
2. **Three-way `ACTION_MAP` naming** (Nin ↔ B's `/pay` `action` ↔ Freenove `Command.py`).
3. **Grant / token design** (how `/pay` authorizes `/commands`).
4. **Final transaction schema** (+ `payment_tx_id`, `status`, `currency`).
5. **Final endpoint names.**
6. **Action whitelist** (single source of truth).

---

## 🇨🇳 中文版

### 0. 这份提案的思路
本文分析去年 **金奖作品**（楽曲EC＋SNS平台，强在正式的要件定义书＋厚实的交易表）与 **银奖作品**（Project Hologram / Inside The Cocoon，3D模型商城，强在访问控制架构），整理出 ARGUS **需要补上的点**。

核心只有一句：
- **从金奖学** → 文档的规范性 ＋ 交易表的深度。
- **从银奖学** → 访问控制（entitlement）的设计。
- ARGUS 在 **技术难度上已经领先**（实机、多模态AI、付费→物理动作→反馈的实时闭环）。缺的正是 HEW 主题本身——**「お金が動くWebサービス」这一层的深度与文档化**。

**方针：借它们的「严谨」，别抄它们的「功能清单」。** 所有 🔴 项都在 7/24 kickoff 定稿。

### 优先级 / 负责人一览

| # | 项目 | 来源 | 负责人 | 优先级 |
|---|------|------|--------|--------|
| A | 授权模型（entitlement） | 银 | B＋任 | 🔴 必做 |
| B | 交易表深化＋付费→执行闭环 | 金＋ARGUS独有 | B | 🔴 必做 |
| C | 正式的要件定义书 | 金 | 任（全员带素材） | 🔴 必做 |
| D | 安全 / 非功能需求 | 金＋银 | B | 🟡 应做 |
| E | ER图＋时序/状态图 | 金 | D＋B | 🟡 应做 |
| F | 带版本的变更记录 | 金 | D／任 | 🟡 应做 |
| G | 细节加分（回执、排行时间窗） | 金＋银 | B＋D | 🟢 可选 |

### A. 🔴 授权模型（entitlement）— 最大的洞
**现状问题**：同一 LAN 内谁都能用任意 `payer_name` 打 `/pay`，谁都能轮询 `/commands`。**「只有付过钱的人才能操作」这件事根本没有机制保证。**

**修正（借银奖的 preview/access 分离 ＋ entitlement）**：
- **看直播＝免费、公开**（对应银奖 `/preview`）。
- **操作机器人＝付费、需授权**（对应银奖 `/access`）。
- `/pay` 成立时 **发一张操作凭证（grant / token）**（短命、一次性）。
- `/commands` 只返回／只接受 **有有效凭证背书的动作**。
- `payer_name` 只做 **显示**（排行榜用），**绝不当授权钥匙。**
- 不信任外部／客户端传来的 ID，服务端一律解析成内部 ID（银奖 `clerk_user_id → 内部UUID` 的教训）。

**⚠️ 银奖的反面教材**：他们为了 demo 把 entitlement 校验 **注释掉了**（`// if (!isAllowed)…`）。对我们而言，钱可以是模拟的，但 **「只有付费者能操作」的授权逻辑，展会全程必须保持开启** —— 因为这逻辑本身就是看点。

### B. 🔴 交易表深化＋付费→执行闭环
金奖的 `PURCHASE` 有 `price_at_buy, currency, payment_status, payment_tx_id, purchased_at`。ARGUS 的 `transactions(id, timestamp, amount, action, payer_name, status)` 缺三样：

1. **`payment_tx_id`** —— 存 Stripe 测试模式返回的 payment_intent id → 「钱真的动过（可审计）」，这是主题的核心证据。
2. **明确的 status 生命周期** —— `pending → succeeded → failed / refunded`（模拟也行）。
3. **`currency`（JPY）／`amount`** 明确化。

**闭环（ARGUS 独有的强项）**：把 `transactions → command_queue → 执行` 串起来，加 `executed_at` / `result`，给付费者一张回执：**「你的指令已于 HH:MM 执行」**。这是比纯电商 **更酷** 的地方，别浪费。

### C. 🔴 正式的要件定义书
金奖的要件定义书用了 shall 句（〜しなければならない）、FR-01～08／NFR／BR、Given/When/Then 受入条件，以及 **根拠（可追溯到真实文件／端点）**。

ARGUS 版：集成后，把每条 FR 映射到端点／模块（例：「FR：付费后机器人执行动作」→ `POST /pay` → `command_queue` → `paid_poller.py`）。

**最可见、成本最低的加分。** 7/24 kickoff 带草稿去，正好当 **接口契约定稿的底本**。

### D. 🟡 安全 / 非功能需求
金奖的 NFR：认证守卫（401/403）、输入校验、路径穿越防护、统一错误格式。

ARGUS 的滥用面：展会现场观众手机从同一 LAN 打 `/pay` —— 可能狂刷，或往 `action` 塞异常字符串。具体做法：
- **`action` 白名单校验**（和三方 `ACTION_MAP` 统一是同一件事）。
- **统一错误响应**。
- 对 `/pay` 做 **基础限流**。
- **输入校验**（如 `payer_name` 长度）。

### E. 🟡 ER图＋时序/状态图
金奖把正式 ER 图＋画面迁移图当成果物。ARGUS 版：ER 图（`detections / transactions / command_queue ＋ grant 表`），以及表示 **付费→grant→command→执行→done→回执** 闭环的时序／状态图。作图由 D 主导，schema 由 B 提供。

### F. 🟡 带版本的变更记录
金奖维护了 Ver 0.5 / 1.0 / 1.5 的 release notes（新功能／修复／UX）—— 是项目管理能力的证明。整个暑假冲刺维护同样格式的 changelog。低成本、好印象。负责人 D／任。

### G. 🟢 细节加分
- 回执／支付历史页（对应金奖购入履历）。
- 排行榜时间窗（今日 / 累计）。

### ⛔ 不要抄的
- **金奖**：follow / like / comment / DAW 这些 SNS 功能 —— 放机器人控制页是画蛇添足，还在 8 月末 deadline 前吃时间。
- **银奖**：Unity / WebGL / 3D 查看器 / SNS / DM / 通知 —— 跑题且规模巨大。
- **原则**：借它们的 **严谨**（规格书、交易、访问控制），别借 **功能清单**。

### ✅ 我们已经领先的地方（别妄自菲薄）
实机集成、多模态 AI（YOLO 视觉 ＋ STT/LLM/TTS 语音）、付费→物理动作→反馈的实时闭环、带检测叠加的 MJPEG 直播。金奖银奖 **都没有活体推理，也没有实机。** 差的不是野心，只是 **把 Web／金流层做扎实 ＋ 文档化**。

### 📅 7/24 kickoff 要定稿的清单
1. **端口统一**（任=5001 ↔ B 文档=5000）。
2. **`ACTION_MAP` 命名三方统一**（任 ↔ B 的 `/pay` `action` ↔ Freenove `Command.py`）。
3. **grant / token 设计**（`/pay` 如何授权 `/commands`）。
4. **交易 schema 最终版**（＋ `payment_tx_id`, `status`, `currency`）。
5. **端点名最终确定**。
6. **`action` 白名单**（唯一真源）。

---

## 🇫🇷 Version française

### 0. L'idée derrière cette proposition
Ce document analyse le **projet médaille d'or** de l'an dernier (une plateforme EC + réseau social musical — fort sur son cahier des charges formel et une table de transactions riche) et le **projet médaille d'argent** (Project Hologram / Inside The Cocoon, une place de marché de modèles 3D — fort sur son architecture de contrôle d'accès), et liste **ce qu'ARGUS doit ajouter**.

Une idée centrale :
- **De l'or** → la rigueur documentaire + la profondeur de la table des transactions.
- **De l'argent** → la conception du contrôle d'accès (entitlement).
- ARGUS mène déjà sur la **difficulté technique** (matériel réel, IA multimodale, boucle temps réel paiement→action physique→retour). Ce qui manque, c'est la profondeur et la documentation de la **couche « service web où l'argent circule »** — c'est-à-dire le thème HEW lui-même.

**Principe : emprunter leur rigueur, pas leurs listes de fonctionnalités.** Chaque élément 🔴 est verrouillé au kickoff du 24/07.

### Tableau priorités / responsables

| # | Élément | Source | Responsable | Priorité |
|---|---------|--------|-------------|----------|
| A | Modèle d'autorisation (entitlement) | Argent | B + Nin | 🔴 Impératif |
| B | Profondeur des transactions + boucle paiement→exécution | Or + propre à ARGUS | B | 🔴 Impératif |
| C | Cahier des charges formel | Or | Nin (chacun apporte de la matière) | 🔴 Impératif |
| D | Sécurité / exigences non fonctionnelles | Or + Argent | B | 🟡 Souhaitable |
| E | Diagramme ER + séquence/états | Or | D + B | 🟡 Souhaitable |
| F | Journal de versions | Or | D / Nin | 🟡 Souhaitable |
| G | Finitions (reçu, fenêtres de classement) | Or + Argent | B + D | 🟢 Optionnel |

### A. 🔴 Modèle d'autorisation (entitlement) — la plus grande faille
**Problème actuel :** sur le même réseau local, n'importe qui peut faire un POST `/pay` avec n'importe quel `payer_name`, et n'importe qui peut interroger `/commands`. **Aucun mécanisme ne garantit que « seul le payeur peut piloter le robot ».**

**Correctif (d'après la séparation preview/access + entitlement de l'argent) :**
- **Regarder le flux en direct = gratuit et public** (comme le `/preview` de l'argent).
- **Piloter le robot = payant et autorisé** (comme le `/access` de l'argent).
- À la réussite de `/pay`, **émettre un droit de contrôle (grant / jeton)** (courte durée, usage unique).
- `/commands` ne renvoie/n'accepte que **les actions adossées à un grant valide**.
- `payer_name` est **uniquement pour l'affichage** (classement). **Jamais la clé d'autorisation.**
- Ne pas faire confiance aux ID externes/fournis par le client ; les résoudre en ID interne côté serveur (leçon `clerk_user_id → UUID interne` de l'argent).

**⚠️ La mise en garde de l'argent :** ils avaient **mis en commentaire** la vérification d'entitlement pour leur démo (`// if (!isAllowed)…`). Pour nous, l'argent peut être simulé, mais la **logique d'autorisation « seuls les payeurs peuvent piloter » doit rester ACTIVE pendant l'exposition** — car cette logique *est* l'attraction.

### B. 🔴 Profondeur des transactions + boucle paiement→exécution
Le `PURCHASE` de l'or avait `price_at_buy, currency, payment_status, payment_tx_id, purchased_at`. Le `transactions(id, timestamp, amount, action, payer_name, status)` d'ARGUS manque de :

1. **`payment_tx_id`** — stocker l'id du payment_intent du mode test Stripe → « l'argent a réellement bougé (auditable) », la preuve centrale du thème.
2. **Un cycle de vie de statut explicite** — `pending → succeeded → failed / refunded` (même simulé).
3. **`currency` (JPY) / `amount`** explicités.

**Boucle fermée (la signature d'ARGUS) :** relier `transactions → command_queue → exécuté`, ajouter `executed_at` / `result`, et donner au payeur un reçu : **« votre commande a été exécutée à HH:MM ».** C'est ce qui nous rend plus intéressants qu'une simple boutique — ne le gaspillez pas.

### C. 🔴 Cahier des charges formel
Le cahier des charges de l'or utilisait des énoncés « shall », FR-01–08 / NFR / BR, des critères d'acceptation Given/When/Then, et une **traçabilité (根拠) vers de vrais fichiers/endpoints.**

Version ARGUS : après l'intégration, associer chaque FR à un endpoint/module (ex. « FR : le robot agit après paiement » → `POST /pay` → `command_queue` → `paid_poller.py`).

**Le gain le plus visible et le moins coûteux.** Apporter un brouillon au kickoff du 24/07 pour qu'il serve aussi de **base à la finalisation du contrat d'interface.**

### D. 🟡 Sécurité / exigences non fonctionnelles
NFR de l'or : garde d'authentification (401/403), validation des entrées, prévention du path-traversal, format d'erreur unifié.

Surface d'abus d'ARGUS : les téléphones des visiteurs sollicitant `/pay` sur le même réseau local — spam, ou injection de chaînes bizarres dans `action`. Mesures concrètes :
- **Validation par liste blanche des `action`** (même travail que l'unification à trois de `ACTION_MAP`).
- **Réponses d'erreur unifiées.**
- **Limitation de débit** de base sur `/pay`.
- **Validation des entrées** (ex. longueur de `payer_name`).

### E. 🟡 Diagramme ER + séquence/états
L'or livrait un diagramme ER formel + un diagramme de transition d'écrans. Version ARGUS : un diagramme ER (`detections / transactions / command_queue + table grant`) et un diagramme de séquence/états de la boucle **paiement → grant → commande → exécution → done → reçu**. D pilote le dessin ; B fournit le schéma.

### F. 🟡 Journal de versions
L'or maintenait des notes de version Ver 0.5 / 1.0 / 1.5 (fonctionnalités / corrections / UX) — preuve de maturité en gestion de projet. Maintenir le même format durant le sprint d'été. Peu coûteux, bon effet. Responsable : D / Nin.

### G. 🟢 Finitions
- Page de reçu / historique de paiement (≈ l'historique d'achat de l'or).
- Fenêtres temporelles du classement (aujourd'hui / cumulé).

### ⛔ Ce qu'il ne faut PAS copier
- **De l'or :** fonctions sociales follow / like / comment / DAW — superflues sur une page de pilotage de robot et chronophages avant l'échéance de fin août.
- **De l'argent :** Unity / WebGL / visionneuse 3D / réseau social / DM / notifications — hors sujet et d'une ampleur énorme.
- **Principe :** emprunter leur **rigueur** (cahier des charges, transactions, contrôle d'accès), pas leurs **listes de fonctionnalités.**

### ✅ Là où nous menons déjà (ayons confiance)
Intégration matérielle réelle ; IA multimodale (vision YOLO + voix STT/LLM/TTS) ; boucle temps réel paiement→action physique→retour ; diffusion en direct MJPEG avec superposition de détection. Aucun des deux lauréats n'avait **d'inférence en direct ni de robot physique.** L'écart n'est pas l'ambition — c'est de rendre la couche web/argent solide et documentée.

### 📅 Éléments à verrouiller au kickoff du 24/07
1. **Unifier le port** (Nin = 5001 vs docs de B = 5000).
2. **Nommage `ACTION_MAP` à trois** (Nin ↔ le `action` de `/pay` de B ↔ `Command.py` de Freenove).
3. **Conception grant / jeton** (comment `/pay` autorise `/commands`).
4. **Schéma de transaction final** (+ `payment_tx_id`, `status`, `currency`).
5. **Noms d'endpoints définitifs.**
6. **Liste blanche des `action`** (source unique de vérité).
