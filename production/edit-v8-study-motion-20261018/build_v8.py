"""Add the supplied study motion clips while copying the complete v7 voice track."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
V7=ROOT.parent/'edit-v7-realvoice-20261017'
PROJECT=ROOT.parent.parent
SOURCE=V7/'善假于物_真人口播合成试听_v7_1080P.mp4'
MOVIE=ROOT/'善假于物_真人口播_v8_书写与翻页动态_1080P.mp4'
PATCHES=[
    dict(id='read-first',start=21.56,end=24.72,clip=6,chapter=2),
    dict(id='write-learning',start=34.12,end=37.12,clip=5,chapter=2),
    dict(id='write-notes',start=108.56,end=111.96,clip=5,chapter=5),
    dict(id='read-again',start=119.44,end=124.96,clip=6,chapter=6),
]

def ff(args):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

def encode(args,out,frames):
    ff([*args,'-an','-frames:v',frames,'-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-r','25','-video_track_timescale','12800',out])

def part(p):
    duration=round(p['end']-p['start'],2)
    out=ROOT/(p['id']+'.mp4')
    if 'clip' not in p:
        encode(['-ss',p['start'],'-i',SOURCE],out,round(duration*25))
    else:
        # End guard frames keep the output duration exact after frame-rate conversion.
        usable=min(duration,4.84)
        vf=f'trim=duration={usable},setpts={duration/usable:.10f}*(PTS-STARTPTS),fps=25,scale=1920:1080,setsar=1,tpad=stop_mode=clone:stop_duration=0.2'
        # Reuse the existing corner mask under the prior project instruction.
        mask=ROOT.parent/'edit-v6-20261017/masks/top-left.pgm'
        vf+=f",removelogo=filename={mask}:enable='gte(t,{3.2*duration/usable:.6f})'"
        graph=f'[0:v]{vf}[picture];[picture][1:v]overlay=0:880:shortest=1[v]'
        encode(['-filter_complex_threads','1','-i',ROOT/f'source-{p["clip"]}.mp4','-loop','1','-framerate','25','-i',V7/f'chapter-{p["chapter"]}.png','-filter_complex',graph,'-map','[v]'],out,round(duration*25))
    print('READY',p['id'],duration,flush=True)
    return out

def main():
    ledger=[]
    for n in [5,6]:
        original=PROJECT/'素材入库/新增动态_20261018'/f'分析项目文档作用 ({n}).mp4'
        target=ROOT/f'source-{n}.mp4';shutil.copy2(original,target)
        ledger.append(dict(file=target.name,original=str(original),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    parts=[];at=0
    for p in PATCHES:
        if p['start']>at:parts.append(dict(id=f'base-{len(parts)}',start=at,end=p['start']))
        parts.append(p);at=p['end']
    parts.append(dict(id='base-ending',start=at,end=141.0))
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs=list(pool.map(part,parts))
    (ROOT/'concat.txt').write_text(''.join("file '"+p.name+"'\n" for p in outputs))
    ff(['-f','concat','-safe','0','-i',ROOT/'concat.txt','-i',SOURCE,'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',MOVIE])
    shutil.copy2(V7/'voice-placement.json',ROOT/'voice-placement.json')
    (ROOT/'patch-plan.json').write_text(json.dumps(dict(sources=ledger,patches=PATCHES,audio='copy complete v7 AAC track; source clip audio excluded',duration=141.0),ensure_ascii=False,indent=2))
    page=(V7/'index.html').read_text().replace(SOURCE.name,MOVIE.name)
    page=page.replace('真人口播合成试听','真人口播 · 书写与翻页动态 v8')
    page=page.replace('原 AI 配音已替换','新增书写与翻页动态 · 真人配音沿用 v7')
    page=page.replace('完整 v6 保留。','本轮新增的书写、翻页取自用户提供的两段 720P 视频，放大至 1080P；原 v6、v7 保留。')
    page=page.replace('下载真人口播版 MP4','下载 v8 MP4')
    page=page.replace('</nav>','<button onclick="document.getElementById(\'film\').currentTime=21.56">看翻页</button><button onclick="document.getElementById(\'film\').currentTime=108.56">看书写</button></nav>')
    (ROOT/'index.html').write_text(page,encoding='utf-8')
    print('DONE',MOVIE,flush=True)

if __name__=='__main__':main()
