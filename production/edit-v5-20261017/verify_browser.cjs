const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const {chromium}=require('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=__dirname;
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href,{timeout:60000});
  await page.waitForFunction(()=>['film','fullAudio','endingAudio'].every(id=>Number.isFinite(document.getElementById(id).duration)));
  const durations=await page.evaluate(()=>Object.fromEntries(['film','fullAudio','endingAudio'].map(id=>[id,document.getElementById(id).duration])));
  if(Math.abs(durations.film-215.64)>.01)throw new Error('Duration mismatch');
  const seeks=[];
  for(const [id,target] of [['water',28.68],['ascent',55.24],['tail',212.64]]){
   const actual=await page.evaluate(async({id,target})=>{const m=document.getElementById('film');const p=new Promise(resolve=>m.addEventListener('seeked',()=>{m.pause();resolve(m.currentTime)},{once:true}));document.getElementById(id).click();return p},{id,target});
   if(Math.abs(actual-target)>.1)throw new Error('Seek mismatch');seeks.push({id,target,actual});
  }
  const exclusive=await page.evaluate(async()=>{const a=document.getElementById('film'),b=document.getElementById('fullAudio');await a.play();await b.play();const ok=a.paused&&!b.paused;b.pause();return ok});
  await page.locator('#film').evaluate(m=>{m.currentTime=62.4;return new Promise(resolve=>m.addEventListener('seeked',resolve,{once:true}))});
  await page.screenshot({path:path.join(root,'preview-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
  const mediaErrors=await page.evaluate(()=>[...document.querySelectorAll('video,audio')].map(m=>({id:m.id,error:m.error?.message||null})));
  await page.screenshot({path:path.join(root,'preview-mobile.png'),fullPage:true});
  await page.goto(pathToFileURL(path.resolve(root,'../../17_项目总览看板.html')).href);
  const dashboard=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,latest:document.querySelector('header a').getAttribute('href')}));
  const result={durations,seeks,exclusive,mobile,mediaErrors,dashboard,errors};
  if(!exclusive||mobile.scrollWidth>390||dashboard.scrollWidth>390||!dashboard.latest.includes('edit-v5-20261017')||errors.length||mediaErrors.some(x=>x.error))throw new Error(JSON.stringify(result));
  fs.writeFileSync(path.join(root,'browser-verification.json'),JSON.stringify(result,null,2));
  console.log('BROWSER_VERIFIED',JSON.stringify(result));
 }finally{if(browser)await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
