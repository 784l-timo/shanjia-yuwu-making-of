"""Replace the ascent scenes and remove the water-to-still jump in the existing cut."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
V3 = ROOT.parent / 'edit-v3-20261017'
PROJECT = ROOT.parents[1]
SOURCE = V3 / '善假于物_配音预演_v3_学习细节与完整片尾.mp4'
MOVIE = ROOT / '善假于物_配音预演_v4_登高场景与流畅修订.mp4'
TOTAL = 215.64
PATCHES = [
    dict(id='water', start=28.68, end=37.12, source='sources/水凝成冰.mp4', usable=9.84, reason='连续呈现水面到冰晶，取消 33 秒处跳切到静帧'),
    dict(id='ascent', start=55.24, end=60.56, source='sources/登阶背影.mp4', usable=5.32, reason='用户新增登阶素材；对应跂而望与登高博见'),
    dict(id='summit', start=60.56, end=74.92, source='sources/高处远眺.mp4', usable=7.84, reason='用户新增高处远眺素材；连续承载登高、顺风与随后理解'),
    dict(id='boat-main', start=90.72, end=95.88, source='sources/舟行测试.mp4', usable=3.84, reason='原慢放靠重复帧；改为运动补帧'),
    dict(id='boat-return', start=163.4, end=167.8, source='sources/舟行测试.mp4', usable=3.84, reason='同一舟行素材的第二次慢放同步修订'),
]


def run(command):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-5000:])
    return result.stdout


def ff(args):
    return run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args])


def save(name, obj):
    (ROOT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def seconds(stamp):
    h, m, s = stamp.split(':')
    return int(h)*3600 + int(m)*60 + float(s)


def prepare():
    for name in ['sources', 'clips', 'captions', 'audit']:
        (ROOT / name).mkdir(exist_ok=True)
    originals = [
        (Path('/path/to/user/Downloads/分析项目文档作用.mp4'), '高处远眺.mp4'),
        (Path('/path/to/user/Downloads/分析项目文档作用 (1).mp4'), '登阶背影.mp4'),
        (PROJECT / '全片预演_HyperFrames/assets/water-freezing.mp4', '水凝成冰.mp4'),
        (PROJECT / '全片预演_HyperFrames/assets/boat-test.mp4', '舟行测试.mp4'),
    ]
    ledger = []
    for old, name in originals:
        target = ROOT / 'sources' / name
        shutil.copy2(old, target)
        ledger.append(dict(original=str(old), local='sources/' + name, sha256=sha(target)))
    shutil.copytree(V3 / 'assets', ROOT / 'assets', dirs_exist_ok=True)
    for name in ['captions.ass', 'captions.srt', 'caption-timing.json', 'timeline.json',
                 'narration.txt', 'narration.mp3', 'ending-preview.mp3', 'script-source.json', 'script-plan.json']:
        shutil.copy2(V3 / name, ROOT / name)
    overlays = []
    for line in (ROOT / 'captions.ass').read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('Dialogue:'):
            continue
        fields = line.split(',', 9)
        start, end = seconds(fields[1]), seconds(fields[2])
        if not any(start < p['end'] and end > p['start'] for p in PATCHES):
            continue
        text = re.sub(r'\{[^}]*\}', '', fields[9]).replace(r'\N', '\n')
        assert fields[3] in ('Quote', 'Narration')
        overlays.append(dict(id=len(overlays), start=start, end=end, style=fields[3], text=text,
                             file=f"captions/{len(overlays):02d}.png"))
    save('caption-overlays.json', overlays)
    save('patch-plan.json', PATCHES)
    save('provenance.json', dict(sources=ledger, base='../edit-v3-20261017/' + SOURCE.name,
         base_sha256=sha(SOURCE), audio_policy='copy complete v3 audio; source clip audio is not mixed',
         method='continuous source ranges, optical-flow frame conversion, full-frame replacements with matching caption times',
         no_new_generated_media=True))
    old_shots = json.loads((V3 / 'shot-plan.json').read_text())
    shots = []
    for s in old_shots:
        active = next((p for p in PATCHES if p['start'] <= s['start'] and p['end'] >= s['end']), None)
        if active:
            if not any(x.get('id') == active['id'] for x in shots):
                shots.append(dict(active, asset=active['source'], frames=round((active['end']-active['start'])*25)))
        else:
            shots.append(s)
    assert all(abs(a['end']-b['start']) < .001 for a, b in zip(shots, shots[1:]))
    assert sum(s['frames'] for s in shots) == 5391
    save('shot-plan.json', shots)
    print('PREPARED', len(overlays), 'caption overlays', flush=True)


def encode(args, output, crf=19):
    ff([*args, '-an', '-c:v', 'libx264', '-threads', 2, '-preset', 'veryfast', '-crf', crf,
        '-pix_fmt', 'yuv420p', '-video_track_timescale', 12800, output])


def render_patch(p):
    duration = round(p['end']-p['start'], 2)
    frames = round(duration*25)
    factor = duration/p['usable']
    clean = ROOT / f"clips/{p['id']}-clean.mp4"
    output = ROOT / f"clips/{p['id']}.mp4"
    # Source has guard frames beyond the selected range. Interpolation gets its
    # look-ahead without clone-padding, looping, or holding the final frame.
    vf = (f'setpts={factor:.10f}*(PTS-STARTPTS),'
          'minterpolate=fps=25:mi_mode=mci:mc_mode=obmc:me_mode=bidir:vsbmc=1,'
          'scale=1920:1080,setsar=1')
    encode(['-filter_threads', 1, '-i', ROOT / p['source'], '-vf', vf, '-frames:v', frames], clean, 16)
    rows = [c for c in json.loads((ROOT / 'caption-overlays.json').read_text())
            if c['start'] < p['end'] and c['end'] > p['start']]
    inputs = ['-i', clean]
    graph = []
    for i, c in enumerate(rows):
        inputs += ['-loop', 1, '-framerate', 25, '-i', ROOT / c['file']]
        start, end = max(0, c['start']-p['start']), min(duration, c['end']-p['start'])
        fade = 'format=rgba'
        if c['start'] >= p['start']:
            fade += f',fade=t=in:st={start:.4f}:d=0.06:alpha=1'
        if c['end'] <= p['end']:
            fade += f',fade=t=out:st={max(start,end-.08):.4f}:d=0.08:alpha=1'
        graph.append(f'[{i+1}:v]{fade}[c{i}]')
        previous = '[0:v]' if i == 0 else f'[v{i-1}]'
        graph.append(f"{previous}[c{i}]overlay=0:880:enable='gte(t,{start:.4f})*lt(t,{end:.4f})':shortest=1[v{i}]")
    encode(['-filter_complex_threads', 1, *inputs, '-filter_complex', ';'.join(graph),
            '-map', f'[v{len(rows)-1}]', '-frames:v', frames], output)
    print('PATCH_READY', p['id'], duration, flush=True)
    return output


def render():
    parts = []
    cursor = 0
    jobs = []
    for p in PATCHES:
        if p['start'] > cursor:
            jobs.append(dict(id=f'keep-{len(jobs)}', start=cursor, end=p['start']))
        parts.append((p['start'], ROOT / f"clips/{p['id']}.mp4"))
        cursor = p['end']
    if cursor < TOTAL:
        jobs.append(dict(id=f'keep-{len(jobs)}', start=cursor, end=TOTAL))

    def keep(job):
        output = ROOT / f"clips/{job['id']}.mp4"
        encode(['-ss', job['start'], '-i', SOURCE, '-frames:v', round((job['end']-job['start'])*25)], output)
        print('CONTEXT_READY', job['id'], flush=True)
        return (job['start'], output)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(render_patch, PATCHES))
    with ThreadPoolExecutor(max_workers=2) as pool:
        parts.extend(pool.map(keep, jobs))
    parts.sort()
    (ROOT / 'pictures.txt').write_text('\n'.join("file '" + str(f).replace("'", "'\\''") + "'" for _, f in parts)+'\n')
    ff(['-f', 'concat', '-safe', 0, '-i', 'pictures.txt', '-i', SOURCE, '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'copy', '-c:a', 'copy', '-t', TOTAL, '-movflags', '+faststart',
        '-metadata', 'title=善假于物·登高场景与流畅修订 v4',
        '-metadata', 'comment=新增登阶与高处远眺；连续水凝成冰；舟行慢放补帧；AI试听人声', MOVIE])
    print('MOVIE_READY', flush=True)


def package():
    html = (V3 / 'index.html').read_text()
    uri = 'data:video/mp4;base64,' + base64.b64encode(MOVIE.read_bytes()).decode()
    html, count = re.subn(r'(<video\b[^>]*\bid="film"[^>]*\bsrc=")[^"]*(")', lambda m:m[1]+uri+m[2], html, count=1)
    assert count == 1
    replacements = {
        '学习细节与完整片尾预演 v3': '登高场景与流畅修订 v4',
        '完整片尾接入预演 · 2026.10.17': '登高场景与流畅修订 · 2026.10.17',
        '学习细节 · 独立片头 · 书桌片尾 · 1080P / 25fps': '新增登高场景 · 连续结冰 · 舟行慢放修订 · 1080P / 25fps',
        '善假于物_配音预演_v3_学习细节与完整片尾.mp4': MOVIE.name,
        'v3 · 推荐 A 片尾接入审看 · 单文件离线预览页': 'v4 · 新增登高场景与流畅修订 · 单文件离线预览页',
        '<button id="last18">最后 18 秒</button>': '<button id="water">看水凝成冰</button> <button id="ascent">看登高新场景</button> <button id="last18">最后 18 秒</button>',
        "document.getElementById('last18').onclick=()=>seek(197.64);": "document.getElementById('last18').onclick=()=>seek(197.64);document.getElementById('water').onclick=()=>seek(28.68);document.getElementById('ascent').onclick=()=>seek(55.24);",
        '五处电脑特写已加入可读的课文、词义、比较解释、删改和笔记内容；新增独立片头海报。': '本轮接入用户提供的登阶背影和高处远眺视频，按古文旁白顺序安排；水凝成冰改为完整连续过程，取消中途跳切静帧，并修订两处舟行慢放。五处学习界面与独立片头海报继续保留。',
    }
    for old, new in replacements.items():
        assert old in html, old
        html = html.replace(old, new)
    (ROOT / 'index.html').write_text(html)
    for label, start, duration in [('水凝成冰_修订对比', 27.68, 10.44), ('登高新场景_局部预览', 53.24, 23.68)]:
        for suffix, movie in ([('修改前', SOURCE), ('修改后', MOVIE)] if '对比' in label else [('修改后', MOVIE)]):
            ff(['-ss', start, '-i', movie, '-t', duration, '-c:v', 'libx264', '-threads', 2,
                '-preset', 'veryfast', '-crf', 19, '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                ROOT / f'{label}_{suffix}.mp4'])


def audio_packets(file):
    return json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_packets',
        '-show_data_hash', 'sha256', '-show_entries', 'packet=pts_time,data_hash', '-of', 'json', file]))['packets']


def boundary_mad(movie, time):
    data = ff(['-ss', time-.04, '-i', movie, '-frames:v', 2, '-vf', 'crop=1920:850:0:0,scale=160:72',
               '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
    n = 160*72
    assert len(data) == n*2
    return sum(abs(a-b) for a, b in zip(data[:n], data[n:]))/n


def verify():
    ff(['-i', MOVIE, '-f', 'null', '-'])
    info = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', MOVIE]))
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    assert abs(float(info['format']['duration'])-TOTAL) < .001
    assert (video['width'], video['height'], video['avg_frame_rate'], int(video['nb_frames'])) == (1920,1080,'25/1',5391)
    assert audio_packets(SOURCE) == audio_packets(MOVIE)
    assert (ROOT / 'captions.srt').read_bytes() == (V3 / 'captions.srt').read_bytes()
    caption_text = json.loads((ROOT / 'caption-timing.json').read_text())
    assert len(caption_text) == 69
    before, after = boundary_mad(SOURCE, 33), boundary_mad(MOVIE, 33)
    assert after < before*.35, (before, after)
    for p in PATCHES:
        d = json.loads(run(['ffprobe','-v','error','-show_entries','stream=nb_frames','-of','json',ROOT/f"clips/{p['id']}.mp4"]))
        assert int(d['streams'][0]['nb_frames']) == round((p['end']-p['start'])*25)
    uri = re.search(r'<video\b[^>]*id="film"[^>]*src="data:video/mp4;base64,([^"]+)"', (ROOT/'index.html').read_text())[1]
    assert hashlib.sha256(base64.b64decode(uri)).hexdigest() == sha(MOVIE)
    ff(['-ss', 28.68, '-i', MOVIE, '-t', 8.44, '-vf', 'fps=1,scale=480:270,tile=4x2', '-frames:v', 1, ROOT/'audit/water-after.jpg'])
    ff(['-ss', 55.24, '-i', MOVIE, '-t', 19.68, '-vf', 'fps=1/2.4,scale=480:270,tile=4x2', '-frames:v', 1, ROOT/'audit/ascent-after.jpg'])
    for label, t in [('stairs',57.6),('summit',62.4),('wind',67.2),('water',35.2),('boat',93.2)]:
        ff(['-ss',t,'-i',MOVIE,'-frames:v',1,ROOT/f'audit/check-{label}.png'])
    save('verification.json', dict(duration=TOTAL, size=MOVIE.stat().st_size, full_decode='passed',
         resolution=[1920,1080], fps=25, frames=5391, complete_audio_packets_and_timestamps_equal=True,
         subtitles_identical_to_v3=True, caption_count=69, embedded_video_matches_mp4=True,
         water_33s_background_boundary_MAD=dict(before=before,after=after),
         patches=PATCHES, no_clone_padding_or_loops_in_replacements=True, probe=info))
    print('VERIFIED', 'water boundary:', round(before,3), '->', round(after,3), flush=True)


if __name__ == '__main__':
    if '--prepare' in sys.argv:
        prepare()
    else:
        render()
        package()
        verify()
