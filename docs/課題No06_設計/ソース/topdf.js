const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
(async () => {
  const b = await puppeteer.launch({ executablePath: CHROME, headless:'new', args:['--hide-scrollbars','--allow-file-access-from-files'] });
  const p = await b.newPage();
  await p.setViewport({ width:1280, height:720, deviceScaleFactor:2 });
  const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.goto('file://' + process.argv[2], { waitUntil:'networkidle0', timeout:120000 });
  await new Promise(r=>setTimeout(r,1500));
  // 各ページの中身がはみ出していないか確認する
  const over = await p.evaluate(() => {
    const out=[];
    document.querySelectorAll('.page').forEach((pg,i)=>{
      const pr=pg.getBoundingClientRect();
      pg.querySelectorAll('.body, .note, .full img, .shot, .tbl').forEach(el=>{
        const r=el.getBoundingClientRect();
        if (r.bottom > pr.bottom-8 || r.right > pr.right-4) out.push({page:i+1, cls:el.className||el.tagName, bottom:Math.round(r.bottom-pr.top), right:Math.round(r.right-pr.left)});
      });
    });
    return out;
  });
  console.log('overflow:', JSON.stringify(over));
  await p.pdf({ path: process.argv[3], width:'1280px', height:'720px', printBackground:true, pageRanges:'' });
  console.log('errors', errs.slice(0,3));
  await b.close();
})();
