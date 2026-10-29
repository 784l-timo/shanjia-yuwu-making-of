/* Three static 3-second ending studies; v2 full film remains the reference cut. */
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const {spawnSync}=require('child_process');
const {chromium}=require('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const ROOT=__dirname;
const PROJECT=path.resolve(ROOT,'../..');
const V2=path.resolve(ROOT,'../edit-v2-20261016');
const SOURCE=path.join(V2,'善假于物_配音预演_v2_学习细节与片头.mp4');
const OUT=path.join(ROOT,'assets');fs.mkdirSync(OUT,{recursive:true});
const options=[
 {id:'A',title:'留在书桌',recommend:true,source:path.join(PROJECT,'全片预演_HyperFrames/assets/desk-return.jpg'),headline:'学不可以已',subtitle:'田阡陌作品',reason:'延续最后的书桌画面，让学习行动成为影片的落点。',note:'推荐 · 衔接最自然',file:'A_留在书桌'},
 {id:'B',title:'舟楫远行',source:path.join(PROJECT,'全片预演_HyperFrames/assets/river-wide.png'),headline:'善假于物',subtitle:'借今天的舟楫，去抵达昨天还到不了的地方。',reason:'回到江河与小舟，让最后一句在远景中留下余韵。',note:'意象收束 · 更开阔',file:'B_舟楫远行'},
 {id:'C',title:'呼应片头',source:path.join(V2,'assets/片头海报_善假于物.png'),reason:'重现已经制作的片头海报，首尾信息与视觉完整对应。',note:'首尾呼应 · 信息较多',file:'C_呼应片头'}
];
const dataURI=(file,mime)=>`data:${mime};base64,${fs.readFileSync(file).toString('base64')}`;
const run=(cmd,args)=>{const r=spawnSync(cmd,args.map(String),{cwd:ROOT,encoding:'utf8',maxBuffer:5*1024*1024});if(r.status!==0)throw new Error((r.stderr||r.stdout).slice(-3500));return r.stdout;};
const ff=args=>run('ffmpeg',['-hide_banner','-loglevel','error','-y',...args]);
const probe=file=>JSON.parse(run('ffprobe',['-v','error','-show_entries','format=duration,size:stream=codec_type,width,height,avg_frame_rate','-of','json',file]));

function frame(o){
 const bg=dataURI(o.source,o.source.endsWith('.png')?'image/png':'image/jpeg');
 return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${o.id} ${o.title}</title><style>
 *{box-sizing:border-box}html,body{width:1920px;height:1080px;margin:0;overflow:hidden;background:#173334}img{width:1920px;height:1080px;object-fit:cover;position:absolute;inset:0}.copy{position:absolute;font-family:'Songti SC',serif}.copy.a{left:1080px;top:190px;color:#f9eed9;text-shadow:0 2px 7px #142c31}.eyebrow{font:28px 'PingFang SC',sans-serif;letter-spacing:7px;margin-bottom:20px}.copy.a h1{font-family:'Kaiti SC','Songti SC',serif;font-size:112px;font-weight:500;letter-spacing:10px;margin:0;line-height:1.5}.byline{font:30px 'PingFang SC',sans-serif;letter-spacing:5px;margin-top:28px}.copy.b{left:260px;right:260px;top:160px;text-align:center;color:#183d40;text-shadow:0 1px 1px #f2f4eb}.copy.b h1{font-family:'Kaiti SC','Songti SC',serif;font-size:152px;font-weight:500;letter-spacing:24px;margin:0 0 38px}.copy.b p{font-size:42px;margin:0;line-height:1.7}.copy.b .byline{font-size:30px;margin-top:35px}
 </style></head><body><img alt="${o.title}片尾画面" src="${bg}">${o.id==='A'?`<div class="copy a"><div class="eyebrow">善假于物</div><h1>${o.headline}</h1><div class="byline">${o.subtitle}</div></div>`:o.id==='B'?`<div class="copy b"><h1>${o.headline}</h1><p>${o.subtitle}</p><div class="byline">田阡陌作品</div></div>`:''}</body></html>`;
}

function comparison(){
 const frames=options.map(o=>({id:o.id,title:o.title,reason:o.reason,note:o.note,recommend:!!o.recommend,image:dataURI(path.join(OUT,o.file+'.png'),'image/png'),video:dataURI(path.join(ROOT,o.file+'_最后18秒.mp4'),'video/mp4')}));
 const json=JSON.stringify(frames).replaceAll('</','<\\/');
 const cards=frames.map(o=>`<article><img src="${o.image}" alt="${o.title}片尾画面"><div class="card-copy"><div class="label">${o.id} / ${o.note}</div><h2>${o.title}</h2><p>${o.reason}</p><button data-option="${o.id}">查看 ${o.id} 方案</button></div></article>`).join('');
 return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>善假于物 · 3 秒片尾方案对比</title><style>
 :root{color-scheme:dark;--bg:#102425;--panel:#1b3434;--ink:#f4ead7;--muted:#acbbb0;--gold:#e1b773}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 'PingFang SC',system-ui,sans-serif}main{max-width:1240px;padding:42px 28px 65px;margin:auto}.eyebrow,.label{font-size:12px;letter-spacing:2px;color:var(--gold)}h1{font:44px 'Songti SC',serif;letter-spacing:3px;margin:12px 0}header>p{color:var(--muted);max-width:900px;margin:0 0 22px}.player{overflow:hidden;background:#09191a;border:1px solid #52675c;border-radius:14px}video{width:100%;aspect-ratio:16/9;display:block;object-fit:contain}.controls{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:17px 20px;flex-wrap:wrap}.controls strong{font-size:19px}.controls small{display:block;color:var(--muted)}button,a{font:inherit}button{border:1px solid #667f70;background:#294439;color:var(--ink);border-radius:7px;cursor:pointer;padding:8px 15px}button:hover,button:focus-visible{border-color:var(--gold)}button.primary{background:var(--gold);color:#192e28;border-color:var(--gold);font-weight:600}.switch{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 30px}.switch button[aria-pressed=true]{background:var(--gold);color:#152b25;border-color:var(--gold)}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}article{border:1px solid #476152;border-radius:12px;overflow:hidden;background:var(--panel)}article img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}.card-copy{padding:20px}h2{font:26px 'Songti SC',serif;margin:6px 0}article p{font-size:14px;color:var(--muted);min-height:52px;margin:8px 0 15px}.recommendation{padding:22px 25px;margin:26px 0 0;background:#213c34;border:1px solid #596f55;border-radius:12px}.recommendation b{color:var(--gold)}.recommendation p{margin:6px 0 0}.note{font-size:13px;color:var(--muted);margin-top:22px}a{color:var(--gold)}.download{display:flex;gap:18px;flex-wrap:wrap;margin-top:18px;font-size:14px}@media(max-width:740px){main{padding:26px 14px 45px}h1{font-size:32px}.cards{grid-template-columns:1fr}.controls{padding:13px}.card-copy{padding:17px}article p{min-height:0}.controls strong{font-size:17px}}
 </style></head><body><main><header><div class="eyebrow">善假于物 / 片尾设计讨论 / 2026.10.16</div><h1>最后 3 秒，停在哪里？</h1><p>三版共用相同的最后 15 秒，只替换新增的 3 秒。点击方案后可连贯观看，也可直接比较新增尾帧。</p></header><div class="player"><video id="player" controls preload="metadata" poster="${frames[0].image}" src="${frames[0].video}"></video><div class="controls"><div><strong id="currentTitle">A · 留在书桌</strong><small id="modeText">18 秒上下文预览 · 新增片尾从 00:15 开始</small></div><div><button class="primary" id="playAll">连看最后 18 秒</button> <button id="playTail">只看新增 3 秒</button></div></div></div><nav class="switch" aria-label="选择片尾方案">${frames.map(o=>`<button data-option="${o.id}" aria-pressed="${o.id==='A'}">${o.id} · ${o.title}${o.recommend?'（推荐）':''}</button>`).join('')}</nav><div class="cards">${cards}</div><div class="recommendation"><b>推荐 A · 留在书桌</b><p>影片已经借舟楫完成了视觉高潮。最后留在读书、动笔的行动中，更贴合“把工具的帮助变成自己的本领”；“学不可以已”也呼应了前文。</p></div><p class="note">当前是片尾讨论样片。三种方案均为 3 秒静帧，没有新增旁白或配乐；C 直接复用片头海报。完整版仍保留原来的书桌预留段，尚未替换为其中任何一个方案。配音沿用 AI 试听人声。</p><div class="download"><a id="download" download="A_留在书桌_最后18秒.mp4" href="${frames[0].video}">下载当前 18 秒样片</a><a href="../edit-v2-20261016/index.html">返回 v2 完整预览</a></div></main><script>
 const variants=${json},player=document.getElementById('player');let selected='A',tailOnly=false;
 const seekAndPlay=t=>{if(player.readyState>=1){player.currentTime=t;player.play().catch(()=>{})}else player.addEventListener('loadedmetadata',()=>{player.currentTime=t;player.play().catch(()=>{})},{once:true})};
 function choose(id){selected=id;const o=variants.find(x=>x.id===id);player.pause();player.src=o.video;player.poster=o.image;player.load();document.getElementById('currentTitle').textContent=id+' · '+o.title;document.querySelectorAll('nav button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.option===id)));const d=document.getElementById('download');d.href=o.video;d.download=id+'_'+o.title+'_最后18秒.mp4';seekAndPlay(tailOnly?15:0)}
 document.querySelectorAll('[data-option]').forEach(b=>b.onclick=()=>choose(b.dataset.option));document.getElementById('playAll').onclick=()=>{tailOnly=false;seekAndPlay(0)};document.getElementById('playTail').onclick=()=>{tailOnly=true;seekAndPlay(15)};
 </script></body></html>`;
}

(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true});
  const framePage=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  const layout=[];
  for(const o of options){
   const file=path.join(OUT,o.file+'.html');fs.writeFileSync(file,frame(o));
   await framePage.goto(pathToFileURL(file).href);await framePage.evaluate(()=>document.fonts.ready);
   const fits=await framePage.evaluate(()=>[...document.querySelectorAll('.copy')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.top>=0&&r.right<=1920&&r.bottom<=1080}));
   if(!fits)throw new Error(o.id+' copy out of frame');
   await framePage.screenshot({path:path.join(OUT,o.file+'.png')});layout.push({id:o.id,copy_in_frame:fits});console.log('FRAME_READY',o.id);
  }
  ff(['-ss',197.64,'-i',SOURCE,'-t',15,'-map','0:v:0','-map','0:a:0','-c:v','libx264','-threads',4,'-preset','veryfast','-crf',19,'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','context-15s.mp4']);
  const videos=[];
  for(const o of options){
   const file=path.join(ROOT,o.file+'_最后18秒.mp4');
   ff(['-filter_complex_threads',1,'-i','context-15s.mp4','-loop',1,'-framerate',25,'-i',path.join(OUT,o.file+'.png'),'-filter_complex','[0:v]setpts=PTS-STARTPTS[v0];[1:v]scale=1920:1080,setsar=1,trim=duration=3,setpts=PTS-STARTPTS[v1];[v0][v1]concat=n=2:v=1:a=0[v]','-map','[v]','-map','0:a:0','-af','apad','-t',18,'-r',25,'-c:v','libx264','-threads',4,'-preset','veryfast','-crf',19,'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',file]);
   ff(['-i',file,'-f','null','-']);const info=probe(file);if(Math.abs(Number(info.format.duration)-18)>.01)throw new Error(o.id+' duration mismatch');
   videos.push({id:o.id,file:path.basename(file),probe:info,full_decode:'passed'});console.log('VIDEO_READY',o.id);
  }
  fs.writeFileSync(path.join(ROOT,'index.html'),comparison());
  const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(ROOT,'index.html')).href,{timeout:60000});await page.waitForFunction(()=>Number.isFinite(document.getElementById('player').duration));
  await page.screenshot({path:path.join(ROOT,'comparison-desktop.png'),fullPage:true});
  const playback=[];
  for(const o of options){
   await page.locator('nav button[data-option="'+o.id+'"]').click();await page.waitForFunction(()=>{const m=document.getElementById('player');return m.readyState>=2&&!m.paused&&Number.isFinite(m.duration)});
   await page.getByRole('button',{name:'只看新增 3 秒'}).click();await page.waitForFunction(()=>document.getElementById('player').currentTime>=15);
   playback.push(await page.evaluate(()=>({title:document.getElementById('currentTitle').textContent,duration:document.getElementById('player').duration,time:document.getElementById('player').currentTime,error:document.getElementById('player').error?.message||null})));await page.locator('#player').evaluate(m=>m.pause());
  }
  await page.setViewportSize({width:390,height:844});const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));await page.screenshot({path:path.join(ROOT,'comparison-mobile.png'),fullPage:true});
  if(errors.length||mobile.scrollWidth>390||playback.some(p=>p.error))throw new Error('Comparison page verification failed');
  fs.writeFileSync(path.join(ROOT,'verification.json'),JSON.stringify({layout,videos,playback,mobile,errors,full_film_modified:false,context_source:'v2',context_start:197.64,context_duration:15,tail_duration:3},null,2));
  console.log('VERIFIED',JSON.stringify({playback,mobile,errors}));
 }finally{if(browser)await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
