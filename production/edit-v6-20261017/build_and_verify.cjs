const fs=require('fs'),path=require('path');
const {pathToFileURL}=require('url');
const {spawnSync}=require('child_process');
const {chromium}=require('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=__dirname;
function homography(corners){
 const src=[[0,0],[1200,0],[1200,760],[0,760]],a=[];
 src.forEach(([x,y],i)=>{const [u,v]=corners[i];a.push([x,y,1,0,0,0,-u*x,-u*y,u]);a.push([0,0,0,x,y,1,-v*x,-v*y,v])});
 for(let i=0;i<8;i++){let pivot=i;for(let j=i+1;j<8;j++)if(Math.abs(a[j][i])>Math.abs(a[pivot][i]))pivot=j;[a[i],a[pivot]]=[a[pivot],a[i]];const d=a[i][i];a[i]=a[i].map(x=>x/d);for(let j=0;j<8;j++)if(i!==j){const f=a[j][i];a[j]=a[j].map((x,k)=>x-f*a[i][k])}}
 const [a0,a1,a2,b0,b1,b2,c0,c1]=a.map(r=>r[8]);return `matrix3d(${[a0,b0,0,c0,a1,b1,0,c1,0,0,1,0,a2,b2,0,1].join(',')})`;
}
function execute(command,args){const r=spawnSync(command,args,{stdio:'inherit',cwd:root});if(r.status!==0)throw new Error(command+' exited '+r.status)}
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true});
  if(!process.argv.includes('--verify-only')){
   const screen=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1.5});
   let html=fs.readFileSync(path.join(root,'assets/screen-3.html'),'utf8').replace(/<img\b[^>]*>/g,'');
   html=html.replace('</style>','html,body{background:transparent!important}.screen{will-change:transform}.answer{will-change:opacity,transform}</style>');
   fs.writeFileSync(path.join(root,'assets/question-motion.html'),html);
   await screen.goto(pathToFileURL(path.join(root,'assets/question-motion.html')).href);await screen.evaluate(()=>document.fonts.ready);
   const title=await screen.locator('.main h1').textContent();
   const track=JSON.parse(fs.readFileSync(path.join(root,'screen-tracking.json'))).output_frames;
   for(const row of track){
    await screen.evaluate(({matrix,t,title})=>{
     const e=document.querySelector('.screen');e.style.transform=matrix;
     const h=document.querySelector('.main h1');h.textContent=title.slice(0,Math.min(title.length,Math.max(2,Math.floor((t+.12)/.055))));
     document.querySelector('.quote').style.opacity=String(Math.max(0,Math.min(1,(t-.2)/.35)));
     const alpha=Math.max(0,Math.min(1,(t-.65)/.65));const answer=document.querySelector('.answer');answer.style.opacity=String(alpha);answer.style.transform=`translateY(${12*(1-alpha)}px)`;
    },{matrix:homography(row.corners),t:row.time,title});
    await screen.screenshot({path:path.join(root,'assets/question-overlay',String(row.frame).padStart(3,'0')+'.png'),omitBackground:true});
   }
   const layout=await screen.evaluate(()=>[...document.querySelectorAll('.screen,.main,.aside')].map(e=>({class:e.className,width:e.clientWidth,scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight})));
   if(layout.some(e=>e.scrollWidth>e.width||e.scrollHeight>e.height))throw new Error('Screen UI overflow');
   fs.writeFileSync(path.join(root,'screen-layout-verification.json'),JSON.stringify({frames:track.length,layout},null,2));
   await screen.close();console.log('SCREEN_OVERLAYS_READY',track.length);
   const captions=await browser.newPage({viewport:{width:1920,height:200}});
   await captions.setContent('<html><head><meta charset="utf-8"><style>html,body{width:1920px;height:200px;margin:0;background:transparent;overflow:hidden}#text{position:absolute;left:90px;right:90px;bottom:74px;text-align:center;line-height:1;letter-spacing:1px;-webkit-text-stroke:2.6px #232520;paint-order:stroke fill;text-shadow:1px 1px 1px #232520;font:56px "Kaiti SC",serif;color:#f7f3ea}</style></head><body><div id="text"></div></body></html>');
   for(const row of JSON.parse(fs.readFileSync(path.join(root,'caption-overlays.json')))){
    await captions.locator('#text').evaluate((e,text)=>e.textContent=text,row.text);await captions.evaluate(()=>document.fonts.ready);
    await captions.screenshot({path:path.join(root,row.file),omitBackground:true});
   }
   await captions.close();console.log('CAPTIONS_READY');
   execute('python3',[path.join(root,'build_v6.py')]);
   execute('swift',['-module-cache-path','/private/tmp/shanjia-swift-modules',path.resolve(root,'../edit-v5-20261017/audit_watermarks.swift'),path.join(root,'audit/ocr-opening'),path.join(root,'audit/ocr-opening.json')]);
   const ocr=JSON.parse(fs.readFileSync(path.join(root,'audit/ocr-opening.json'))),hits=[];
   ocr.forEach(f=>f.texts.forEach(x=>{if(/生成|豆包|豆|ai/i.test(x.text.replaceAll(' ','')))hits.push({time:f.time+3,...x})}));
   fs.writeFileSync(path.join(root,'audit/ocr-summary.json'),JSON.stringify({sample_rate:4,frames:ocr.length,candidates:hits},null,2));
   if(hits.length)throw new Error('Corner lettering remains: '+JSON.stringify(hits));
  }
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href,{timeout:60000});
  await page.waitForFunction(()=>['film','fullAudio','endingAudio'].every(id=>Number.isFinite(document.getElementById(id).duration)));
  const durations=await page.evaluate(()=>Object.fromEntries(['film','fullAudio','endingAudio'].map(id=>[id,document.getElementById(id).duration])));
  if(Math.abs(durations.film-215.64)>.01)throw new Error('Wrong full duration');
  const opening=await page.evaluate(async()=>{const m=document.getElementById('film');const p=new Promise(resolve=>m.addEventListener('seeked',()=>{m.pause();resolve(m.currentTime)},{once:true}));document.getElementById('opening').click();return p});
  if(Math.abs(opening-3)>.1)throw new Error('Opening button');
  await page.locator('#film').evaluate(m=>{m.currentTime=11.7;return new Promise(resolve=>m.addEventListener('seeked',resolve,{once:true}))});
  await page.screenshot({path:path.join(root,'preview-desktop.png'),fullPage:true});
  const exclusive=await page.evaluate(async()=>{const a=document.getElementById('film'),b=document.getElementById('fullAudio');await a.play();await b.play();const ok=a.paused&&!b.paused;b.pause();return ok});
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
  await page.screenshot({path:path.join(root,'preview-mobile.png'),fullPage:true});
  const mediaErrors=await page.evaluate(()=>[...document.querySelectorAll('video,audio')].map(m=>({id:m.id,error:m.error?.message||null})));
  await page.goto(pathToFileURL(path.join(root,'开场三镜_局部预览_v6.mp4')).href);await page.waitForFunction(()=>{const m=document.querySelector('video');return m&&Number.isFinite(m.duration)});
  const localDuration=await page.locator('video').evaluate(async m=>{await m.play();return m.duration});
  if(Math.abs(localDuration-21.56)>.05||!exclusive||mobile.scrollWidth>390||errors.length||mediaErrors.some(m=>m.error))throw new Error('Browser verification failed');
  const result={durations,opening,exclusive,mobile,mediaErrors,localDuration,errors};
  fs.writeFileSync(path.join(root,'browser-verification.json'),JSON.stringify(result,null,2));console.log('BROWSER_VERIFIED',JSON.stringify(result));
 }finally{if(browser)await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
