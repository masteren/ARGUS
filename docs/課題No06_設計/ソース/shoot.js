const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const B = 'http://127.0.0.1:5077';

const targets = [
  { name: 'public_pc',    url: '/',          w: 1440, h: 900,  dsf: 2, full: false },
  { name: 'public_sp',    url: '/',          w: 430,  h: 932,  dsf: 2, full: true  },
  { name: 'ranking_pc',   url: '/ranking',   w: 1440, h: 900,  dsf: 2, full: false },
  { name: 'dashboard_pc', url: '/dashboard', w: 1440, h: 900,  dsf: 2, full: true  },
];

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
    args: ['--hide-scrollbars', '--force-color-profile=srgb'] });
  for (const t of targets) {
    const page = await browser.newPage();
    await page.setViewport({ width: t.w, height: t.h, deviceScaleFactor: t.dsf, isMobile: t.w < 600, hasTouch: t.w < 600 });
    await page.goto(B + t.url, { waitUntil: 'networkidle2', timeout: 30000 }).catch(e => console.log('nav', e.message));
    await new Promise(r => setTimeout(r, 2500));
    await page.evaluate(() => window.dispatchEvent(new Event('resize')));
    await new Promise(r => setTimeout(r, 1800));
    await page.screenshot({ path: `shots/${t.name}.png`, fullPage: t.full });
    console.log('shot', t.name);
    await page.close();
  }
  await browser.close();
})();
