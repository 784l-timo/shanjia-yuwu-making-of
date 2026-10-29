"""Integrate three opening motion clips without changing narration or later edit decisions."""
from pathlib import Path
import base64
import hashlib
import importlib.util
import json
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parent
V5=ROOT.parent/'edit-v5-20261017'
SOURCE=V5/'善假于物_配音预演_v5_画面去字.mp4'
MOVIE=ROOT/'善假于物_配音预演_v6_开场三镜动态.mp4'
PATCHES=[
    dict(id='desk-motion',start=3.0,end=9.64,source='sources/01_夜间书桌.mp4',usable=4.84),
    dict(id='question-motion',start=9.64,end=13.28,source='sources/02_屏幕提问.mp4',usable=3.64),
    dict(id='pause-motion',start=13.28,end=19.56,source='sources/03_停笔凝视.mp4',usable=4.84),
]
spec=importlib.util.spec_from_file_location('existing_video_assembly',ROOT.parent/'edit-v4-20261017/build_v4.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.ROOT=ROOT;base.SOURCE=SOURCE;base.MOVIE=MOVIE;base.PATCHES=PATCHES
ff=base.ff;save=base.save;run=base.run


def prepare():
    for name in ['sources','clips','captions','assets/question-overlay','audit/ocr-opening']:
        (ROOT/name).mkdir(parents=True,exist_ok=True)
    ledger=[]
    for number,p in zip([2,3,4],PATCHES):
        original=Path('/path/to/user/Downloads')/f'分析项目文档作用 ({number}).mp4'
        target=ROOT/p['source'];shutil.copy2(original,target)
        ledger.append(dict(original=str(original),local=p['source'],sha256=base.sha(target)))
    shutil.copytree(V5/'assets',ROOT/'assets',dirs_exist_ok=True)
    shutil.copytree(V5/'masks',ROOT/'masks',dirs_exist_ok=True)
    for name in ['captions.srt','captions.ass','caption-timing.json','timeline.json','narration.txt',
                 'narration.mp3','ending-preview.mp3','script-source.json','script-plan.json']:
        shutil.copy2(V5/name,ROOT/name)
    rows=[]
    for line in (ROOT/'captions.ass').read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('Dialogue:'):continue
        fields=line.split(',',9);start,end=base.seconds(fields[1]),base.seconds(fields[2])
        if start<19.56 and end>3:
            rows.append(dict(id=len(rows),start=start,end=end,style=fields[3],text=re.sub(r'\{[^}]*\}','',fields[9]),file=f'captions/{len(rows):02d}.png'))
    save('caption-overlays.json',rows);save('patch-plan.json',PATCHES)
    old=json.loads((V5/'shot-plan.json').read_text())
    shots=[old[0]]+[dict(p,asset=p['source'],frames=round((p['end']-p['start'])*25)) for p in PATCHES]+[s for s in old if s['start']>=19.56]
    assert all(abs(a['end']-b['start'])<.001 for a,b in zip(shots,shots[1:]))
    assert sum(s['frames'] for s in shots)==5391
    save('shot-plan.json',shots)
    save('provenance.json',dict(sources=ledger,base='../edit-v5-20261017/'+SOURCE.name,
        base_sha256=base.sha(SOURCE),screen='Existing editable learning UI on tracked display corners; answer appears progressively.',
        source_audio_mixed=False,corner_labels='Remove new corner labels under the prior user instruction.'))
    print('PREPARED',len(rows),'captions',flush=True)


def render_patch(p):
    duration=round(p['end']-p['start'],2);frames=round(duration*25);factor=duration/p['usable']
    clean=ROOT/f"clips/{p['id']}-clean.mp4";output=ROOT/f"clips/{p['id']}.mp4"
    vf=f'setpts={factor:.10f}*(PTS-STARTPTS),minterpolate=fps=25:mi_mode=mci:mc_mode=obmc:me_mode=bidir:vsbmc=1,scale=1920:1080,format=yuv420p,setsar=1'
    # The same corner label alternates after roughly four source seconds.
    # Keep the hair and desk pixels intact while that corner contains no label.
    vf+=f",removelogo=filename=masks/bottom-right.pgm:enable='lt(t,{min(duration,4.5*factor):.6f})'"
    if p['usable']>4.0:
        vf+=f",removelogo=filename=masks/top-left.pgm:enable='gte(t,{3.3*factor:.6f})'"
    base.encode(['-filter_threads',1,'-i',ROOT/p['source'],'-vf',vf,'-frames:v',frames],clean,16)
    inputs=['-i',clean];graph=[];video='[0:v]';offset=1
    if p['id']=='question-motion':
        inputs+=['-framerate',25,'-i',ROOT/'assets/question-overlay/%03d.png']
        graph.append('[0:v][1:v]overlay=0:0:shortest=1[screened]');video='[screened]';offset=2
    rows=[c for c in json.loads((ROOT/'caption-overlays.json').read_text()) if c['start']<p['end'] and c['end']>p['start']]
    for i,c in enumerate(rows):
        inputs+=['-loop',1,'-framerate',25,'-i',ROOT/c['file']]
        start,end=max(0,c['start']-p['start']),min(duration,c['end']-p['start'])
        fade='format=rgba'
        if c['start']>=p['start']:fade+=f',fade=t=in:st={start:.4f}:d=0.06:alpha=1'
        if c['end']<=p['end']:fade+=f',fade=t=out:st={max(start,end-.08):.4f}:d=0.08:alpha=1'
        graph.append(f'[{offset+i}:v]{fade}[c{i}]')
        previous=video if i==0 else f'[v{i-1}]'
        graph.append(f"{previous}[c{i}]overlay=0:880:enable='gte(t,{start:.4f})*lt(t,{end:.4f})':shortest=1[v{i}]")
    base.encode(['-filter_complex_threads',1,*inputs,'-filter_complex',';'.join(graph),'-map',f'[v{len(rows)-1}]','-frames:v',frames],output)
    print('PATCH_READY',p['id'],duration,flush=True)
    return output


def package():
    html=(V5/'index.html').read_text()
    uri='data:video/mp4;base64,'+base64.b64encode(MOVIE.read_bytes()).decode()
    html,count=re.subn(r'(<video\b[^>]*\bid="film"[^>]*\bsrc=")[^"]*(")',lambda m:m[1]+uri+m[2],html,count=1);assert count==1
    replacements={
        '画面去字预演 v5':'开场三镜动态预演 v6',
        '画面去字预演 · 2026.10.17':'开场三镜动态预演 · 2026.10.17',
        '已去除角落生成字样 · 1080P / 25fps':'书桌 · 提问 · 停笔动态接入 · 1080P / 25fps',
        SOURCE.name:MOVIE.name,
        'v5 · 画面角落去字 · 单文件离线预览页':'v6 · 开场三镜动态接入 · 单文件离线预览页',
        '<button id="water">看水凝成冰</button>':'<button id="opening">看开场新镜头</button> <button id="water">看水凝成冰</button>',
        "document.getElementById('water').onclick=()=>seek(28.68);":"document.getElementById('opening').onclick=()=>seek(3);document.getElementById('water').onclick=()=>seek(28.68);",
        '本轮去掉染布、结冰、登阶与远眺画面角落的“豆包 AI 生成”字样，局部补绘背景。':'本轮接入夜间书桌、屏幕提问和停笔凝视三段动态素材；屏幕保留可读的课文学习内容，并随画面贴合、逐步显现。新增角落字样沿上一轮要求处理，背景有局部修补痕迹。',
        '</footer>':'</footer><p class="note"><a href="开场三镜_局部预览_v6.mp4">单独查看前 21.56 秒</a> · <a href="../edit-v5-20261017/index.html">回看 v5</a></p>',
    }
    for old,new in replacements.items():
        assert old in html,old
        html=html.replace(old,new)
    (ROOT/'index.html').write_text(html)
    ff(['-i',MOVIE,'-t',21.56,'-c:v','libx264','-threads',2,'-preset','veryfast','-crf',18,'-c:a','aac','-b:a','192k','-movflags','+faststart',ROOT/'开场三镜_局部预览_v6.mp4'])
    for label,t in [('desk',7),('question-early',9.8),('question',11.7),('pause',16.5)]:
        ff(['-ss',t,'-i',MOVIE,'-frames:v',1,ROOT/f'audit/check-{label}.png'])
    ff(['-ss',3,'-i',MOVIE,'-t',16.56,'-filter_complex','fps=4,split[a][b];[a]crop=480:216:0:0[top];[b]crop=480:216:1440:864[bottom];[top][bottom]vstack','-q:v',2,ROOT/'audit/ocr-opening/frame-%04d.jpg'])
    print('PACKAGED',flush=True)


def verify():
    ff(['-i',MOVIE,'-f','null','-'])
    info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',MOVIE]))
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_frames']))==(1920,1080,'25/1',5391)
    assert abs(float(info['format']['duration'])-215.64)<.001
    assert base.audio_packets(SOURCE)==base.audio_packets(MOVIE)
    assert (ROOT/'captions.srt').read_bytes()==(V5/'captions.srt').read_bytes()
    data=re.search(r'<video\b[^>]*id="film"[^>]*src="data:video/mp4;base64,([^"]+)"',(ROOT/'index.html').read_text())[1]
    assert hashlib.sha256(base64.b64decode(data)).hexdigest()==base.sha(MOVIE)
    save('verification.json',dict(duration=215.64,size=MOVIE.stat().st_size,full_decode='passed',
        complete_audio_packets_and_timestamps_equal=True,subtitles_identical_to_v5=True,
        embedded_video_matches_mp4=True,opening_replaced=[3,19.56],screen_overlay_frames=91,
        patches=PATCHES,probe=info))
    print('VERIFIED',flush=True)


if __name__=='__main__':
    if '--prepare' in sys.argv:prepare()
    else:
        base.render_patch=render_patch
        base.render()
        fixed=ROOT/'clips/master-tagged.mp4'
        ff(['-i',MOVIE,'-map','0','-c','copy','-metadata','title=善假于物·开场三镜动态预演 v6',
            '-metadata','comment=夜间书桌、屏幕提问、停笔凝视动态接入；AI试听人声','-movflags','+faststart',fixed])
        fixed.replace(MOVIE)
        package();verify()
