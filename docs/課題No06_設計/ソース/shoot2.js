const puppeteer = require('puppeteer-core');
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const B = 'http://127.0.0.1:5077';
const sleep = ms => new Promise(r => setTimeout(r, ms));

// スマホ（430x932）で、ログイン・購入パネルと操作パネルの各状態を撮る。
// パネルは .modal-card の周囲だけ、操作パネルは .payment-panel だけを切り出す。
(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
    args: ['--hide-scrollbars', '--force-color-profile=srgb', '--no-sandbox'] });

  async function newPhone() {
    const ctx = await browser.createBrowserContext();
    const p = await ctx.newPage();
    await p.setViewport({ width: 430, height: 932, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    return { ctx, p };
  }
  async function open(p) {
    await p.goto(B + '/', { waitUntil: 'networkidle2' });
    await sleep(1200);
  }
  async function login(p, name, pin) {
    await p.goto(B + '/health');
    await p.evaluate((n, k) => fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: n, pin: k }) }), name, pin);
  }
  async function shotEl(p, sel, path, pad = 12, untilSel = null) {
    // clip は文書座標。固定表示のパネル（.modal）以外はスクロール量を足す
    const r = await p.$eval(sel, e => { const b = e.getBoundingClientRect(); const off = e.closest('.modal') ? 0 : window.scrollY;
      return { x: b.x, y: b.y + off, w: b.width, h: b.height, off }; });
    let h = r.h;
    if (untilSel) {
      const u = await p.$eval(untilSel, e => e.getBoundingClientRect().bottom + window.scrollY);
      h = u - r.y + 14;
    }
    await p.screenshot({ path, clip: { x: Math.max(0, r.x - pad), y: Math.max(0, r.y - pad), width: r.w + pad * 2, height: h + pad * 2 } });
    console.log('shot', path);
  }
  async function panelInView(p) {
    await p.$eval('.payment-panel', e => e.scrollIntoView({ block: 'start' }));
    await sleep(400);
  }

  // ── ログイン・新規登録 ─────────────────────────────
  {
    const { ctx, p } = await newPhone();
    await open(p);
    await panelInView(p);
    await shotEl(p, '.payment-panel', 'shots/st_guest.png', 0, '#account_guest');

    await p.click('#open_login');
    await sleep(300);
    await p.type('#auth_name', 'ゆい');
    await p.type('#auth_pin', '1234');
    await shotEl(p, '#login_modal .modal-card', 'shots/auth_login.png');

    await p.evaluate(() => setAuthMode('register'));
    await p.$eval('#auth_name', e => { e.value = ''; });
    await p.$eval('#auth_pin', e => { e.value = ''; });
    await p.type('#auth_name', 'あおい');
    await p.type('#auth_pin', '2580');
    await shotEl(p, '#login_modal .modal-card', 'shots/auth_register.png');

    await p.evaluate(() => setAuthMode('login'));
    await p.$eval('#auth_name', e => { e.value = ''; });
    await p.$eval('#auth_pin', e => { e.value = ''; });
    await p.type('#auth_name', 'ゆい');
    await p.type('#auth_pin', '0000');
    await p.click('#auth_submit');
    await sleep(700);
    console.log('auth error:', await p.$eval('#auth_error', e => e.textContent));
    await shotEl(p, '#login_modal .modal-card', 'shots/auth_error.png');
    await ctx.close();
  }

  // ── 残高不足からの案内（402）→ パック選択 → 確認 → 完了 ──
  {
    const { ctx, p } = await newPhone();
    await login(p, 'たいが', '7777');          // seed.py で残高 400
    await open(p);
    await panelInView(p);
    await p.click('.action-button[data-action="search_person"]');   // 500 必要 → 402
    await sleep(900);
    console.log('402:', await p.$eval('#shop_error', e => e.textContent));
    await shotEl(p, '#shop_modal .modal-card', 'shots/shop_short.png');

    await p.evaluate(() => openShop());
    await sleep(300);
    await shotEl(p, '#shop_modal .modal-card', 'shots/shop_select.png');

    await p.click('.pack-card[data-pack="pack_500"]');
    await sleep(300);
    await shotEl(p, '#shop_modal .modal-card', 'shots/shop_confirm.png');

    await p.click('#confirm_submit');
    await sleep(900);
    await panelInView(p);
    console.log('done:', await p.$eval('#result', e => e.textContent));
    await shotEl(p, '.payment-panel', 'shots/shop_done.png', 0);
    await ctx.close();
  }

  // ── 操作パネルの状態：ログイン中 → 受付 → エラー ──
  {
    const { ctx, p } = await newPhone();
    await login(p, 'ゆい', '1234');
    await open(p);
    await panelInView(p);
    await shotEl(p, '.payment-panel', 'shots/st_ready.png', 0);

    await p.click('.action-button[data-action="bow"]');
    await sleep(1200);
    console.log('result:', await p.$eval('#result', e => e.textContent));
    await shotEl(p, '.payment-panel', 'shots/st_result.png', 0);

    // 未実行10件で受付を止めたときの表示（文言は app.py の 429 と同じ）
    await p.evaluate(() => {
      document.getElementById('result').textContent = 'ERROR: ARGUS が混み合っています。少し待ってからお試しください';
    });
    await shotEl(p, '.payment-panel', 'shots/st_error.png', 0);
    await ctx.close();
  }

  await browser.close();
})();
