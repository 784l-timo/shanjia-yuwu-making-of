"""Render the complete current narrative to actual recognized speech timestamps."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,html,hashlib
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
V6=ROOT.parent/'edit-v6-20261017'
V4=ROOT.parent/'edit-v4-20261017'
V8=ROOT.parent/'edit-v8-study-motion-20261018'
ASSETS=PROJECT/'全片预演_HyperFrames/assets'
SHOTS=json.loads((ROOT/'shot-plan.json').read_text())
CAPTIONS=json.loads((ROOT/'caption-timing.json').read_text())
SPEECH=json.loads((ROOT/'speech-plan.json').read_text())
META=json.loads((ROOT/'rhythm-meta.json').read_text())
MOVIE=ROOT/'善假于物_真人口播_v10_识别校订与节奏调整_1080P.mp4'

def ff(args):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

def probe(file):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(file)]))

def prepare():
    for folder in ['clips','captions','audit']:(ROOT/folder).mkdir(exist_ok=True)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Songti.ttc',48)
    for i,c in enumerate(CAPTIONS):
        im=Image.new('RGBA',(1920,200),(0,0,0,0));d=ImageDraw.Draw(im)
        d.text((960,88),c['text'],font=font,anchor='mm',fill='#f7f2e8',stroke_width=2,stroke_fill=(0,0,0,210))
        im.save(ROOT/'captions'/f'{i:03d}.png')
    # The existing tracked UI is combined with its clean picture before retiming.
    ff(['-filter_complex_threads',1,'-i',V6/'clips/question-motion-clean.mp4','-framerate',25,'-i',V6/'assets/question-overlay/%03d.png','-filter_complex','[0:v][1:v]overlay=0:0:shortest=1[v]','-map','[v]','-an','-frames:v',91,'-c:v','libx264','-threads',2,'-preset','veryfast','-crf',17,ROOT/'question-ui-clean.mp4'])

def locate(s):
    # Keep the two most recent supplied learning actions in use.
    if s['id'] in [5,17,33,41,45]:return V8/'source-6.mp4',True
    if s['id'] in [9,30,32,42,48]:return V8/'source-5.mp4',True
    if 'reuse' in s:return PROJECT/s['reuse'],False
    if s['id']=='question-motion':return ROOT/'question-ui-clean.mp4',False
    a=s['asset']
    candidates=[V6/a,V6/'assets'/a,V4/a,ASSETS/a]
    for p in candidates:
        if p.is_file():return p,s['id'] in [6,'water','ascent','summit']
    raise FileNotFoundError(a)

def render(s):
    frames=round((s['end']-s['start'])*25)
    if frames<=0:raise ValueError(s)
    duration=frames/25;source,repair=locate(s)
    video=source.suffix.lower() in ['.mp4','.mov']
    inputs=[];offset=0
    if video:
        m=probe(source);available=float(m['format']['duration'])-.10
        if s['id'] in [6,'water']:
            usable=available
        elif s['id']=='question-motion':usable=3.64
        else:usable=min(available,duration)
        factor=duration/usable
        inputs=['-i',source]
        vf=f'trim=duration={usable:.6f},setpts={factor:.10f}*(PTS-STARTPTS),fps=25,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,tpad=stop_mode=clone:stop_duration=0.2'
    else:
        inputs=['-loop','1','-framerate','25','-i',source]
        vf='scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=25'
    if repair:
        vf+=f',removelogo=filename={V6/"masks/bottom-right.pgm"},removelogo=filename={V6/"masks/top-left.pgm"}'
    graph=[f'[0:v]{vf}[base]'];label='base'
    cues=[(i,c) for i,c in enumerate(CAPTIONS) if c['start']<s['end'] and c['end']>s['start']]
    for k,(i,c) in enumerate(cues):
        inputs+=['-loop','1','-framerate','25','-i',ROOT/'captions'/f'{i:03d}.png']
        a=max(0,c['start']-s['start']);b=min(duration,c['end']-s['start'])
        graph.append(f"[{label}][{k+1}:v]overlay=0:880:shortest=1:enable='gte(t,{a:.8f})*lt(t,{b:.8f})'[o{k}]");label=f'o{k}'
    out=ROOT/'clips'/f'{s["id"]}.mp4'
    ff([*inputs,'-filter_complex_threads',1,'-filter_complex',';'.join(graph),'-map',f'[{label}]','-frames:v',frames,'-an','-c:v','libx264','-threads',2,'-preset','veryfast','-crf',18,'-pix_fmt','yuv420p','-r',25,'-video_track_timescale',12800,out])
    s['resolved_source']=str(source);s['frames']=frames
    print('SHOT',s['id'],round(duration,2),flush=True)
    return out

def package():
    nav=[]
    for ch in range(1,7):
        s=next(s for s in SPEECH if s['chapter']==ch)
        nav.append(f'<button onclick="seek({s["start"]})">{s["title"]}</button>')
    lines=[]
    for s in SPEECH:
        lines.append(f'<p class="line" data-start="{s["start"]}" data-end="{s["end"]}" onclick="seek({s["start"]})"><time>{int(s["start"])//60:02}:{int(s["start"])%60:02}</time> {html.escape(s["text"])}</p>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>善假于物 · 新录音与节奏调整 v10</title><style>body{margin:0;background:#102021;color:#f5f0e5;font:16px/1.8 system-ui}main{max-width:1150px;margin:auto;padding:24px}h1{font-size:30px}video,audio{width:100%}p{color:#bccbc5}button{background:#304b42;color:white;padding:10px;border:1px solid #6d8074;border-radius:6px;margin:4px;cursor:pointer}a{color:#e4bc77}.line{padding:9px 12px;border-left:2px solid transparent;cursor:pointer}.line.active{background:#243d34;border-color:#e4bc77}time{font-variant-numeric:tabular-nums;color:#d8b479;margin-right:10px}.note{font-size:14px;color:#b9c9c3}</style><main><h1>善假于物 · 新录音与节奏调整 v10</h1><p>整段真人录音 · 中文转写校订 · 1080P / 25fps · 无底条字幕</p><video id="film" controls preload="metadata" src="'''+MOVIE.name+'''"></video><nav>'''+''.join(nav)+'''</nav><p>保留原声语速，只调整句间静音。镜头按实际读到的句子重排，字幕按本次识别的字级时间生成；完整加长结尾已经恢复。复用书写、翻页、停笔、登阶与舟行素材，屏幕学习文字继续保留。</p><p><a download href="'''+MOVIE.name+'''">下载视频</a> · <a href="captions.srt" download>下载字幕</a> · <a href="真人录音校订与节奏稿.md">查看校订与朗读节奏稿</a> · <a href="asr-full.txt">机器原始识别</a></p><details open><summary>全文 · 点击一句定位</summary>'''+''.join(lines)+'''</details><p class="note">识别疑点：写到这里／学到这里、做到以前做不到的事情，以及末句“昨天”前的轻微疑似口误，已在校订稿标记。古文同音字按原句规范；原始识别和原录音均保留，未声称这些疑点已人工听辨确认。当前仍是审片版，纸面清晰改句和完整划桨转向尚需补齐。</p></main><script>const film=document.getElementById('film');function seek(t){film.currentTime=t;film.scrollIntoView({block:'center',behavior:'smooth'})}film.ontimeupdate=()=>document.querySelectorAll('.line').forEach(p=>p.classList.toggle('active',film.currentTime>=Number(p.dataset.start)&&film.currentTime<Number(p.dataset.end)));</script></html>'''
    (ROOT/'index.html').write_text(page)

def main():
    prepare()
    with ThreadPoolExecutor(max_workers=2) as pool:files=list(pool.map(render,SHOTS))
    (ROOT/'concat.txt').write_text(''.join("file '"+str(p)+"'\n" for p in files))
    ff(['-f','concat','-safe',0,'-i',ROOT/'concat.txt','-i',ROOT/'narration-rhythm.wav','-filter_complex',f'[1:a]adelay=3000,apad,atrim=duration={META["total"]}[a]','-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-ar',48000,'-ac',1,'-t',META['total'],'-movflags','+faststart',MOVIE])
    (ROOT/'resolved-shot-plan.json').write_text(json.dumps(SHOTS,ensure_ascii=False,indent=2))
    package()
    print('DONE',MOVIE,flush=True)

if __name__=='__main__':main()
