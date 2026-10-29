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
  if(Math.abs(durations.film-215.64)>.01)throw new Error('film duration');
  await page.screenshot({path:path.join(root,'preview-desktop.png'),fullPage:true});
  const seek=[];
  for(const [id,time] of [['ending',147.48],['last18',197.64],['tail',212.64]]){
   await page.locator('#'+id).click();
   await page.waitForFunction(t=>{const m=document.getElementById('film');return !m.paused&&Math.abs(m.currentTime-t)<.8},time);
   const actual=await page.locator('#film').evaluate(m=>{m.pause();return m.currentTime});seek.push({button:id,target:time,actual});
  }
  await page.locator('#film').evaluate(m=>{m.currentTime=214;return new Promise(resolve=>m.addEventListener('seeked',resolve,{once:true}))});
  await page.locator('#film').screenshot({path:path.join(root,'preview-tail.png')});
  const exclusive=await page.evaluate(async()=>{
   const film=document.getElementById('film'),full=document.getElementById('fullAudio'),ending=document.getElementById('endingAudio');
   await film.play();await full.play();const first=film.paused&&!full.paused;await ending.play();const second=full.paused&&!ending.paused;ending.pause();return first&&second;
  });
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
  await page.screenshot({path:path.join(root,'preview-mobile.png'),fullPage:true});
  const mediaErrors=await page.evaluate(()=>['film','fullAudio','endingAudio'].map(id=>({id,error:document.getElementById(id).error?.message||null})));
  await page.goto(pathToFileURL(path.resolve(root,'../../17_项目总览看板.html')).href);
  const dashboard=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,title:document.title,links:[...document.querySelectorAll('a')].map(a=>a.getAttribute('href'))}));
  await page.screenshot({path:path.join(root,'dashboard-mobile.png'),fullPage:true});
  const result={durations,seek,exclusive,mobile,mediaErrors,dashboard,errors};
  if(errors.length||!exclusive||mobile.scrollWidth>390||dashboard.scrollWidth>390||mediaErrors.some(m=>m.error))throw new Error('browser verification failed: '+JSON.stringify(result));
  fs.writeFileSync(path.join(root,'browser-verification.json'),JSON.stringify(result,null,2));
  for(const href of dashboard.links){if(!href.startsWith('#')&&!/^https?:/.test(href)&&!fs.existsSync(path.resolve(root,'../..',decodeURIComponent(href))))throw new Error('broken dashboard link: '+href)}
  console.log('BROWSER_VERIFIED',JSON.stringify({...result,dashboard:{...dashboard,links:dashboard.links.length}}));
 }finally{if(browser)await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
