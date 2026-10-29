"""Integrate ending study A while copying the v2 picture and audio streams."""
from pathlib import Path
import base64
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
V2 = ROOT.parent / 'edit-v2-20261016'
OPTIONS = ROOT.parent / 'ending-options-20261016'
SOURCE = V2 / '善假于物_配音预演_v2_学习细节与片头.mp4'
MOVIE = ROOT / '善假于物_配音预演_v3_学习细节与完整片尾.mp4'
TOTAL, TAIL_START = 215.64, 212.64


def run(command):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-4000:])
    return result.stdout


def ff(args):
    return run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args])


def save(name, data):
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def packet_hashes(file, stream):
    data = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', stream,
        '-show_packets', '-show_data_hash', 'sha256', '-show_entries',
        'packet=pts_time,data_hash', '-of', 'json', file]))
    return data['packets']


def prepare():
    shutil.copytree(V2 / 'assets', ROOT / 'assets', dirs_exist_ok=True)
    for ext in ('png', 'html'):
        shutil.copy2(OPTIONS / f'assets/A_留在书桌.{ext}', ROOT / f'assets/片尾_A_学不可以已.{ext}')
    for name in ('captions.ass', 'captions.srt', 'caption-timing.json', 'timeline.json',
                 'narration.txt', 'narration.mp3', 'ending-preview.mp3', 'script-source.json', 'script-plan.json'):
        shutil.copy2(V2 / name, ROOT / name)
    shots = json.loads((V2 / 'shot-plan.json').read_text())
    shots[-1] = dict(id='ending-a', start=TAIL_START, end=TOTAL, frames=75,
        asset='assets/片尾_A_学不可以已.png', status='推荐 A 接入审看版；尚未由用户锁定片尾')
    save('shot-plan.json', shots)
    save('provenance.json', dict(source=str(SOURCE.relative_to(ROOT.parent)),
        source_sha256=digest(SOURCE.read_bytes()), tail_source='../ending-options-20261016/assets/A_留在书桌.png',
        tail_sha256=digest((ROOT / 'assets/片尾_A_学不可以已.png').read_bytes()),
        method='Copy v2 intro/body video packets and complete v2 audio; encode only the new 75-frame tail.',
        voice='AI 试听人声；非本人正式录音', tail_selection='推荐方案接入审看，未锁定最终设计'))


def render():
    (ROOT / 'clips').mkdir(exist_ok=True)
    tail = ROOT / 'clips/ending-a.mp4'
    ff(['-loop', 1, '-framerate', 25, '-i', ROOT / 'assets/片尾_A_学不可以已.png',
        '-vf', 'scale=1920:1080,setsar=1,fps=25', '-frames:v', 75, '-an',
        '-c:v', 'libx264', '-threads', 2, '-preset', 'veryfast', '-crf', 20, '-pix_fmt', 'yuv420p', tail])
    clips = [V2 / 'clips/intro.mp4', V2 / 'clips/body-captioned.mp4', tail]
    (ROOT / 'pictures.txt').write_text('\n'.join("file '" + str(p).replace("'", "'\\''") + "'" for p in clips) + '\n')
    ff(['-f', 'concat', '-safe', 0, '-i', 'pictures.txt', '-i', SOURCE,
        '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'copy', '-t', TOTAL,
        '-movflags', '+faststart', '-metadata', 'title=善假于物·学习细节与完整片尾预演 v3',
        '-metadata', 'comment=推荐A片尾接入审看版；AI试听人声；新增片头3秒与片尾3秒', MOVIE])
    print('MOVIE_READY', MOVIE.name, flush=True)


def package():
    html = (V2 / 'index.html').read_text(encoding='utf-8')
    media = 'data:video/mp4;base64,' + base64.b64encode(MOVIE.read_bytes()).decode()
    html, count = re.subn(r'(<video\b[^>]*\bid="film"[^>]*\bsrc=")[^"]*(")',
        lambda m: m[1] + media + m[2], html, count=1)
    assert count == 1
    changes = {
        '学习细节与片头预演 v2': '学习细节与完整片尾预演 v3',
        '学习细节与片头预演 · 2026.10.16': '完整片尾接入预演 · 2026.10.17',
        '完整版 3 分 36 秒': '完整版 3 分 35.64 秒',
        '片头 +3 秒 · 片尾预留 +3 秒': '片头 +3 秒 · A 片尾 +3 秒',
        '五处学习界面细化 · 片头海报 · 1080P / 25fps': '学习细节 · 独立片头 · 书桌片尾 · 1080P / 25fps',
        '善假于物_配音预演_v2.mp4': MOVIE.name,
        '最后新增的 3 秒先延续书桌画面，片尾设计待讨论。': '最后新增的 3 秒接入 A「留在书桌」：以“学不可以已”和创作者署名收束。这是推荐方案的完整审看版，片尾仍可调整。',
        'v2 · 配音保持完整 · 片尾设计待讨论 · 单文件离线预览页': 'v3 · 推荐 A 片尾接入审看 · 单文件离线预览页',
        '<button id="ending">重点听结尾</button>': '<button id="ending">重点听结尾</button> <button id="last18">最后 18 秒</button> <button id="tail">新增 3 秒片尾</button>',
        "document.getElementById('ending').onclick=()=>seek(147.48);": "document.getElementById('ending').onclick=()=>seek(147.48);document.getElementById('last18').onclick=()=>seek(197.64);document.getElementById('tail').onclick=()=>seek(212.64);",
        '</footer>': '</footer><p class="note"><a href="../ending-options-20261016/index.html">对比 A / B / C 三种片尾</a> · <a href="../../17_项目总览看板.html">项目总览</a></p>',
    }
    for old, new in changes.items():
        assert old in html, old
        html = html.replace(old, new)
    (ROOT / 'index.html').write_text(html, encoding='utf-8')


def verify():
    ff(['-i', MOVIE, '-f', 'null', '-'])
    info = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', MOVIE]))
    assert abs(float(info['format']['duration']) - TOTAL) < .001
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    assert (video['width'], video['height'], video['avg_frame_rate'], int(video['nb_frames'])) == (1920, 1080, '25/1', 5391)
    before = packet_hashes(SOURCE, 'v:0')
    after = packet_hashes(MOVIE, 'v:0')
    prefix = [p['data_hash'] for p in before if float(p['pts_time']) < TAIL_START]
    new_prefix = [p['data_hash'] for p in after if float(p['pts_time']) < TAIL_START]
    assert len(prefix) == 5316 and prefix == new_prefix, 'v2 picture changed before ending'
    audio_before = packet_hashes(SOURCE, 'a:0')
    audio_after = packet_hashes(MOVIE, 'a:0')
    assert audio_before == audio_after, 'audio or its timestamps changed'
    assert (ROOT / 'captions.srt').read_bytes() == (V2 / 'captions.srt').read_bytes()
    html = (ROOT / 'index.html').read_text()
    encoded = re.search(r'<video\b[^>]*id="film"[^>]*src="data:video/mp4;base64,([^"]+)"', html)[1]
    assert digest(base64.b64decode(encoded)) == digest(MOVIE.read_bytes())
    ff(['-ss', 214, '-i', MOVIE, '-frames:v', 1, ROOT / 'verify-tail.png'])
    save('verification.json', dict(duration=TOTAL, size=MOVIE.stat().st_size, full_decode='passed',
        copied_video_prefix_seconds=TAIL_START, copied_video_packets=len(prefix),
        video_prefix_packet_hashes_equal=True, complete_audio_packets_and_timestamps_equal=True,
        subtitles_identical_to_v2=True, embedded_video_matches_mp4=True,
        tail_start=TAIL_START, tail_duration=3, tail_selection='推荐 A；接入审看版，未锁定', probe=info))
    print('VERIFIED', TOTAL, 'seconds; 5316 video packets + complete audio unchanged', flush=True)


if __name__ == '__main__':
    prepare()
    render()
    package()
    verify()
