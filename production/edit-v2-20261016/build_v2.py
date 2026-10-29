"""Local, offline revision of the imported voice preview. Original edit/ is read-only input."""
from pathlib import Path
import base64
import concurrent.futures
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'edit'
PROJECT = ROOT.parents[1]
ASSETS = PROJECT / '全片预演_HyperFrames/assets'
CLIPS = ROOT / 'clips'
CLIPS.mkdir(exist_ok=True)
FPS, INTRO, TAIL = 25, 3.0, 3.0
TOTAL = 215.64
MOVIE = ROOT / '善假于物_配音预演_v2_学习细节与片头.mp4'

def save(name, obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def ff(args):
    command = ['ffmpeg','-hide_banner','-loglevel','error','-y',*[str(x) for x in args]]
    result = subprocess.run(command,cwd=ROOT,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8',errors='replace')[-3500:])

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def read(name):
    return json.loads((SOURCE/name).read_text(encoding='utf-8'))

def ass_seconds(value):
    h,m,s=value.split(':');return int(h)*3600+int(m)*60+float(s)

def ass_stamp(value):
    cs=round(value*100)
    return f'{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}'

def srt_stamp(value):
    ms=round(value*1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'

def prepare():
    shots=read('shot-plan.json')
    timeline=read('timeline.json')
    captions=read('caption-timing.json')
    for rows in (timeline,captions):
        for row in rows:
            for key in ('start','end'):row[key]=round(row[key]+INTRO,3)
    save('timeline.json',timeline)
    save('caption-timing.json',captions)
    for name in ['script-source.json','script-plan.json','narration.txt','narration.mp3','ending-preview.mp3']:
        shutil.copy2(SOURCE/name,ROOT/name)
    (ROOT/'captions.srt').write_text('\n\n'.join(f"{i+1}\n{srt_stamp(c['start'])} --> {srt_stamp(c['end'])}\n{c['text']}" for i,c in enumerate(captions))+'\n',encoding='utf-8-sig')
    lines=[]
    for line in (SOURCE/'captions.ass').read_text(encoding='utf-8-sig').splitlines():
        line=line.replace(',KaiTi,',',Kaiti SC,').replace(',SimSun,',',Songti SC,')
        if line.startswith('Dialogue:'):
            fields=line.split(',',9)
            # The separate poster now carries the opening title. Keep its original 3s desk introduction.
            if fields[3]=='Title' and ass_seconds(fields[1])<3:continue
            fields[1]=ass_stamp(ass_seconds(fields[1])+INTRO)
            fields[2]=ass_stamp(ass_seconds(fields[2])+INTRO)
            line=','.join(fields)
        lines.append(line)
    (ROOT/'captions.ass').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
    new_shots=[dict(id='intro',start=0,end=INTRO,asset='assets/片头海报_善假于物.png',frames=75,status='独立海报')]
    for s in shots:
        row=dict(s,start=round(s['start']+INTRO,3),end=round(s['end']+INTRO,3))
        if s['id'] in [3,16,18,37,38]:row['asset']=f"assets/screen-{s['id']}.png"
        new_shots.append(row)
    new_shots.append(dict(id='tail-reserve',start=212.64,end=TOTAL,asset='desk-return.jpg',frames=75,status='片尾新增3秒预留；暂续书桌画面，设计待讨论'))
    assert all(abs(a['end']-b['start'])<.001 for a,b in zip(new_shots,new_shots[1:]))
    assert sum(s['frames'] for s in new_shots)==round(TOTAL*FPS)
    save('shot-plan.json',new_shots)
    return shots,timeline

def encode_still(source,target,frames):
    # Match the imported clips' codec, cadence and pixel format; do not touch existing picture/audio speed.
    vf='scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=25'
    ff(['-loop','1','-framerate',FPS,'-i',source,'-vf',vf,'-frames:v',frames,'-an','-c:v','libx264','-threads',2,'-preset','veryfast','-crf',20,'-pix_fmt','yuv420p',target])
    print('CLIP_READY',target.name,flush=True)

def render(shots):
    jobs=[(ROOT/'assets/片头海报_善假于物.png',CLIPS/'intro.mp4',75),(ASSETS/'desk-return.jpg',CLIPS/'tail-reserve.mp4',75)]
    jobs += [(ROOT/f"assets/screen-{s['id']}.png",CLIPS/f"{s['id']:02d}.mp4",s['frames']) for s in shots if s['id'] in [3,16,18,37,38]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda job:encode_still(*job),jobs))
    # This machine's FFmpeg lacks libass. Preserve the already verified burned-in
    # captions from the imported movie instead of rebuilding them with a different renderer.
    # All learning-screen edits sit above y=900; the caption band below remains intact.
    changed=[s for s in shots if s['id'] in [3,16,18,37,38]]
    inputs=['-i',SOURCE/'shanjia-voice-preview.mp4','-loop','1','-framerate',25,'-i',ASSETS/'desk-opening.jpg']
    for s in changed:inputs+=['-loop','1','-framerate',25,'-i',ROOT/f"assets/screen-{s['id']}.png"]
    graph=['[1:v]scale=1920:1080,setsar=1[desk]','[0:v][desk]overlay=0:0:enable=lt(t\\,3):shortest=1[v0]']
    for index,s in enumerate(changed):
        n=index+2
        graph.append(f'[{n}:v]crop=1920:900:0:0[screen{index}]')
        graph.append(f"[v{index}][screen{index}]overlay=0:0:enable='gte(t,{s['start']})*lt(t,{s['end']})':shortest=1[v{index+1}]")
    ff(['-filter_complex_threads',1,*inputs,'-filter_complex',';'.join(graph),'-map','[v5]','-an','-t',209.64,'-c:v','libx264','-threads',4,'-preset','veryfast','-crf',20,'-pix_fmt','yuv420p',CLIPS/'body-captioned.mp4'])
    paths=[CLIPS/'intro.mp4',CLIPS/'body-captioned.mp4',CLIPS/'tail-reserve.mp4']
    assert all(p.is_file() for p in paths)
    (ROOT/'pictures.txt').write_text('\n'.join("file '"+str(p).replace("'","'\\''")+"'" for p in paths)+'\n')
    ff(['-f','concat','-safe',0,'-i','pictures.txt','-i',SOURCE/'narration.wav','-map','0:v:0','-map','1:a:0','-af','adelay=3000:all=1,apad','-t',TOTAL,'-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-metadata','title=善假于物·学习细节与片头预演 v2','-metadata','comment=AI合成配音预演；片头新增3秒海报；片尾3秒仅作预留，设计待讨论',MOVIE])

def package(timeline):
    html=(SOURCE/'index.html').read_text(encoding='utf-8')
    replacements={
      'poster':('image/png',ROOT/'assets/片头海报_善假于物.png'),
      'film':('video/mp4',MOVIE),
      'fullAudio':('audio/mpeg',ROOT/'narration.mp3'),
      'endingAudio':('audio/mpeg',ROOT/'ending-preview.mp3'),
    }
    for target,(mime,file) in replacements.items():
        value='data:'+mime+';base64,'+base64.b64encode(file.read_bytes()).decode()
        if target=='poster':
            html=re.sub(r'poster="[^"]*"',lambda m:'poster="'+value+'"',html,count=1)
        else:
            html=re.sub(r'(<(?:video|audio)\b[^>]*\bid="'+target+r'"[^>]*\bsrc=")[^"]*(")',lambda m:m[1]+value+m[2],html,count=1)
    srt='data:application/x-subrip;base64,'+base64.b64encode((ROOT/'captions.srt').read_bytes()).decode()
    html=re.sub(r'data:application/x-subrip;base64,[^"\s>]+',lambda m:srt,html)
    html=re.sub(r'(data-(?:time|start|end)=")([\d.]+)(")',lambda m:m[1]+str(round(float(m[2])+INTRO,3))+m[3],html)
    html=html.replace('seek(144.48)','seek(147.48)')
    html=html.replace('完整版 3 分 30 秒','完整版 3 分 36 秒').replace('新版台词试听 · 2026.10.15','学习细节与片头预演 · 2026.10.16')
    html=html.replace('<title>善假于物 · 新台词配音预览</title>','<title>善假于物 · 学习细节与片头预演 v2</title>')
    html=html.replace('<span>加长结尾 65 秒</span>','<span>片头 +3 秒 · 片尾预留 +3 秒</span>')
    html=html.replace('按声音节奏重排现有画面 · 1080P / 25fps','五处学习界面细化 · 片头海报 · 1080P / 25fps')
    html=re.sub(r'(<button class="chapter"[^>]*>.*?<small>)(\d\d:\d\d)(</small>)',lambda m:m[1]+f"{(int(m[2][:2])*60+int(m[2][3:])+3)//60:02d}:{(int(m[2][:2])*60+int(m[2][3:])+3)%60:02d}"+m[3],html)
    html=html.replace('善假于物_配音预览.mp4','善假于物_配音预演_v2.mp4')
    html=html.replace('画面沿用已有分镜原画和测试视频；纸面新写内容、人物完整动作仍待正式制作。本版的重点是听配音与叙事节奏。尚未加入背景音乐。','五处电脑特写已加入可读的课文、词义、比较解释、删改和笔记内容；新增独立片头海报。最后新增的 3 秒先延续书桌画面，片尾设计待讨论。纸面新写内容、人物完整动作仍待正式制作，尚未加入背景音乐。')
    html=html.replace('新版台词保持完整 · 原作品文件保留 · 单文件离线预览页','v2 · 配音保持完整 · 片尾设计待讨论 · 单文件离线预览页')
    (ROOT/'index.html').write_text(html,encoding='utf-8')
    ff(['-ss','10.8','-i',MOVIE,'-frames:v',1,ROOT/'verify-screen.png'])
    ff(['-ss','176','-i',MOVIE,'-frames:v',1,ROOT/'verify-revision.png'])
    ff(['-ss','214','-i',MOVIE,'-frames:v',1,ROOT/'verify-tail.png'])
    ff(['-i',MOVIE,'-f','null','-'])
    info=probe(MOVIE)
    assert abs(float(info['format']['duration'])-TOTAL)<.01
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (video['width'],video['height'],video['avg_frame_rate'])==(1920,1080,'25/1')
    assert any(s['codec_type']=='audio' for s in info['streams'])
    clean=lambda s:''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]',s)).lower()
    assert clean(''.join(c['text'] for c in json.loads((ROOT/'caption-timing.json').read_text())))==clean((ROOT/'narration.txt').read_text())
    save('verification.json',dict(duration=TOTAL,intro_added=INTRO,tail_reserved=TAIL,tail_design='待讨论；暂时延续书桌画面',voice_content_unchanged=True,post_production_speed_changes=0,full_decode='passed',subtitle_offset=INTRO,caption_text_match=True,shots=50,screen_shots_updated=[3,16,18,37,38],ending_start=147.48,bytes=MOVIE.stat().st_size,probe=info,source_video_sha256=hashlib.sha256((SOURCE/'shanjia-voice-preview.mp4').read_bytes()).hexdigest()))
    print('VERIFIED',MOVIE.name,TOTAL,MOVIE.stat().st_size,flush=True)

if __name__=='__main__':
    shots,timeline=prepare()
    render(shots)
    package(timeline)
