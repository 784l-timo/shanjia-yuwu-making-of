"""Assemble a reversible chapter-level audition with the six original recordings."""
from pathlib import Path
import concurrent.futures
import json
import math
import subprocess

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
BASE = ROOT.parent / 'edit-v6-20261017'
SOURCE = BASE / '善假于物_配音预演_v6_开场三镜动态.mp4'
AUDIO = PROJECT / '素材入库/阡陌口播_原始录音'
MOVIE = ROOT / '善假于物_真人口播合成试听_v7_1080P.mp4'
TITLES = ['答案与理解', '学习使人改变', '从思考到看见', '舟楫渡河', '积累与判断', '回到当下']
RANGES = [[(3,19.56)],[(19.56,49.16)],[(49.16,85.6)],[(85.6,115.76)],[(115.76,147.48)],[(147.48,153.88),(167.8,174.12),(203.8,212.64)]]
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'

def run(args):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

def encode(args,out):
    run([*args,'-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p','-r','25','-c:a','aac','-b:a','192k','-ar','48000','-ac','1','-movflags','+faststart',out])

def chapter(item):
    i,row=item
    duration=math.ceil((row['duration']+.6)*25)/25
    spans=RANGES[i]
    inputs=[]
    for a,b in spans: inputs+=['-ss',a,'-t',round(b-a,4),'-i',SOURCE]
    inputs+=['-i',AUDIO/row['file'],'-loop','1','-framerate','25','-i',ROOT/f'chapter-{i+1}.png']
    graph=[]
    for k in range(len(spans)): graph.append(f'[{k}:v]setpts=PTS-STARTPTS[v{k}]')
    if len(spans)>1:
        graph.append(''.join(f'[v{k}]' for k in range(len(spans)))+f'concat=n={len(spans)}:v=1:a=0[joined]')
        label='joined'
    else: label='v0'
    factor=duration/sum(b-a for a,b in spans)
    text=ROOT/f'chapter-{i+1}.txt'
    text.write_text(TITLES[i],encoding='utf-8')
    graph.append(f'[{label}]setpts={factor:.10f}*PTS,fps=25,tpad=stop_mode=clone:stop_duration=1,trim=duration={duration}[picture]')
    graph.append(f'[picture][{len(spans)+1}:v]overlay=0:880:shortest=1[v]')
    graph.append(f'[{len(spans)}:a]aresample=48000,aformat=channel_layouts=mono,adelay=280,apad,atrim=duration={duration},asetpts=PTS-STARTPTS[a]')
    out=ROOT/f'chapter-{i+1}.mp4'
    encode([*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map','[v]','-map','[a]','-t',duration],out)
    print('CHAPTER_READY',i+1,duration,flush=True)
    return dict(chapter=i+1,title=TITLES[i],recording=row['file'],duration=duration,source_ranges=spans,voice_offset=.28,file=out.name)

def main():
    rows=json.loads((AUDIO/'录音入库清单.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        plan=list(pool.map(chapter,enumerate(rows)))
    for name,start in [('intro',0),('ending',212.64)]:
        encode(['-ss',start,'-t',3,'-i',SOURCE,'-f','lavfi','-i','anullsrc=r=48000:cl=mono','-map','0:v:0','-map','1:a:0','-t',3],ROOT/f'{name}.mp4')
    sequence=['intro.mp4']+[p['file'] for p in plan]+['ending.mp4']
    (ROOT/'concat.txt').write_text(''.join("file '"+name+"'\n" for name in sequence))
    run(['-f','concat','-safe','0','-i',ROOT/'concat.txt','-c','copy','-movflags','+faststart',MOVIE])
    at=3
    for p in plan:
        p['start']=at
        at+=p['duration']
        p['end']=at
    (ROOT/'voice-placement.json').write_text(json.dumps(dict(mode='chapter-level audition; transcript and order not yet confirmed',source=str(SOURCE),chapters=plan,duration=at+3),ensure_ascii=False,indent=2))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>善假于物 · 真人口播合成试听</title><style>body{margin:0;background:#102021;color:#f5f0e5;font:16px/1.7 system-ui}main{max-width:1100px;margin:auto;padding:30px 20px}video{width:100%;background:#000}p{color:#b8c8c3}a{color:#e4bc77}button{background:#27423d;color:#f5f0e5;border:1px solid #61776d;padding:10px;margin:5px;border-radius:7px;cursor:pointer}</style><main><h1>善假于物 · 真人口播合成试听</h1><p>1080P · 六段原声 · 保持原录音语速 · 原 AI 配音已替换</p><video id="film" controls preload="metadata" src="'''+MOVIE.name+'''"></video><nav>'''+''.join(f'<button onclick="document.getElementById(\'film\').currentTime={p["start"]}">{p["title"]}</button>' for p in plan)+'''</nav><p>这是章节级合成试听。六段按录音编号暂配对应章节，画面按录音长度重排；录音内容及章节对应仍待核对，逐句字幕尚未完成。旧字幕暂以章节栏遮盖，避免与真人录音不符。片尾加长画面已节选，完整 v6 保留。</p><p><a download href="'''+MOVIE.name+'''">下载真人口播版 MP4</a> · <a href="../edit-v6-20261017/index.html">查看原 v6</a></p></main></html>'''
    (ROOT/'index.html').write_text(page,encoding='utf-8')
    print('DONE',str(MOVIE),at+3,flush=True)

if __name__=='__main__': main()
