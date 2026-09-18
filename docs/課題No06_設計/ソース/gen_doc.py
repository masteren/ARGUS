# -*- coding: utf-8 -*-
"""画面設計書（16:9スライド）の HTML を組み立てる。"""
import json, html, os

BASE = os.path.dirname(os.path.abspath(__file__))
BOXES = json.load(open(os.path.join(BASE, "boxes.json")))

DATE   = "2026-09-18"
TEAM   = "ARGUS（IH19 / 課題No06）"
REV    = "1.0"
DOCTTL = "体験チケット連動型 AI 相棒ロボット『ARGUS』 画面設計書"

# 切り出した画像が元画面のどの範囲かを持っておき、注釈ピンの座標を変換する
CROPS = {
    "public_pc":  ("public_pc",    0.0,   0.0,   1.0, 1.0),
    "hud_zoom":   ("public_pc",    0.205, 0.10,  0.762, 0.685),
    "sp_top":     ("public_sp",    0.0,   0.0,   1.0, 0.50),
    "sp_bottom":  ("public_sp",    0.0,   0.50,  1.0, 1.0),
    "ranking_pc": ("ranking_pc",   0.0,   0.0,   1.0, 1.0),
    "dash_top":   ("dashboard_pc", 0.0,   0.0,   1.0, 0.38),
    "dash_tx":    ("dashboard_pc", 0.10,  0.383, 0.90, 0.565),
    "dash_det":   ("dashboard_pc", 0.10,  0.652, 0.90, 0.842),
}


def pin(crop, selector, n, idx=0, dx=1.2, dy=1.2, corner="tl"):
    """撮影時に採った要素座標を、切り出し後の画像上の % に直してピンを置く。"""
    src, cl, ct, cr, cb = CROPS[crop]
    r = BOXES[src]["els"][selector][idx]
    x = r["l"] if corner in ("tl", "bl") else r["l"] + r["rw"]
    y = r["t"] if corner in ("tl", "tr") else r["t"] + r["rh"]
    x = (x / 100.0 - cl) / (cr - cl) * 100.0 + dx
    y = (y / 100.0 - ct) / (cb - ct) * 100.0 + dy
    return '<span class="pin" style="left:%.2f%%;top:%.2f%%">%d</span>' % (x, y, n)


def free_pin(n, x, y):
    return '<span class="pin" style="left:%.2f%%;top:%.2f%%">%d</span>' % (x, y, n)


def shot(img, pins, cls=""):
    return ('<div class="shot %s"><img src="img/%s">%s</div>'
            % (cls, img, "".join(pins)))


def items(rows):
    out = []
    for i, (t, d) in enumerate(rows, 1):
        out.append('<li><span class="no">%d</span><span class="tx"><b>%s</b>%s</span></li>'
                   % (i, t, ("<br><small>%s</small>" % d) if d else ""))
    return '<ol class="items">%s</ol>' % "".join(out)


slides = []


def slide(label, name, body, note="", wide=False):
    slides.append((label, name, body, note, wide))


# ── 1. 表紙 ─────────────────────────────────────────────
slides.append(("__cover__", "", "", "", False))

# ── 2. 画面一覧 ─────────────────────────────────────────
rows = [
    ("公開ページ", "/", "観客", "スマートフォン（iOS Safari / Android Chrome・縦画面）<br>会場モニタでも常時表示",
     "ライブ映像とAI検出枠を見せ、体験チケットでロボットを操作する。取引結果とランキングを同じ画面に返す。"),
    ("ランキング画面", "/ranking", "観客・来場者", "PC（Chrome）＋大型ディスプレイ",
     "累計チケットの上位者を表彰台と一覧で見せる。15秒ごとに自動で最新データへ更新する。"),
    ("管理ダッシュボード", "/dashboard", "運営", "PC（Chrome）",
     "サマリ（累計チケット・取引件数・未実行コマンド）と、命令キュー・取引履歴・AI検出履歴を1画面で確認する。"),
    ("ダミー検出登録", "/dummy/detection", "運営", "PC（Chrome）",
     "動作確認用。検出を1件登録して /dashboard へリダイレクトする。展示本番では使用しない。"),
]
tb = ['<table class="tbl"><tr><th>画面名</th><th>URL</th><th>利用者</th><th>利用端末・ブラウザ</th><th>画面の目的</th></tr>']
for r in rows:
    tb.append("<tr>" + "".join("<td>%s</td>" % c for c in r) + "</tr>")
tb.append("</table>")
note = ("会員登録・ログイン画面は Ver1.0 のスコープ外。観客は名前を入力するだけで参加し、未入力のときは「匿名」として記録する。<br>"
        "3画面とも会場ローカル LAN のみで提供し、インターネットには公開しない。体験チケットは模擬通貨であり、実際の金銭は発生しない。")
slide("画面一覧", "ブラウザで開くURLは4つ（画面3 ＋ 動作確認用1）。ほかに画面を持たないAPI・映像配信の経路がある", "".join(tb), note, wide=True)

# ── 3. 画面遷移図 ───────────────────────────────────────
slide("画面遷移図", "観客・会場モニタ・運営の3系統",
      '<div class="full"><img src="img/flow.png"></div>',
      "観客の操作は公開ページ1枚で完結する（fetch で結果だけ差し替え、ページ遷移なし）。詳細は提出物「画面遷移図」を参照。",
      wide=True)

# ── 4. 公開ページ（PC / 会場モニタ）─────────────────────
pins = [
    pin("public_pc", ".site-header .header-status", 1, dx=-3.2, dy=0.2),
    pin("public_pc", ".robot-card", 2, dx=1.4, dy=1.4),
    pin("public_pc", ".status-list", 3, dx=1.4, dy=1.0),
    pin("public_pc", ".live-panel .panel-header", 4, dx=1.0, dy=0.4),
    pin("public_pc", ".live-screen", 5, dx=1.2, dy=1.2),
    pin("public_pc", ".board-panel", 6, dx=1.2, dy=1.2),
    pin("public_pc", "#board_ranking", 7, dx=1.2, dy=1.2),
    pin("public_pc", "#board_feed", 8, dx=1.2, dy=1.2),
    pin("public_pc", ".ticket-notice", 9, dx=1.2, dy=0.2),
    pin("public_pc", "#payer_name", 10, dx=1.2, dy=1.0),
    pin("public_pc", '.action-button[data-action="forward"]', 11, dx=1.2, dy=1.2),
    pin("public_pc", '.action-button[data-action="search_person"]', 12, dx=1.2, dy=1.2),
]
lst = items([
    ("稼働状態", "SYSTEM ONLINE の固定表示。ページが開けている＝サーバが応答している"),
    ("ロボット紹介カード", "ARGUS UNIT-01 / 6脚ロボットの外観写真"),
    ("状態表示", "STATUS・CONTROL・NETWORK の3項目"),
    ("ライブ表示ラベル", "LIVE CAMERA ／ ● LIVE"),
    ("ライブ映像＋AI検出枠", "GET /video_feed（MJPEG）の上に GET /overlay の枠を重ねる"),
    ("サポーターボード", "5秒ごとに自動更新（画面遷移なし）"),
    ("ランキング", "GET /api/ranking：利用者ごとの累計チケット 上位"),
    ("直近の操作", "GET /api/transactions?limit=5：名前とアクション名"),
    ("模擬通貨の明示", "「体験チケットは模擬通貨です。実際の金銭は発生しません。」を常時表示"),
    ("名前入力", "24文字まで。未入力は「匿名」として記録"),
    ("アクションボタン", "前進・左旋回・右旋回 各100／お辞儀・手を振る 各300"),
    ("人を探すミッション", "500チケット。押すとロボットが巡回し、AIが人物を見つけると成功になる"),
])
slide("画面詳細設計（PC・会場モニタ）", "公開ページ（/）",
      shot("public_pc.jpg", pins) + lst,
      "ページを再読込するとライブ映像（MJPEG）が切れるため、操作結果は fetch で受け取り、10〜12 の押下後も画面は遷移させない。")

# ── 5. 公開ページ（スマートフォン・上部）────────────────
pins = [
    pin("sp_top", ".site-header", 1, dx=2.0, dy=1.0),
    pin("sp_top", ".live-screen", 2, dx=2.0, dy=2.0),
    pin("sp_top", ".ticket-notice", 3, dx=2.0, dy=-1.0),
    pin("sp_top", "#payer_name", 4, dx=2.0, dy=1.0),
    pin("sp_top", ".action-grid", 5, dx=2.0, dy=1.0),
    pin("sp_top", '.action-button[data-action="search_person"]', 6, dx=2.0, dy=1.0),
    free_pin(7, 6.0, 91.0),
]
lst = items([
    ("ヘッダー", "高さを詰め、タイトルと稼働状態のみ"),
    ("ライブ映像", "縦画面では映像を先頭（ヘッダーの直下）に置き、4:3 の高さを確保する"),
    ("模擬通貨の明示", "操作パネルの直前に置き、押す前に必ず目に入るようにする"),
    ("名前入力", "高さ48px・文字16px（iOS で入力時に自動ズームさせないため）"),
    ("アクションボタン", "縦画面では横2列。1ボタンの高さ72px以上（指で押せる大きさ）"),
    ("人を探す（500）", "ミッション開始。ほかより高い価格で目玉として見せる"),
    ("結果表示", "押下後にこの位置へ受付メッセージまたはエラーを表示する"),
])
slide("画面詳細設計（スマートフォン・上部）", "公開ページ（/）／ 観客が操作する範囲",
      shot("sp_top.jpg", pins, cls="tall") + lst,
      "820px 以下では 映像 → 操作 → ボード → ロボット紹介 の順に並べ替える。380px 以下ではボタンを1列にする。")

# ── 6. 公開ページ（スマートフォン・下部）────────────────
pins = [
    pin("sp_bottom", ".board-panel", 1, dx=2.0, dy=1.2),
    pin("sp_bottom", "#board_ranking", 2, dx=2.0, dy=1.2),
    free_pin(3, 88.0, 57.0),
    pin("sp_bottom", ".robot-card", 4, dx=2.0, dy=1.2),
    pin("sp_bottom", ".status-list", 5, dx=2.0, dy=1.0),
]
lst = items([
    ("サポーターボード", "縦画面では高さ300pxまでとし、内側をスクロールさせる"),
    ("ランキング", "自分の名前が操作直後に載る（送信成功時にその場で再取得する）"),
    ("直近の操作", "ランキングの下に続く。ボードの内側をスクロールして見る"),
    ("ロボット紹介カード", "操作の邪魔になるため、縦画面では最後に回す"),
    ("状態表示", "STATUS / CONTROL / NETWORK"),
])
slide("画面詳細設計（スマートフォン・下部）", "公開ページ（/）／ スクロールした先",
      shot("sp_bottom.jpg", pins, cls="tall") + lst,
      "上部（映像・操作）と下部（ボード・紹介）で1画面。ページ遷移は発生しない。")

# ── 7. 操作の状態遷移 ───────────────────────────────────
body = """
<div class="states">
  <figure><div class="cap">① 入力中</div><img src="img/sp_input.jpg">
    <figcaption>名前を入力し、使うアクションを選ぶ。送信中はボタンを一時的に無効化し、「チケットを確認しています...」と表示する。</figcaption></figure>
  <figure><div class="cap">② 受付（正常）</div><img src="img/sp_result.jpg">
    <figcaption>○○さんの「△△」を受け付けました。まもなく実行します。<br>入力欄は空にし（共用端末のため）、ランキングをその場で更新する。</figcaption></figure>
  <figure><div class="cap">③ エラー</div><img src="img/sp_error.jpg">
    <figcaption>受け付けられない場合は同じ位置に理由を表示する。画面は遷移せず、そのまま押し直せる。</figcaption></figure>
</div>
<table class="tbl small">
<tr><th>状況</th><th>HTTP</th><th>画面に出す文言</th></tr>
<tr><td>未定義のアクション</td><td>400</td><td>ERROR: 存在しないアクションです</td></tr>
<tr><td>名前が25文字以上</td><td>400</td><td>ERROR: 名前は24文字までです</td></tr>
<tr><td>メッセージが101文字以上</td><td>400</td><td>ERROR: メッセージは100文字までです</td></tr>
<tr><td>同じ端末からの連打（1.5秒以内）</td><td>429</td><td>ERROR: 操作が速すぎます。少し待ってからもう一度お願いします</td></tr>
<tr><td>未実行の命令が10件に達している</td><td>429</td><td>ERROR: ARGUS が混み合っています。少し待ってからお試しください</td></tr>
<tr><td>サーバへ届かない</td><td>—</td><td>通信エラーが発生しました</td></tr>
</table>
"""
slide("画面詳細設計（状態遷移）", "公開ページ（/）／ 体験チケット操作パネル", body,
      "3状態とも同一URL・同一画面。POST /pay の応答は1秒以内、押してから実機が動き出すまでは5秒以内（非機能要件）。", wide=True)

# ── 8. ライブ映像とAI検出枠 ─────────────────────────────
pins = [
    free_pin(1, 4.5, 20.0),
    free_pin(2, 37.0, 26.5),
    free_pin(3, 32.5, 60.0),
    free_pin(4, 88.0, 5.5),
]
lst = items([
    ("映像", "GET /video_feed（MJPEG）。object-fit: cover で枠いっぱいに表示する"),
    ("検出ラベル", "種別と信頼度（例：person 92%）を枠の上辺に重ねる"),
    ("AI検出枠", "GET /overlay の bbox を 0.4秒ごとに取得して描画する。映像と同じ座標変換を使う"),
    ("LIVE 表示", "配信中であることを示す"),
])
note = ("検出から1.5秒を超えた枠は描かない（古い枠を残さない）。経過に応じて薄くし、次の検出まで滑らかにつなぐ。"
        "バックエンドが一時的に落ちても描画ループは止めず、映像だけは出し続ける。")
slide("画面詳細設計（部分拡大）", "公開ページ（/）／ ライブ映像とAI検出枠",
      shot("hud_zoom.jpg", pins) + lst, note)

# ── 9. ランキング画面 ───────────────────────────────────
pins = [
    pin("ranking_pc", ".ranking-header", 1, dx=1.0, dy=1.0),
    pin("ranking_pc", ".ranking-sync", 2, dx=-2.2, dy=0.2),
    pin("ranking_pc", ".podium-gold", 3, dx=1.2, dy=1.2),
    pin("ranking_pc", ".ranking-list-area", 4, dx=1.2, dy=1.2),
    pin("ranking_pc", ".ranking-stat-main", 5, dx=1.2, dy=1.2),
    pin("ranking_pc", ".ranking-stat-wide", 6, dx=1.2, dy=1.2, idx=0),
    pin("ranking_pc", ".ranking-stat-wide", 7, dx=1.2, dy=1.2, idx=1),
    pin("ranking_pc", ".latest-support-card", 8, dx=1.2, dy=1.2),
]
lst = items([
    ("ヘッダー", "ARGUS SUPPORTER RANKING ／ 稼働状態"),
    ("自動更新の明示", "AUTO SYNC。15秒ごとにページ全体を再読み込みする"),
    ("表彰台 TOP3", "中央が1位。累計チケットと操作回数を表示する"),
    ("4位以下の一覧", "順位・名前・操作回数・累計チケット（上位10名まで）"),
    ("累計チケット", "status='paid' の合計。模擬通貨の総額"),
    ("本日の命令数", "当日に登録されたロボット命令の件数"),
    ("参加人数", "操作した人数（payer_name の種類数）"),
    ("最新の操作", "直近1件の名前・消費チケット・アクション名・時刻"),
])
slide("画面詳細設計（PC・大型ディスプレイ）", "ランキング画面 /ranking",
      shot("ranking_pc.jpg", pins) + lst,
      "観客が操作しない表示専用の画面。会場モニタに常時映し、来場者の参加を促す。")

# ── 10. 管理ダッシュボード（上部）───────────────────────
pins = [
    pin("dash_top", "header", 1, dx=1.0, dy=1.5),
    pin("dash_top", ".summary-card", 2, dx=1.0, dy=1.5, idx=0),
    pin("dash_top", ".summary-card", 3, dx=1.0, dy=1.5, idx=1),
    pin("dash_top", ".summary-card", 4, dx=1.0, dy=1.5, idx=2),
    pin("dash_top", ".card", 5, dx=1.0, dy=1.2, idx=0),
]
lst = items([
    ("ヘッダー", "ARGUS 管理ダッシュボード（運営PC専用）"),
    ("累計チケット", "模擬通貨の合計。展示中の総消費量が分かる"),
    ("取引件数", "transactions の総件数"),
    ("未実行コマンド", "status='pending' の件数。10件でチケット受付を止める"),
    ("ロボット命令キュー", "ID・アクション・発行元（現状は paid のみ）・状態（pending → done）・作成日時。新しい順に20件"),
])
slide("画面詳細設計（PC・運営）", "管理ダッシュボード /dashboard（上部）",
      shot("dash_top.jpg", pins) + lst,
      "展示中に運営が見る唯一の画面。チケット消費 → 命令 → 実行完了 の詰まりをここで検知する。")

# ── 11. 管理ダッシュボード（下部）───────────────────────
body = """
<div class="stack">
  <figure><div class="cap">取引履歴（transactions・新しい順に20件）</div>
    <div class="shot"><img src="img/dash_tx.jpg"><span class="pin" style="left:3.5%;top:16%">1</span></div></figure>
  <figure><div class="cap">AI検出履歴（detections・新しい順に20件）</div>
    <div class="shot"><img src="img/dash_det.jpg"><span class="pin" style="left:3.5%;top:13%">2</span><span class="pin" style="left:7.5%;top:28%">3</span></div></figure>
</div>
"""
lst = items([
    ("取引履歴", "ID・日時・名前・消費チケット・アクション・状態（paid）。ランキングと累計チケットの元データ"),
    ("AI検出履歴", "ID・日時・種類（person / mission_person）・信頼度・静止画ファイル名"),
    ("ダミー検出を追加", "動作確認用リンク。1件登録して同じ画面へ戻る。展示本番では使用しない"),
]).replace('class="items"', 'class="items row"')
slide("画面詳細設計（PC・運営）", "管理ダッシュボード /dashboard（下部）", body + lst,
      "取引 → 命令 → 検出 が同じ時刻で並ぶため、「チケットを使った操作が実際に動いたか」を後から追跡できる。", wide=True)

# ── 12. 共通仕様 ────────────────────────────────────────
body = """
<div class="cols">
<div>
<h3>入力と検証</h3>
<table class="tbl small">
<tr><th>項目</th><th>入力方法</th><th>制限</th></tr>
<tr><td>名前</td><td>テキスト入力（任意）</td><td>24文字まで／未入力は「匿名」</td></tr>
<tr><td>アクション</td><td>ボタン選択のみ</td><td>6種のホワイトリスト。自由入力は受け付けない</td></tr>
<tr><td>応援メッセージ</td><td>API のみ（画面は未使用）</td><td>100文字まで</td></tr>
<tr><td>連打</td><td>—</td><td>同一端末から1.5秒に1回まで</td></tr>
<tr><td>受付停止</td><td>—</td><td>未実行の命令が10件に達したら受け付けない</td></tr>
</table>
<h3>自動更新</h3>
<table class="tbl small">
<tr><th>対象</th><th>取得先</th><th>間隔</th></tr>
<tr><td>AI検出枠</td><td>GET /overlay</td><td>0.4秒</td></tr>
<tr><td>ランキング・直近の操作<br><small>（公開ページのボード）</small></td><td>GET /api/ranking・/api/transactions</td><td>5秒</td></tr>
<tr><td>ランキング画面</td><td>GET /ranking（ページ全体を再読込）</td><td>15秒</td></tr>
<tr><td>ライブ映像</td><td>GET /video_feed</td><td>MJPEG（接続しっぱなし）</td></tr>
</table>
</div>
<div>
<h3>表示の共通ルール</h3>
<ul class="bullets">
<li>観客向け画面（公開ページ・ランキング）は背景写真に暗色（rgba(3,7,18,…)）を重ね、文字 #e5e7eb ＋シアン #67e8f9 のアクセント。等幅フォント（JetBrains Mono）で計器らしく見せる。</li>
<li>運営画面は明色（#f2f4f8）＋白カード。数値と表の読みやすさを優先する。</li>
<li>金額の単位は「チケット」「TKT」と書き、円記号は使わない（模擬通貨であることを誤解させないため）。</li>
<li>観客が入力した名前は必ず文字列として扱い、HTML として描画しない。</li>
<li>エラーは画面を遷移させず、操作した場所のすぐ下に理由を日本語で出す。</li>
</ul>
<h3>Ver1.0 で作らないもの</h3>
<ul class="bullets">
<li>会員登録・ログイン画面（その場で数十秒の体験を優先するため）</li>
<li>実カード決済・返金の画面（体験チケットで主題を再現できるため）</li>
<li>多言語 UI・録画閲覧・インターネット公開</li>
</ul>
<h3>未実装（今後の追加）</h3>
<ul class="bullets">
<li>「人を探す」ミッションの成功演出。GET /mission/latest を見て、成功時に公開ページで演出を出し、チケットを使った人へ結果を知らせる。</li>
</ul>
</div>
</div>
"""
slide("共通仕様", "全画面に共通するルール", body, "", wide=True)


# ── HTML 組み立て ───────────────────────────────────────
CSS = """
@page { size: 338.67mm 190.5mm; margin: 0; }
* { box-sizing: border-box; }
body { margin:0; background:#fff; color:#1b2434;
       font-family:"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { position:relative; width:1280px; height:720px; padding:26px 44px 56px; page-break-after:always; overflow:hidden; }
.page:last-child { page-break-after:auto; }
.doc-title { position:absolute; right:44px; top:22px; font-size:15px; font-weight:700; color:#1b2434; letter-spacing:.02em; }
.label { font-size:21px; font-weight:700; color:#2f6fbf; margin:34px 0 2px; }
.name  { font-size:15px; font-weight:600; color:#1b2434; margin:0 0 12px; padding-left:16px; }
.body { display:flex; gap:22px; height:508px; }
.body.wide { display:block; height:auto; }
.shot { position:relative; flex:0 0 700px; align-self:flex-start; border:1px solid #c7d0e0; }
.shot.tall { flex:0 0 262px; }
.shot img { display:block; width:100%; }
.body > .items { flex:1; }
.full { text-align:center; }
.full img { max-width:1176px; max-height:486px; border:1px solid #c7d0e0; }
.pin { position:absolute; width:19px; height:19px; margin:-9px 0 0 -9px; border-radius:50%;
       background:#e8397a; color:#fff; font-size:11.5px; font-weight:700; line-height:19px;
       text-align:center; box-shadow:0 0 0 1.5px #fff; }
ol.items { list-style:none; margin:0; padding:0; }
ol.items li { display:flex; gap:7px; margin-bottom:8px; font-size:12.5px; line-height:1.45; }
ol.items .no { flex:0 0 17px; height:17px; border-radius:50%; background:#e8397a; color:#fff;
               font-size:10.5px; font-weight:700; line-height:17px; text-align:center; margin-top:1px; }
ol.items small { color:#5b6b8c; font-size:11px; line-height:1.5; }
.tbl { width:100%; border-collapse:collapse; font-size:12.5px; margin:4px 0 12px; }
.tbl th { background:#eef2f9; color:#1b2434; font-weight:700; text-align:left; }
.tbl th, .tbl td { border:1px solid #c7d0e0; padding:6px 9px; vertical-align:top; }
.tbl.small { font-size:11.5px; }
.tbl.small th, .tbl.small td { padding:4px 7px; }
.states { display:flex; gap:14px; margin-bottom:10px; }
.states figure { margin:0; flex:1; }
.states figure { text-align:center; }
.states img { height:236px; width:auto; border:1px solid #c7d0e0; display:inline-block; }
.cap { font-size:12px; font-weight:700; color:#2f6fbf; margin-bottom:4px; }
.states figcaption { font-size:10.5px; color:#5b6b8c; line-height:1.5; margin-top:5px; text-align:left; }
.stack { display:flex; gap:16px; margin-bottom:10px; align-items:flex-start; }
.stack img { display:block; width:100%; }
.stack figure { text-align:left; }
ol.items.row { columns:3; column-gap:22px; }
ol.items.row li { break-inside:avoid; }
.stack figure { margin:0; flex:1; }
.stack .shot { flex:none; }
.cols { display:flex; gap:26px; }
.cols > div { flex:1; }
h3 { font-size:13.5px; color:#2f6fbf; margin:2px 0 5px; border-left:4px solid #2f6fbf; padding-left:7px; }
.bullets { margin:0 0 12px; padding-left:18px; font-size:12px; line-height:1.6; }
.bullets li { margin-bottom:3px; }
.note { position:absolute; left:44px; right:44px; bottom:30px; font-size:11px; color:#5b6b8c; line-height:1.55; }
.foot { position:absolute; left:44px; right:44px; bottom:12px; display:flex; gap:28px;
        font-size:10.5px; color:#7a879e; }
.foot .pno { margin-left:auto; color:#1b2434; }
/* 表紙 */
.cover { display:flex; flex-direction:column; justify-content:center; height:600px; }
.cover .eyebrow { font-size:13px; letter-spacing:.22em; color:#2f6fbf; font-weight:700; }
.cover h1 { font-size:40px; margin:10px 0 6px; letter-spacing:.01em; }
.cover h2 { font-size:19px; font-weight:500; color:#41506b; margin:0 0 26px; }
.cover .meta { display:flex; gap:44px; font-size:13px; color:#41506b; line-height:1.9; }
.cover .meta b { color:#1b2434; }
.cover .rule { height:3px; width:96px; background:#e8397a; margin:0 0 20px; }
"""

parts = ['<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body>'
         % (html.escape(DOCTTL), CSS)]

pno = 0
for label, name, body, note, wide in slides:
    if label == "__cover__":
        parts.append("""
<div class="page">
  <div class="cover">
    <p class="eyebrow">HEW 2026 ／ IH19 課題No06 設計</p>
    <div class="rule"></div>
    <h1>『ARGUS』画面設計書</h1>
    <h2>体験チケット連動型 AI 相棒ロボット（6脚）とライブ配信 Web サービス　Ver 1.0（HEW 展示版）</h2>
    <div class="meta">
      <div><b>対象画面</b><br>公開ページ /<br>ランキング /ranking<br>管理ダッシュボード /dashboard</div>
      <div><b>利用端末</b><br>観客：スマートフォン（iOS Safari / Android Chrome・縦画面）<br>会場モニタ・運営：PC（Chrome）<br>サーバ：PC または Raspberry Pi 5（Flask + SQLite）</div>
      <div><b>前提</b><br>会場ローカル LAN のみで動作<br>体験チケットは模擬通貨（実際の金銭は発生しない）<br>会員登録・ログインはスコープ外</div>
    </div>
  </div>
  <div class="foot"><span>最終保存日付：%s</span><span>チーム名：%s</span><span>改訂番号：%s</span><span class="pno">表紙</span></div>
</div>""" % (DATE, TEAM, REV))
        continue

    pno += 1
    parts.append('<div class="page"><div class="doc-title">%s</div>' % html.escape(DOCTTL))
    parts.append('<p class="label">%s</p><p class="name">%s</p>' % (label, name))
    parts.append('<div class="body%s">%s</div>' % (" wide" if wide else "", body))
    if note:
        parts.append('<div class="note">%s</div>' % note)
    parts.append('<div class="foot"><span>最終保存日付：%s</span><span>チーム名：%s</span><span>改訂番号：%s</span><span class="pno">%d</span></div></div>'
                 % (DATE, TEAM, REV, pno))

parts.append("</body></html>")
open(os.path.join(BASE, "doc", "design.html"), "w").write("".join(parts))
print("pages:", pno + 1)
