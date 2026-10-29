const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {chromium} = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const root = __dirname;
  const exe = [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe'
  ].find(x => fs.existsSync(x));
  const browser = await chromium.launch({headless: true, executablePath: exe});
  const page = await browser.newPage({viewport: {width: 1440, height: 1150}, deviceScaleFactor: 1});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const audio = JSON.parse(fs.readFileSync(path.join(root,'audio-verification.json'),'utf8'));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href, {waitUntil:'load',timeout:60000});
  await page.waitForFunction(() => [...document.querySelectorAll('video,audio')].every(m => Number.isFinite(m.duration)), {timeout:30000});
  const metadata = await page.evaluate(() => [...document.querySelectorAll('video,audio')].map(m => ({id:m.id,duration:m.duration,readyState:m.readyState,error:m.error?.message||null})));
  await page.screenshot({path:path.join(root,'verify/page-desktop.png'),fullPage:false});
  await page.getByRole('button',{name:'重点听结尾'}).click();
  await page.waitForFunction(t => {
    const m=document.getElementById('film');
    return !m.paused && m.currentTime >= t && m.currentTime < t+5;
  },audio.ending_start,{timeout:20000});
  await page.waitForFunction(() => document.getElementById('film').currentTime>145);
  const ending = await page.evaluate(() => ({time:document.getElementById('film').currentTime,paused:document.getElementById('film').paused,activeChapter:document.querySelector('.chapter.active b')?.textContent,errors:[...document.querySelectorAll('video,audio')].map(m=>m.error?.message||null)}));
  await page.locator('#film').evaluate(m=>m.pause());
  await page.screenshot({path:path.join(root,'verify/page-ending.png'),fullPage:false});
  await page.locator('#fullAudio').evaluate(m=>m.play());
  await page.waitForFunction(()=>!document.getElementById('fullAudio').paused);
  const exclusive=await page.evaluate(()=>document.getElementById('film').paused&&document.getElementById('endingAudio').paused);
  await page.locator('#fullAudio').evaluate(m=>m.pause());
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(root,'verify/page-mobile.png'),fullPage:true});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,chapters:document.querySelectorAll('.chapter').length,paragraphs:document.querySelectorAll('.line').length}));
  const report={metadata,ending,exclusivePlayback:exclusive,mobile,errors};
  fs.writeFileSync(path.join(root,'browser-verification.json'),JSON.stringify(report,null,2));
  await browser.close();
  if(errors.length||!exclusive||mobile.scrollWidth>mobile.width||metadata.some(m=>m.error)) throw new Error('Browser checks failed');
  console.log(JSON.stringify(report));
})().catch(e=>{console.error(e.message);process.exit(1)});
