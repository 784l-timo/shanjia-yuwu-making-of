"""Local video-only removal of visible corner labels; preserve complete audio and timing."""
from pathlib import Path
import base64
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
V4 = ROOT.parent / 'edit-v4-20261017'
SOURCE = V4 / '善假于物_配音预演_v4_登高场景与流畅修订.mp4'
MOVIE = ROOT / '善假于物_配音预演_v5_画面去字.mp4'
TOTAL = 215.64
INTERVALS = [(23.96, 28.68), (28.68, 37.12), (55.24, 60.56), (60.56, 74.92)]
BOXES = {'top-left': (24, 44, 356, 96), 'bottom-right': (1544, 940, 370, 104)}


def run(args):
    r = subprocess.run(list(map(str,args)), cwd=ROOT, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors='replace')[-4000:])
    return r.stdout


def ff(args):
    return run(['ffmpeg','-hide_banner','-loglevel','error','-y',*args])


def save(name, data):
    (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def prepare():
    (ROOT/'masks').mkdir(exist_ok=True)
    for name,(x,y,w,h) in BOXES.items():
        data=bytearray(1920*1080)
        for row in range(y,y+h):
            data[row*1920+x:row*1920+x+w]=bytes([255])*w
        (ROOT/f'masks/{name}.pgm').write_bytes(b'P5\n1920 1080\n255\n'+data)
    shutil.copytree(V4/'assets',ROOT/'assets',dirs_exist_ok=True)
    for name in ['captions.srt','captions.ass','caption-timing.json','timeline.json','shot-plan.json',
                 'script-plan.json','script-source.json','narration.txt','narration.mp3','ending-preview.mp3']:
        shutil.copy2(V4/name,ROOT/name)
    save('repair-plan.json',dict(intervals=INTERVALS,boxes=BOXES,
         method='FFmpeg removelogo bounded background interpolation on the two corner masks',
         scope='Visible Doubao AI-generated lettering in indigo, water, ascent and summit footage',
         limitation='Repaired corner texture is approximate; original background pixels under the label cannot be recovered.'))
    save('provenance.json',dict(source='../edit-v4-20261017/'+SOURCE.name,sha256=sha(SOURCE),
         user_request='去掉视频中的几个豆包 AI 生成字样',
         source_files_modified=False,media_generation_status='Underlying scene sources are still generated media.'))


def render():
    enabled='+'.join(f'gte(t,{a})*lt(t,{b})' for a,b in INTERVALS)
    vf='scale=in_range=auto:out_range=tv,format=yuv420p'
    for name in BOXES:
        vf+=f",removelogo=filename=masks/{name}.pgm:enable='{enabled}'"
    # Mixed input segments carry full/limited-range flags. Normalize the pixel
    # format before encoding; keep the filter clock continuous through changes.
    ff(['-reinit_filter',0,'-i',SOURCE,'-map','0:v:0','-map','0:a:0','-vf',vf,
        '-c:v','libx264','-threads',4,'-preset','veryfast','-crf',18,'-pix_fmt','yuv420p',
        '-color_range','tv','-c:a','copy','-t',TOTAL,'-movflags','+faststart',
        '-metadata','title=善假于物·画面去字预演 v5',MOVIE])
    print('MOVIE_READY',MOVIE.name,flush=True)


def package():
    html=(V4/'index.html').read_text()
    uri='data:video/mp4;base64,'+base64.b64encode(MOVIE.read_bytes()).decode()
    html,count=re.subn(r'(<video\b[^>]*\bid="film"[^>]*\bsrc=")[^"]*(")',lambda m:m[1]+uri+m[2],html,count=1)
    assert count==1
    replacements={
        '登高场景与流畅修订 v4':'画面去字预演 v5',
        '登高场景与流畅修订 · 2026.10.17':'画面去字预演 · 2026.10.17',
        '新增登高场景 · 连续结冰 · 舟行慢放修订 · 1080P / 25fps':'已去除角落生成字样 · 1080P / 25fps',
        '善假于物_配音预演_v4_登高场景与流畅修订.mp4':MOVIE.name,
        'v4 · 新增登高场景与流畅修订 · 单文件离线预览页':'v5 · 画面角落去字 · 单文件离线预览页',
        '本轮接入用户提供的登阶背影和高处远眺视频，按古文旁白顺序安排；':'本轮去掉染布、结冰、登阶与远眺画面角落的“豆包 AI 生成”字样，局部补绘背景。保留用户提供的登阶背影和高处远眺视频，按古文旁白顺序安排；',
    }
    for old,new in replacements.items():
        assert old in html,old
        html=html.replace(old,new)
    (ROOT/'index.html').write_text(html)
    (ROOT/'audit/ocr-after').mkdir(exist_ok=True)
    ff(['-i',MOVIE,'-filter_complex','fps=4,split[a][b];[a]crop=480:216:0:0[top];[b]crop=480:216:1440:864[bottom];[top][bottom]vstack',
        '-q:v',2,ROOT/'audit/ocr-after/frame-%04d.jpg'])
    # Fixed sample times make early/late appearances in both corners reviewable.
    times=[25.5,28.4,30.0,33.5,36.5,57.0,60.1,62.4,68.0,71.5,74.4]
    for i,t in enumerate(times):
        ff(['-ss',t,'-i',MOVIE,'-frames:v',1,ROOT/f'audit/after-{i:02d}.png'])
    print('PACKAGED_AND_SAMPLED',flush=True)


def packets(file):
    return json.loads(run(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_data_hash','sha256',
        '-show_entries','packet=pts_time,data_hash','-of','json',file]))['packets']


def verify():
    ff(['-i',MOVIE,'-f','null','-'])
    info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',MOVIE]))
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_frames']))==(1920,1080,'25/1',5391)
    assert abs(float(info['format']['duration'])-TOTAL)<.001
    assert packets(SOURCE)==packets(MOVIE)
    assert (ROOT/'captions.srt').read_bytes()==(V4/'captions.srt').read_bytes()
    encoded=re.search(r'<video\b[^>]*id="film"[^>]*src="data:video/mp4;base64,([^"]+)"',(ROOT/'index.html').read_text())[1]
    assert hashlib.sha256(base64.b64decode(encoded)).hexdigest()==sha(MOVIE)
    save('verification.json',dict(duration=TOTAL,bytes=MOVIE.stat().st_size,full_decode='passed',
         complete_audio_packets_and_timestamps_equal=True,subtitles_identical_to_v4=True,
         embedded_video_matches_mp4=True,repair_intervals=INTERVALS,repair_boxes=BOXES,probe=info))
    print('VERIFIED',TOTAL,'audio/captions unchanged',flush=True)


if __name__=='__main__':
    prepare()
    render()
    package()
    verify()
