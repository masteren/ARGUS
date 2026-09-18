const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const jobs = [
  { name:'public_pc', url:'/', w:1440, h:900, full:false, sel:['.site-header .header-status','.robot-card','.status-list','.live-panel .panel-header','.live-screen','.board-panel','#board_ranking','#board_feed','.section-title','.ticket-notice','#payer_name','.action-button[data-action="forward"]','.action-button[data-action="search_person"]','#result'] },
  { name:'public_sp', url:'/', w:430, h:932, full:true, mobile:true, sel:['.site-header','.live-panel','.live-screen','#payer_name','.action-grid','.action-button[data-action="search_person"]','#result','.board-panel','#board_ranking','#board_feed','.robot-card','.status-list','.ticket-notice'] },
  { name:'ranking_pc', url:'/ranking', w:1440, h:900, full:false, sel:['.ranking-header','.supporter-panel','.podium-grid','.podium-gold','.ranking-list-area','.ranking-stats-panel','.ranking-stat-main','.ranking-stat-wide','.latest-support-card','.ranking-sync'] },
  { name:'dashboard_pc', url:'/dashboard', w:1440, h:900, full:true, sel:['header','.summary','.summary-card','.card'] },
];
(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args:['--hide-scrollbars'] });
  const out = {};
  for (const j of jobs) {
    const p = await browser.newPage();
    await p.setViewport({ width:j.w, height:j.h, deviceScaleFactor:1, isMobile:!!j.mobile, hasTouch:!!j.mobile });
    await p.goto('http://127.0.0.1:5077'+j.url, { waitUntil:'networkidle2' });
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
    await p.close();
  }
  require('fs').writeFileSync('boxes.json', JSON.stringify(out,null,1));
  console.log('ok');
})();
