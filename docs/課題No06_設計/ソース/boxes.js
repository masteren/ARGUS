const puppeteer = require('puppeteer-core');
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const B = 'http://127.0.0.1:5077';
// login: shoot.js と同じく、公開ページはログイン中（seed.py の「ゆい」）の状態で座標を採る
const jobs = [
  { name:'public_pc', url:'/', w:1440, h:900, full:false, login:true, sel:['.site-header .header-status','.robot-card','.status-list','.live-panel .panel-header','.live-screen','.board-panel','#board_ranking','#board_feed','.section-title','.ticket-notice','#account_member','#account_balance','#open_shop','#logout_button','.action-button[data-action="forward"]','.action-button[data-action="search_person"]','#result'] },
  { name:'public_sp', url:'/', w:430, h:932, full:true, mobile:true, login:true, sel:['.site-header','.live-panel','.payment-panel','.live-screen','.ticket-notice','#account_member','#account_balance','#open_shop','#logout_button','.action-grid','.action-button[data-action="search_person"]','#result','.board-panel','#board_ranking','#board_feed','.robot-card','.status-list'] },
  { name:'ranking_pc', url:'/ranking', w:1440, h:900, full:false, sel:['.ranking-header','.supporter-panel','.podium-grid','.podium-gold','.ranking-list-area','.ranking-stats-panel','.ranking-stat-main','.ranking-stat-wide','.latest-support-card','.ranking-sync'] },
  { name:'dashboard_pc', url:'/dashboard', w:1440, h:900, full:true, sel:['header','.summary','.summary-card','.card','.card table'] },
];
(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args:['--hide-scrollbars','--no-sandbox'] });
  const out = {};
  for (const j of jobs) {
    const ctx = await browser.createBrowserContext();
    const p = await ctx.newPage();
    await p.setViewport({ width:j.w, height:j.h, deviceScaleFactor:1, isMobile:!!j.mobile, hasTouch:!!j.mobile });
    if (j.login) {
      await p.goto(B + '/health');
      await p.evaluate(() => fetch('/auth/login', { method:'POST', headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ name:'ゆい', pin:'1234' }) }));
    }
    await p.goto(B + j.url, { waitUntil:'networkidle2' });
    await new Promise(r=>setTimeout(r,1200));
    const dims = await p.evaluate(() => ({ dw: document.documentElement.scrollWidth, dh: document.documentElement.scrollHeight }));
    const H = j.full ? dims.dh : j.h, W = j.full ? dims.dw : j.w;
    out[j.name] = { W, H, els: {} };
    for (const s of j.sel) {
      const all = await p.$$eval(s, els => els.map(e => { const r = e.getBoundingClientRect(); return { x:r.x+window.scrollX, y:r.y+window.scrollY, w:r.width, h:r.height }; })).catch(()=>[]);
      out[j.name].els[s] = all.map(r => ({
        l:+(r.x/W*100).toFixed(2), t:+(r.y/H*100).toFixed(2),
        cx:+((r.x+r.w/2)/W*100).toFixed(2), cy:+((r.y+r.h/2)/H*100).toFixed(2),
        rw:+(r.w/W*100).toFixed(2), rh:+(r.h/H*100).toFixed(2) }));
    }
    await ctx.close();
  }
  require('fs').writeFileSync('boxes.json', JSON.stringify(out,null,1));
  await browser.close();
  console.log('ok');
})();
