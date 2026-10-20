const puppeteer = require('puppeteer-core');
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const B = 'http://127.0.0.1:5077';

// login: 撮影前に seed.py で作った会員でログインしておく（公開ページはログイン中の状態で撮る）
const targets = [
  { name: 'public_pc',    url: '/',          w: 1440, h: 900,  dsf: 2, full: false, login: true, hud: true },
  { name: 'public_sp',    url: '/',          w: 430,  h: 932,  dsf: 2, full: true,  login: true },
  { name: 'ranking_pc',   url: '/ranking',   w: 1440, h: 900,  dsf: 2, full: false },
  { name: 'dashboard_pc', url: '/dashboard', w: 1440, h: 900,  dsf: 2, full: true  },
];

// AI検出枠は「1.5秒以内の検出」だけが描かれるので、撮る直前に1件送る
async function freshDetection() {
  await fetch(B + '/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'person', confidence: 0.92, image: 'detections/capture_hud.jpg',
      bbox: [232, 142, 350, 424], frame_wh: [640, 480] }) });
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
    args: ['--hide-scrollbars', '--force-color-profile=srgb', '--no-sandbox'] });
  for (const t of targets) {
    const ctx = await browser.createBrowserContext();
    const page = await ctx.newPage();
    await page.setViewport({ width: t.w, height: t.h, deviceScaleFactor: t.dsf, isMobile: t.w < 600, hasTouch: t.w < 600 });
    if (t.login) {
      await page.goto(B + '/health');
      await page.evaluate(() => fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'ゆい', pin: '1234' }) }));
    }
    await page.goto(B + t.url, { waitUntil: 'networkidle2', timeout: 30000 }).catch(e => console.log('nav', e.message));
    await new Promise(r => setTimeout(r, 2000));
    await page.evaluate(() => window.dispatchEvent(new Event('resize')));
    if (t.hud) { await freshDetection(); }
    await new Promise(r => setTimeout(r, t.hud ? 450 : 900));
    await page.screenshot({ path: `shots/${t.name}.png`, fullPage: t.full });
    console.log('shot', t.name);
    await ctx.close();
  }
  await browser.close();
})();
