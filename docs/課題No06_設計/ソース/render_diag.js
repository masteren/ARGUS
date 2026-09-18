const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const file = process.argv[2], out = process.argv[3], w = +(process.argv[4]||1600), svgW = +(process.argv[5]||0);
(async () => {
  const b = await puppeteer.launch({ executablePath: CHROME, headless:'new', args:['--hide-scrollbars'] });
  const p = await b.newPage();
  await p.setViewport({ width:w, height:1000, deviceScaleFactor:2 });
  const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.goto('file://'+file, { waitUntil:'networkidle2', timeout:60000 });
  await new Promise(r=>setTimeout(r,3500));
  if (svgW) {
    await p.evaluate((sw)=>{ document.querySelectorAll('#d svg').forEach(s=>{ s.style.maxWidth='none'; s.style.width=sw+'px'; s.style.height='auto'; }); }, svgW);
    await new Promise(r=>setTimeout(r,800));
  }
  const box = await p.evaluate(()=>{ const r=document.body.getBoundingClientRect();
    return { x:0, y:0, width: Math.ceil(Math.max(document.body.scrollWidth, r.width)), height: Math.ceil(document.body.scrollHeight) }; });
  await p.setViewport({ width: Math.max(box.width, w), height: box.height, deviceScaleFactor:2 });
  await new Promise(r=>setTimeout(r,600));
  await p.screenshot({ path: out, clip: { x:0, y:0, width: box.width, height: box.height } });
  console.log('box', JSON.stringify(box), 'errors', errs.slice(0,2));
  await b.close();
})();
