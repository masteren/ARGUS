const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
    args: ['--hide-scrollbars','--force-color-profile=srgb'] });
  // 1) スマホ：名前入力 → 「お辞儀」押下後の受付メッセージ
  const p = await browser.newPage();
  await p.setViewport({ width: 430, height: 932, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://127.0.0.1:5077/', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 1500));
  await p.type('#payer_name', 'ゆい');
  await p.screenshot({ path: 'shots/public_sp_input.png', fullPage: true });
  await p.click('.action-button[data-action="bow"]');
  await new Promise(r => setTimeout(r, 1500));
  await p.evaluate(() => window.dispatchEvent(new Event('resize')));
  await new Promise(r => setTimeout(r, 1200));
  await p.screenshot({ path: 'shots/public_sp_result.png', fullPage: true });
  console.log('result text:', await p.$eval('#result', e => e.textContent));
  // 2) PC：エラー時（存在しないアクション）の表示
  await p.evaluate(() => {
    const r = document.getElementById('result');
    r.textContent = 'ERROR: ARGUS が混み合っています。少し待ってからお試しください';
  });
  await p.screenshot({ path: 'shots/public_sp_error.png', fullPage: true });
  await browser.close();
})();
