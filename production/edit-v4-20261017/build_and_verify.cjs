const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const {spawnSync}=require('child_process');
const {chromium}=require('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=__dirname;
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true});
  if(!process.argv.includes('--verify-only')){
   const page=await browser.newPage({viewport:{width:1920,height:200},deviceScaleFactor:1});
   const rows=JSON.parse(fs.readFileSync(path.join(root,'caption-overlays.json')));
   const layouts=[];
   await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{width:1920px;height:200px;margin:0;overflow:hidden;background:transparent}
    #text{position:absolute;bottom:74px;left:90px;right:90px;text-align:center;white-space:pre-wrap;line-height:1;letter-spacing:1px;font-weight:400;-webkit-text-stroke:2.6px #232520;paint-order:stroke fill;text-shadow:1px 1px 1px #232520}
   </style></head><body><div id="text"></div></body></html>`);
   for(const row of rows){
    await page.evaluate(c=>{const e=document.getElementById('text');e.textContent=c.text;e.style.fontFamily=c.style==='Quote'?'"Songti SC",serif':'"Kaiti SC",serif';e.style.fontSize=c.style==='Quote'?'54px':'56px';e.style.color=c.style==='Quote'?'#f5e5cd':'#f7f3ea'},row);
    await page.evaluate(()=>document.fonts.ready);
    const layout=await page.locator('#text').evaluate(e=>({width:e.clientWidth,scrollWidth:e.scrollWidth,top:e.getBoundingClientRect().top,bottom:e.getBoundingClientRect().bottom}));
    if(layout.scrollWidth>layout.width||layout.top<0||layout.bottom>200)throw new Error('Caption does not fit '+row.id);
    await page.screenshot({path:path.join(root,row.file),omitBackground:true});layouts.push({id:row.id,text:row.text,...layout});
   }
   fs.writeFileSync(path.join(root,'captions/layout-verification.json'),JSON.stringify(layouts,null,2));
   await page.close();console.log('CAPTIONS_READY',rows.length);
   const rendered=spawnSync('python3',[path.join(root,'build_v4.py')],{stdio:'inherit',cwd:root});
   if(rendered.status!==0)throw new Error('Video build failed: '+rendered.status);
  }
  const page=await browser.newPage({viewport:{width:1440,height:1050}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href,{timeout:60000});
  await page.waitForFunction(()=>['film','fullAudio','endingAudio'].every(id=>Number.isFinite(document.getElementById(id).duration)));
  const durations=await page.evaluate(()=>Object.fromEntries(['film','fullAudio','endingAudio'].map(id=>[id,document.getElementById(id).duration])));
  if(Math.abs(durations.film-215.64)>.01)throw new Error('Wrong film duration');
  await page.screenshot({path:path.join(root,'preview-desktop.png'),fullPage:true});
  const seeks=[];
  for(const [id,target] of [['water',28.68],['ascent',55.24],['ending',147.48],['tail',212.64]]){
   const actual=await page.evaluate(async({id,target})=>{
    const m=document.getElementById('film');const ready=new Promise(resolve=>m.addEventListener('seeked',()=>{m.pause();resolve(m.currentTime)},{once:true}));
    document.getElementById(id).click();return ready;
   },{id,target});
   if(Math.abs(actual-target)>.1)throw new Error('Seek mismatch '+id+': '+actual);
   seeks.push({id,target,actual});
  }
  const exclusive=await page.evaluate(async()=>{
   const a=document.getElementById('film'),b=document.getElementById('fullAudio'),c=document.getElementById('endingAudio');
   await a.play();await b.play();const first=a.paused&&!b.paused;await c.play();const second=b.paused&&!c.paused;c.pause();return first&&second;
  });
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
  await page.screenshot({path:path.join(root,'preview-mobile.png'),fullPage:true});
  const mediaErrors=await page.evaluate(()=>[...document.querySelectorAll('video,audio')].map(m=>({id:m.id,error:m.error?.message||null})));
  await page.goto(pathToFileURL(path.join(root,'修订片段对比.html')).href,{timeout:60000});
  await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(m=>Number.isFinite(m.duration)));
  const comparison=await page.evaluate(async()=>{
   const media=[...document.querySelectorAll('video')],items=[];
   for(const m of media){
    await m.play();await new Promise(resolve=>setTimeout(resolve,650));
    items.push({id:m.id,duration:m.duration,time:m.currentTime,playing:!m.paused,othersPaused:media.every(o=>o===m||o.paused),error:m.error?.message||null});m.pause();
   }
   return {items,width:innerWidth,scrollWidth:document.documentElement.scrollWidth};
  });
  if(comparison.items.some((x,i)=>Math.abs(x.duration-[10.44,10.44,23.68][i])>.05||!x.playing||!x.othersPaused||x.time<.2||x.error)||comparison.scrollWidth>390)throw new Error('Comparison verification failed: '+JSON.stringify(comparison));
  await page.screenshot({path:path.join(root,'comparison-mobile.png'),fullPage:true});
  await page.goto(pathToFileURL(path.resolve(root,'../../17_项目总览看板.html')).href);
  const dashboard=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,latest:document.querySelector('header a')?.getAttribute('href')}));
  if(dashboard.scrollWidth>390||!dashboard.latest.includes('edit-v4-20261017'))throw new Error('Dashboard verification failed');
  const result={durations,seeks,exclusive,mobile,mediaErrors,comparison,dashboard,errors};
  if(!exclusive||mobile.scrollWidth>390||errors.length||mediaErrors.some(x=>x.error))throw new Error(JSON.stringify(result));
  fs.writeFileSync(path.join(root,'browser-verification.json'),JSON.stringify(result,null,2));
  console.log('BROWSER_VERIFIED',JSON.stringify(result));
 }finally{if(browser)await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
