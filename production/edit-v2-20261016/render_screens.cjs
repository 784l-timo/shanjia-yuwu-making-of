/* Editable HTML learning interfaces, projected into the original laptop screens. */
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const ROOT = __dirname;
const ASSETS = path.resolve(ROOT, '../../全片预演_HyperFrames/assets');
const OUT = path.join(ROOT, 'assets');
fs.mkdirSync(OUT, { recursive: true });

function homography(corners) {
  const src = [[0,0],[1200,0],[1200,760],[0,760]], a=[];
  src.forEach(([x,y],i) => {
    const [u,v]=corners[i];
    a.push([x,y,1,0,0,0,-u*x,-u*y,u]);
    a.push([0,0,0,x,y,1,-v*x,-v*y,v]);
  });
  for (let i=0;i<8;i++) {
    let pivot=i;
    for(let j=i+1;j<8;j++) if(Math.abs(a[j][i])>Math.abs(a[pivot][i]))pivot=j;
    [a[i],a[pivot]]=[a[pivot],a[i]];
    const divisor=a[i][i]; a[i]=a[i].map(x=>x/divisor);
    for(let j=0;j<8;j++)if(i!==j){const f=a[j][i];a[j]=a[j].map((x,k)=>x-f*a[i][k]);}
  }
  const [a0,a1,a2,b0,b1,b2,c0,c1]=a.map(r=>r[8]);
  return `matrix3d(${[a0,b0,0,c0,a1,b1,0,c1,0,0,1,0,a2,b2,0,1].join(',')})`;
}

const variants = [
  {id:3,name:'01-提出问题',base:'screen-question.jpg',phase:'提出问题',title:'“善假于物”是什么意思？',tag:'原文 · 《劝学》',quote:'君子生非异也，善假于物也。',body:`<div class="answer"><b>词义拆解</b><p><mark>假</mark>：借助、利用。　<mark>物</mark>：外物。</p><p>善于借助外物，拓展自己的能力。</p></div>`,aside:'看懂了解释，<br>我能自己讲清楚吗？',steps:['对照原文','理解词义','自己复述'],active:1},
  {id:16,name:'02-换个角度',base:'screen-question.jpg',phase:'换个角度',title:'借助工具，怎样看得更远？',tag:'原文 · 登高博见',quote:'不如登高之博见也。',body:`<div class="answer"><b>联系上下文</b><p>登高：借助位置，扩大视野。</p><p>学习：借助外物，拓展认识。</p><div class="rule"></div><b>我的追问</b><p>找到资料之后，我怎样判断和理解？</p></div>`,aside:'读原文<br>比较解释<br>再说自己的理解',steps:['找资料','看上下文','换个角度'],active:2},
  {id:18,name:'03-比较解释',base:'screen-revision.jpg',phase:'比较解释',title:'同一句话，比较两种表达',tag:'原文 · 学不可以已',quote:'君子曰：学不可以已。',body:`<div class="comparison"><label>参考解释</label><p>学习不能停止，要持续积累。</p></div><div class="draft"><label>我试着复述</label><p>得到解释以后，还要接着思考、验证。</p></div>`,aside:'“已”是停止。<br>重点是持续学习，<br>再联系自己的行动。',steps:['读原句','比较解释','标出疑问'],active:1},
  {id:37,name:'04-整理问题',base:'screen-question.jpg',phase:'整理问题',title:'把得到的帮助，变成自己的本领',tag:'原文 · 善假于物',quote:'君子生非异也，善假于物也。',body:`<div class="answer"><b>我的学习清单</b><p>01　提出自己的问题</p><p>02　比较不同的解释</p><p>03　用自己的话表达，再试着验证</p></div>`,aside:'工具带来更多可能。<br>理解与尝试，<br>还要由我完成。',steps:['记录问题','比较资料','实践验证'],active:2},
  {id:38,name:'05-形成表达',base:'screen-revision.jpg',phase:'形成表达',title:'从参考解释，到自己的表达',tag:'我的阅读笔记 · 原创理解',quote:'学习让我发生变化。',body:`<div class="comparison"><label>第一稿</label><p><del>工具给我答案，我就学会了。</del></p></div><div class="draft"><label>修改后</label><p>借助工具，也要把原来不会的东西学会。</p></div><div class="saved">✓ 已保存到《劝学》阅读笔记</div>`,aside:'改掉“得到答案<br>就等于学会”。<br>再加上自己的行动。',steps:['检查理解','删改表达','保存笔记'],active:2}
];

function makeHTML(v) {
  const revision=v.base.includes('revision');
  const corners=revision ? [[548,178],[1000,201],[957,491],[480,429]] : [[603,226],[981,242],[938,491],[552,440]];
  const bg=fs.readFileSync(path.join(ASSETS,v.base)).toString('base64');
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${v.name} · 善假于物</title><style>
  *{box-sizing:border-box}html,body{margin:0;width:1280px;height:720px;overflow:hidden}body{position:relative;background:#172422}img{position:absolute;inset:0;width:1280px;height:720px}.screen{position:absolute;left:0;top:0;width:1200px;height:760px;transform-origin:0 0;transform:${homography(corners)};overflow:hidden;background:#f7f8f3;color:#233d3c;font-family:'PingFang SC','Hiragino Sans GB',sans-serif;-webkit-font-smoothing:antialiased}.header{height:93px;background:#e5eeea;border-bottom:2px solid #c9d9d1;display:flex;align-items:center;padding:0 38px;gap:22px}.logo{width:38px;height:38px;border-radius:10px;background:#315e56;color:#fff;font-size:27px;text-align:center;line-height:38px}.brand{font-size:35px;font-weight:650}.path{font-size:24px;color:#526a65;margin-left:auto}.context{padding:20px 38px 14px;color:#55716a;font-size:26px;letter-spacing:1px}.context em{font-style:normal;background:#e8ead8;padding:5px 13px;border-radius:7px;color:#4e6544;margin-left:20px}.layout{display:grid;grid-template-columns:810px 1fr;gap:25px;padding:0 32px}.main{padding:24px;background:#fff;border:2px solid #d8e1d9;border-radius:16px;height:554px}.main h1{margin:0 0 22px;font-size:40px;line-height:1.35;letter-spacing:-1px;font-weight:650}.tag{font-size:24px;color:#6a786b;letter-spacing:2px}.quote{font-family:'Songti SC',serif;font-size:37px;line-height:1.55;margin:6px 0 18px;padding-bottom:17px;border-bottom:2px solid #e2e8e0;color:#263c37}.answer{background:#eef4ef;padding:20px 22px;border-radius:12px;font-size:28px;line-height:1.55}.answer b{font-size:28px}.answer p{margin:10px 0}mark{background:#dbe7c7;color:#32523c;border-radius:5px;padding:1px 7px}.rule{height:1px;background:#c9d9ce;margin:14px 0}.comparison,.draft{padding:13px 20px;border-radius:10px;font-size:29px;line-height:1.5}.comparison{background:#f4f2ed;margin-bottom:13px;color:#5b625c}.draft{background:#eaf2e9;border-left:5px solid #67886e}.comparison label,.draft label{font-size:24px;font-weight:600}.comparison p,.draft p{margin:6px 0}.comparison del{text-decoration-color:#9d5c52;color:#8a6760}.saved{font-size:23px;color:#4c7454;margin-top:15px}.aside{padding-top:10px}.aside h2{font-size:29px;margin:8px 0 18px}.step{font-size:26px;padding:12px 13px;border-radius:9px;line-height:1.5;color:#687c71;margin-bottom:8px}.step.current{background:#dceade;color:#2a513d;font-weight:600}.note{border-top:2px solid #d8e2d7;margin-top:25px;padding-top:24px;font-size:28px;line-height:1.75;color:#465e52}.footer{position:absolute;bottom:15px;left:39px;font-size:21px;color:#75867c}.reflection{position:absolute;inset:0;pointer-events:none;background:linear-gradient(120deg,#fff1,transparent 55%,#fff1)}
  </style></head><body><img alt="少年在书桌前使用电脑学习" src="data:image/jpeg;base64,${bg}"><div class="screen"><div class="header"><div class="logo">学</div><div class="brand">课文研读</div><div class="path">原文　·　解释　·　笔记</div></div><div class="context">《劝学》 · 荀子 <em>${v.phase}</em></div><div class="layout"><div class="main"><h1>${v.title}</h1><div class="tag">${v.tag}</div><div class="quote">${v.quote}</div>${v.body}</div><div class="aside"><h2>学习步骤</h2>${v.steps.map((s,i)=>`<div class="step ${i===v.active?'current':''}">${String(i+1).padStart(2,'0')}　${s}</div>`).join('')}<div class="note">${v.aside}</div></div></div><div class="footer">普通高中语文 · 必修上册　/　学习界面示意</div><div class="reflection"></div></div></body></html>`;
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1.5});
  const report=[];
  for(const v of variants){
    const file=path.join(OUT,`screen-${v.id}.html`);
    const extra=v.id===16?'.answer{padding:15px 22px;font-size:27px;line-height:1.45}.answer p{margin:8px 0}.rule{margin:10px 0}':'';
    fs.writeFileSync(file,makeHTML(v).replace('</style>',extra+'</style>'));
    await page.goto(pathToFileURL(file).href); await page.evaluate(()=>document.fonts.ready);
    const overflow=await page.evaluate(()=>[...document.querySelectorAll('.main,.screen,.aside')].map(e=>({class:e.className,width:e.clientWidth,scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight})));
    await page.screenshot({path:path.join(OUT,`screen-${v.id}.png`)});
    report.push({shot:v.id,name:v.name,overflow});
    console.log('SCREEN',v.id,v.name);
  }
  fs.writeFileSync(path.join(ROOT,'screen-verification.json'),JSON.stringify(report,null,2));
  if(report.some(r=>r.overflow.some(e=>e.scrollWidth>e.width||e.scrollHeight>e.height)))throw new Error('Learning interface overflow');
  if(process.argv.includes('--build')){
    const {spawnSync}=require('child_process');
    const verification=path.join(ROOT,'verification.json');
    if(!fs.existsSync(verification)){
      const build=spawnSync('python3',[path.join(ROOT,'build_v2.py')],{stdio:'inherit'});
      if(build.status!==0)throw new Error('Video build failed');
    }
    const review=await browser.newPage({viewport:{width:1440,height:1100}});
    const errors=[];review.on('pageerror',e=>errors.push(e.message));
    await review.goto(pathToFileURL(path.join(ROOT,'index.html')).href,{waitUntil:'load',timeout:60000});
    await review.waitForFunction(()=>[...document.querySelectorAll('video,audio')].every(m=>Number.isFinite(m.duration)),{timeout:30000});
    const metadata=await review.evaluate(()=>[...document.querySelectorAll('video,audio')].map(m=>({id:m.id,duration:m.duration,error:m.error?.message||null})));
    await review.screenshot({path:path.join(ROOT,'preview-desktop.png')});
    await review.getByRole('button',{name:'重点听结尾'}).click();
    await review.waitForFunction(()=>{const v=document.getElementById('film');return !v.paused&&v.currentTime>=147.48&&v.currentTime<152.48});
    const ending=await review.evaluate(()=>({time:document.getElementById('film').currentTime,chapter:document.querySelector('.chapter.active b')?.textContent}));
    await review.locator('#film').evaluate(m=>m.pause());
    await review.locator('#fullAudio').evaluate(m=>m.play());
    const exclusive=await review.evaluate(()=>document.getElementById('film').paused&&document.getElementById('endingAudio').paused);
    await review.locator('#fullAudio').evaluate(m=>m.pause());
    await review.setViewportSize({width:390,height:844});
    const mobile=await review.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
    await review.screenshot({path:path.join(ROOT,'preview-mobile.png'),fullPage:true});
    const browserReport={metadata,ending,exclusive,mobile,errors};
    fs.writeFileSync(path.join(ROOT,'browser-verification.json'),JSON.stringify(browserReport,null,2));
    if(errors.length||!exclusive||mobile.scrollWidth>390||metadata.some(m=>m.error)||Math.abs(metadata[0].duration-215.64)>.01)throw new Error('Offline player verification failed');
    console.log('BROWSER_VERIFIED',JSON.stringify(browserReport));
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
