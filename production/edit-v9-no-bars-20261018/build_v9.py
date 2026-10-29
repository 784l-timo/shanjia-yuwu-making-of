"""Restore full-frame pictures and existing transparent captions before the chapter bars."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess

ROOT=Path(__file__).resolve().parent
V6=ROOT.parent/'edit-v6-20261017'
V7=ROOT.parent/'edit-v7-realvoice-20261017'
V8=ROOT.parent/'edit-v8-study-motion-20261018'
SOURCE=V6/'善假于物_配音预演_v6_开场三镜动态.mp4'
VOICE_SOURCE=V8/'善假于物_真人口播_v8_书写与翻页动态_1080P.mp4'
MOVIE=ROOT/'善假于物_真人口播_v9_无底条字幕版_1080P.mp4'
PLAN=json.loads((V7/'voice-placement.json').read_text())
PATCHES=json.loads((V8/'patch-plan.json').read_text())['patches']

def ff(args):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

def encode(args,out,frames):
    ff([*args,'-an','-frames:v',frames,'-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-r','25','-video_track_timescale','12800',out])

def chapter(ch):
    inputs=[];graph=[];spans=ch['source_ranges'];duration=ch['duration']
    for a,b in spans:inputs+=['-ss',a,'-t',round(b-a,4),'-i',SOURCE]
    for i in range(len(spans)):graph.append(f'[{i}:v]setpts=PTS-STARTPTS[v{i}]')
    if len(spans)>1:
        graph.append(''.join(f'[v{i}]' for i in range(len(spans)))+f'concat=n={len(spans)}:v=1:a=0[joined]');label='joined'
    else:label='v0'
    factor=duration/sum(b-a for a,b in spans)
    graph.append(f'[{label}]setpts={factor:.10f}*PTS,fps=25,tpad=stop_mode=clone:stop_duration=1,trim=duration={duration}[v]')
    out=ROOT/f'chapter-{ch["chapter"]}.mp4'
    encode([*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map','[v]'],out,round(duration*25))
    print('CHAPTER',ch['chapter'],flush=True)
    return out

def mapped_captions():
    source=json.loads((V6/'caption-timing.json').read_text());rows=[]
    for ch in PLAN['chapters']:
        factor=ch['duration']/sum(b-a for a,b in ch['source_ranges']);cursor=ch['start']
        for a,b in ch['source_ranges']:
            for cue in source:
                x,y=max(a,cue['start']),min(b,cue['end'])
                if y>x:rows.append(dict(start=cursor+(x-a)*factor,end=cursor+(y-a)*factor,text=cue['text'],style=cue['style']))
            cursor+=(b-a)*factor
    return rows

def patch(p):
    duration=round(p['end']-p['start'],2);usable=min(duration,4.84);factor=duration/usable
    inputs=['-i',V8/f'source-{p["clip"]}.mp4']
    vf=f'trim=duration={usable},setpts={factor:.10f}*(PTS-STARTPTS),fps=25,scale=1920:1080,setsar=1,tpad=stop_mode=clone:stop_duration=0.2'
    vf+=f",removelogo=filename={V6/'masks/bottom-right.pgm'}:enable='lt(t,{4.5*factor:.6f})'"
    vf+=f",removelogo=filename={V6/'masks/top-left.pgm'}:enable='gte(t,{3.2*factor:.6f})'"
    graph=[f'[0:v]{vf}[base]'];label='base'
    rows=[c for c in mapped_captions() if c['start']<p['end'] and c['end']>p['start']]
    for i,c in enumerate(rows):
        inputs+=['-loop','1','-framerate','25','-i',ROOT/'captions'/f'{p["id"]}-{i}.png']
        a=max(0,c['start']-p['start']);b=min(duration,c['end']-p['start'])
        graph.append(f"[{label}][{i+1}:v]overlay=0:880:shortest=1:enable='gte(t,{a:.8f})*lt(t,{b:.8f})'[o{i}]");label=f'o{i}'
    out=ROOT/f'{p["id"]}.mp4'
    encode([*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map',f'[{label}]'],out,round(duration*25))
    print('PATCH',p['id'],flush=True)
    return out

def prepare_captions():
    # Use the bundled Pillow runtime; original captions remain burned into v6 elsewhere.
    rows=[]
    for p in PATCHES:
        for i,c in enumerate(c for c in mapped_captions() if c['start']<p['end'] and c['end']>p['start']):
            rows.append(dict(file=f'{p["id"]}-{i}.png',**c))
    (ROOT/'caption-images.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    (ROOT/'captions').mkdir(exist_ok=True)
    script="""from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parent
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Songti.ttc',48)
for c in json.loads((root/'caption-images.json').read_text()):
 im=Image.new('RGBA',(1920,200),(0,0,0,0));draw=ImageDraw.Draw(im)
 draw.text((960,88),c['text'],font=font,anchor='mm',fill='#f7f2e8',stroke_width=2,stroke_fill=(0,0,0,210))
 im.save(root/'captions'/c['file'])
"""
    (ROOT/'render_caption_images.py').write_text(script)
    subprocess.run(['/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',str(ROOT/'render_caption_images.py')],check=True)

def main():
    prepare_captions()
    with ThreadPoolExecutor(max_workers=2) as pool:chapters=list(pool.map(chapter,PLAN['chapters']))
    basefiles=[V7/'intro.mp4',*chapters,V7/'ending.mp4']
    (ROOT/'base-concat.txt').write_text(''.join("file '"+str(p)+"'\n" for p in basefiles))
    base=ROOT/'full-frame-base.mp4'
    ff(['-f','concat','-safe','0','-i',ROOT/'base-concat.txt','-map','0:v:0','-c','copy',base])
    parts=[];at=0
    for p in PATCHES:
        if p['start']>at:parts.append(dict(id=f'keep-{len(parts)}',start=at,end=p['start']))
        parts.append(p);at=p['end']
    parts.append(dict(id='keep-ending',start=at,end=141.0))
    def render(p):
        if 'clip' in p:return patch(p)
        out=ROOT/f'{p["id"]}.mp4';encode(['-ss',p['start'],'-i',base],out,round((p['end']-p['start'])*25));return out
    with ThreadPoolExecutor(max_workers=2) as pool:files=list(pool.map(render,parts))
    (ROOT/'concat.txt').write_text(''.join("file '"+str(p)+"'\n" for p in files))
    ff(['-f','concat','-safe','0','-i',ROOT/'concat.txt','-i',VOICE_SOURCE,'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',MOVIE])
    captions=mapped_captions()
    (ROOT/'caption-timing.json').write_text(json.dumps(captions,ensure_ascii=False,indent=2))
    page=(V8/'index.html').read_text().replace(VOICE_SOURCE.name,MOVIE.name)
    page=page.replace('真人口播 · 书写与翻页动态 v8','真人口播 · 无底条字幕版 v9').replace('下载 v8 MP4','下载 v9 MP4')
    page=page.replace('新增书写与翻页动态 · 真人配音沿用 v7','去除全部底条 · 保留透明底字幕 · 真人配音')
    a=page.index('<p>这是章节级合成试听。');b=page.index('</p>',a)+4
    page=page[:a]+'<p>已移除底部墨绿色条和章节文字，恢复完整画面。保留原版字幕，白字加细描边、无色块背景；新增书写与翻页镜头仍保留。真人配音与总时长沿用 v8。字幕沿用先前文案和时间映射，与真人口播的逐句对应仍待校对。</p>'+page[b:]
    page=page.replace('../edit-v8-study-motion-20261018/index.html','../edit-v8-study-motion-20261018/index.html')
    (ROOT/'index.html').write_text(page)
    print('DONE',MOVIE,flush=True)

if __name__=='__main__':main()
