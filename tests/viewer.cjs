// Isolated headless browser tests; no user keyboard/mouse control.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {createRequire} = require('node:module');
const runtime = process.env.UI_NODE_MODULES;
if (!runtime) throw new Error('Set UI_NODE_MODULES to a directory containing playwright');
const {chromium} = createRequire(path.join(runtime, 'package.json'))('playwright');
const root=path.resolve(__dirname,'..');
const primary=path.resolve(root,process.env.UI_REVIEW_PACKAGE||'output/workbench');
const artifacts=path.resolve(root,process.env.UI_TEST_OUTPUT||'output/browser-current');
fs.mkdirSync(artifacts,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.UI_BROWSER_CHANNEL||undefined});
 const results=[];
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
  const errors=[], network=[];
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});
  await page.goto(pathToFileURL(path.join(primary,'index.html')).href);
  await page.waitForFunction(()=>window.viewerReady);
  assert.equal(await page.locator('#system option').count(),2);
  const baseline=await page.evaluate(()=>window.lastDiff);
  assert(baseline.count>0);
  await page.evaluate(()=>{document.getElementById('mode').value='overlay';document.getElementById('mode').dispatchEvent(new Event('input'))});
  assert.equal(await page.locator('#rightTitle').textContent(),'参考与组装透明叠加');
  await page.evaluate(()=>{document.getElementById('mode').value='diff';document.getElementById('threshold').value='1';document.getElementById('threshold').dispatchEvent(new Event('input'))});
  assert.equal(await page.evaluate(()=>window.lastDiff.count),0);
  await page.evaluate(()=>{document.getElementById('threshold').value='0.1';document.getElementById('threshold').dispatchEvent(new Event('input'));document.getElementById('zoom').value='2';document.getElementById('zoom').dispatchEvent(new Event('input'));document.getElementById('left').scrollLeft=90;document.getElementById('left').scrollTop=60});
  await page.waitForFunction(()=>document.getElementById('right').scrollLeft===document.getElementById('left').scrollLeft);
  await page.evaluate(()=>{document.getElementById('state').value='disabled';document.getElementById('state').dispatchEvent(new Event('change'))});
  await page.waitForFunction(()=>document.getElementById('identity').textContent.includes('/ disabled'));
  await page.waitForTimeout(250);
  const download=page.waitForEvent('download');
  await page.evaluate(()=>document.getElementById('export').click());
  await (await download).saveAs(path.join(artifacts,'exported-review.png'));
  const metadata=page.waitForEvent('download');
  await page.evaluate(()=>document.getElementById('metadata').click());
  await (await metadata).saveAs(path.join(artifacts,'feedback.json'));
  const info=JSON.parse(fs.readFileSync(path.join(artifacts,'feedback.json')));
  assert.equal(info.state,'disabled');assert.equal(info.reference_sha256.length,64);
  await page.evaluate(()=>{document.getElementById('bounds').checked=true;document.getElementById('bounds').dispatchEvent(new Event('input'))});
  await page.evaluate(()=>{document.getElementById('zoom').value='0.8';document.getElementById('zoom').dispatchEvent(new Event('input'));document.getElementById('left').scrollLeft=0;document.getElementById('left').scrollTop=0});
  await page.screenshot({path:path.join(artifacts,'browser.png'),fullPage:true});
  await page.evaluate(()=>{document.getElementById('system').value='settings';document.getElementById('system').dispatchEvent(new Event('change'))});
  await page.waitForFunction(()=>document.getElementById('identity').textContent.includes('settings / Settings'));
  results.push({package:primary,states:await page.locator('#state option').count(),systems:2,offline:true,exports:true,sync_scroll:true});
  for(const folder of (process.env.UI_ADDITIONAL_PACKAGES||'output/reference-workbench|output/alternate-workbench').split('|')){
   await page.goto(pathToFileURL(path.resolve(root,folder,'index.html')).href);
   await page.waitForFunction(()=>window.viewerReady);
   await page.evaluate(()=>{document.getElementById('mode').value='diff';document.getElementById('mode').dispatchEvent(new Event('input'))});
   await page.screenshot({path:path.join(artifacts,path.basename(folder)+'-'+results.length+'.png'),fullPage:true});
   results.push({package:folder,offline:true,diff:await page.evaluate(()=>window.lastDiff)});
  }
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  fs.writeFileSync(path.join(artifacts,'browser-tests.json'),JSON.stringify({passed:true,errors,network,results},null,2));
  console.log(JSON.stringify({passed:true,results}));
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
