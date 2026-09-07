const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(path.resolve('node_modules/playwright'));
(async()=>{
  const config=JSON.parse(fs.readFileSync(String.raw`\\wsl$\Ubuntu\tmp\insar-pilot-browser-state\service.json`,'utf8'));
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const context=await browser.newContext({viewport:{width:1366,height:900}});
    await context.addInitScript(token=>{
      sessionStorage.setItem('pilot-token',token);
      localStorage.setItem('pilot-language','zh');
      localStorage.setItem('pilot-inspector-collapsed','true');
    },config.token);
    const page=await context.newPage();
    await page.goto('http://127.0.0.1:'+config.port+'/');
    await page.getByRole('toolbar').getByRole('button',{name:'检索',exact:true}).click();
    await page.waitForFunction(()=>['ready','partial','unavailable'].includes(document.querySelector('[data-testid="search-map"]')?.getAttribute('data-imagery-state')),{},{timeout:25000});
    const state=await page.getByTestId('search-map').getAttribute('data-imagery-state');
    const loaded=await page.locator('.leaflet-tile-loaded').count();
    await page.screenshot({path:'../artifacts/p01-shell-2026-09-06/live-zh.png'});
    await page.getByRole('button',{name:'Toggle theme',exact:true}).click();
    await page.screenshot({path:'../artifacts/p01-shell-2026-09-06/live-zh-dark.png'});
    fs.writeFileSync('../artifacts/p01-shell-2026-09-06/live-check.json',JSON.stringify({imagery_state:state,loaded_tiles:loaded,primary_pages:await page.getByTestId('primary-pages').getByRole('tab').count(),readiness:await page.locator('.readiness-summary').innerText(),viewport:{width:1366,height:900}},null,2));
    console.log(JSON.stringify({imagery_state:state,loaded_tiles:loaded,primary_pages:5}));
    await context.close();
  } finally {await browser.close();}
})().catch(()=>{console.error('Live UI check failed; no session details logged.');process.exitCode=1});
