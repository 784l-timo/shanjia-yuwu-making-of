from pathlib import Path
import base64, concurrent.futures, hashlib, html, json, math, os, re, subprocess, sys, types, urllib.request, urllib.error, uuid, wave

R = Path(__file__).resolve().parent
P = R.parents[2]
SOURCE = P / 'output/shanjia-review-20261014/comparison-data.json'
ASSETS = P / '善假于物_制作规划/善假于物_制作规划/全片预演_HyperFrames/assets'
BIN = Path('C:/Users/Administrator/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-essentials_build/bin')
VOICE = 'zh_male_shaonianzixin_uranus_bigtts'
for name in ('audio', 'clips', 'verify'):
    (R / name).mkdir(parents=True, exist_ok=True)

def save(name, value):
    (R / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def clean(text):
    return ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text)).lower()

def ff(args):
    result = subprocess.run([str(BIN / 'ffmpeg.exe'), '-hide_banner', '-loglevel', 'error', '-y'] + [str(x) for x in args], cwd=R, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-2000:])
    return result.stdout

def probe(path):
    return json.loads(subprocess.check_output([str(BIN / 'ffprobe.exe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))

def duration(path):
    return float(probe(path)['format']['duration'])

def get_key():
    # Credentials are loaded only into memory from the account's existing configuration.
    def post(url, headers, data, timeout):
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status, body = response.status, response.read()
        return types.SimpleNamespace(status_code=status, json=lambda: json.loads(body))
    sys.modules['requests'] = types.SimpleNamespace(post=post)
    sys.path.insert(0, str(P / 'output/dazhong-digital-human/pilot'))
    from volc_client import signed_call
    status, response = signed_call('ListAPIKeys', {'ProjectName': 'default'}, service='speech_saas_prod', region='cn-beijing', host='open.volcengineapi.com', version='2025-05-20')
    def find(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in ('apikey', 'api_key') and isinstance(value, str):
                    yield value
                else:
                    yield from find(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from find(value)
    keys = list(find(response.get('Result', {})))
    if not keys:
        raise RuntimeError('Existing speech credential lookup failed: HTTP ' + str(status))
    return keys[0]

def plan():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    rows = []
    for section in data['sections']:
        for kind in ('quote', 'new'):
            text = section[kind]
            if not text:
                continue
            for block in text.split('〔停〕'):
                # Complete sentences stay together; the marked pauses are explicit edit boundaries.
                text = block.strip()
                if text:
                    rows.append(dict(id=len(rows)+1, chapter=section['number'], title=section['title'], kind=kind, text=text,
                                     pause_after=0.65 if kind == 'quote' else (0.75 if section['number'] == 6 else 0.48)))
    for i, row in enumerate(rows):
        if i == len(rows)-1:
            row['pause_after'] = 3.0
        elif rows[i+1]['chapter'] != row['chapter']:
            row['pause_after'] = 1.0
        elif rows[i+1]['kind'] != row['kind']:
            row['pause_after'] = 0.85
    save('script-source.json', data)
    save('script-plan.json', rows)
    (R / 'narration.txt').write_text('\n\n'.join(x['text'] for x in rows)+'\n', encoding='utf-8')
    return rows

def request_body(row):
    style = '用清晰、自然的少年男声讲述自己的阅读体会，温和认真，有思考的停顿，像和老师分享，不用夸张播音腔。只朗读正文。'
    rate = -8
    if row['kind'] == 'quote':
        style = '清晰从容地朗读文言文，声调自然，句读分明，略带韵律，不拖腔，不喊口号。只朗读正文。'
        rate = -14
    elif row['chapter'] == 6:
        style = '少年在读书之后分享自己的领悟，语气真诚温暖，带着向前探索的期待，坚定但克制，句末自然收住。只朗读正文。'
        rate = -10
    additions = {
        'context_texts': [style],
        'pronunciation_dict': {'tone': [
            '生非异也/(xing4)(fei1)(yi4)(ye3)',
            '跂/(qi3)', '须臾/(xu1)(yu2)', '舆马/(yu2)(ma3)',
            '跬步/(kui3)(bu4)', '善假于物/(shan4)(jia3)(yu2)(wu4)',
            '假舟楫/(jia3)(zhou1)(ji2)', '假舆马/(jia3)(yu2)(ma3)'
        ]},
        'aigc_metadata': {'enable': True, 'content_producer': 'DoubaoVoice', 'produce_id': 'shanjia-voice-preview-20261015'}
    }
    return {'user': {'uid': 'shanjia-preview'}, 'req_params': {
        'text': row['text'], 'speaker': VOICE,
        'audio_params': {'format': 'mp3', 'sample_rate': 24000, 'bit_rate': 160000, 'speech_rate': rate, 'enable_subtitle': True},
        'additions': json.dumps(additions, ensure_ascii=False)
    }}

def synth(row, key):
    path = R / 'audio' / f"{row['id']:02d}.mp3"
    meta_path = path.with_suffix('.json')
    body = request_body(row)
    encoded = json.dumps(body, ensure_ascii=False).encode('utf-8')
    digest = hashlib.sha256(encoded).hexdigest()
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('request_sha256') == digest:
            print('CACHED', row['id'], flush=True)
            return
        raise RuntimeError('A different cached take exists; use a new take directory')
    headers = {'Content-Type': 'application/json', 'X-Api-Key': key, 'X-Api-Resource-Id': 'seed-tts-2.0', 'X-Api-Request-Id': str(uuid.uuid4())}
    request = urllib.request.Request('https://openspeech.bytedance.com/api/v3/tts/unidirectional', data=encoded, headers=headers)
    audio, events = bytearray(), []
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            for line in response:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get('code', 0) not in (0, 20000000):
                    raise RuntimeError('TTS returned code '+str(item.get('code'))+': '+str(item.get('message', ''))[:220])
                if item.get('data'):
                    audio.extend(base64.b64decode(item['data']))
                events.append({k:v for k,v in item.items() if k != 'data'})
    except urllib.error.HTTPError as error:
        # Print only the service status and message, never request headers or credential responses.
        payload = error.read()
        try:
            detail = json.loads(payload)
            message = str(detail.get('message', detail.get('error', '')))[:240]
        except Exception:
            message = 'No structured service message'
        raise RuntimeError(f'TTS HTTP {error.code}: {message}') from None
    if not audio:
        raise RuntimeError('TTS returned no audio')
    path.write_bytes(audio)
    save(str(meta_path.relative_to(R)), {'request_sha256': digest, 'request': body, 'events': events})
    words = [w for event in events for w in event.get('sentence', {}).get('words', [])]
    if clean(''.join(w['word'] for w in words)) != clean(row['text']):
        raise RuntimeError('Subtitle transcript mismatch in segment '+str(row['id']))
    print('AUDIO_READY', row['id'], 'seconds', round(duration(path), 3), 'words', len(words), flush=True)

def generate(pilot=False):
    rows = plan()
    key = get_key()
    for row in (rows[:1] if pilot else rows):
        synth(row, key)

def stamp(t, srt=False):
    if srt:
        ms = round(max(0,t)*1000)
        return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    cs = round(max(0,t)*100)
    return f'{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}'

def caption_chunks(text):
    parts = re.findall(r'.*?[，。！？；：](?:[”’])?|.+$', text)
    chunks = []
    for part in parts:
        if not clean(part):
            if chunks:
                chunks[-1] += part
            continue
        boundary = bool(chunks and re.search(r'[。！？；][”’]?$', chunks[-1]))
        if chunks and not boundary and (len(clean(chunks[-1])) < 6 or len(clean(part)) < 4) and len(chunks[-1]+part) <= 23:
            chunks[-1] += part
        else:
            chunks.append(part)
    assert all(len(x) <= 27 for x in chunks), chunks
    assert clean(''.join(chunks)) == clean(text)
    return chunks

def compose_audio():
    rows = json.loads((R/'script-plan.json').read_text(encoding='utf-8'))
    captions, timeline = [], []
    offset = 3.0
    ff(['-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t',3,'audio/00.wav'])
    for row in rows:
        n = row['id']
        path = R/'audio'/f'{n:02d}.mp3'
        spoken = duration(path)
        length = math.ceil((spoken+row['pause_after'])*25)/25
        meta = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        words = [w for e in meta['events'] for w in e.get('sentence',{}).get('words',[])]
        assert clean(''.join(w['word'] for w in words)) == clean(row['text']), n
        assert all(w['startTime'] <= w['endTime'] and w['endTime'] <= spoken+.1 for w in words), n
        char_times = []
        for word in words:
            char_times.extend([(word['startTime'],word['endTime'])]*len(clean(word['word'])))
        index = 0
        for text in caption_chunks(row['text']):
            count = len(clean(text))
            start = offset+max(0,char_times[index][0]-.07)
            end = min(offset+length-.08,offset+char_times[index+count-1][1]+.18)
            captions.append(dict(segment=n,chapter=row['chapter'],text=text,start=round(start,3),end=round(end,3),style='Quote' if row['kind']=='quote' else 'Narration'))
            index += count
        timeline.append(dict(row,start=round(offset,3),end=round(offset+length,3),spoken=spoken,words=words))
        ff(['-i',path,'-af',f'afade=t=in:st=0:d=0.03,afade=t=out:st={spoken-.03}:d=0.03,apad','-t',length,'-ar',48000,'-ac',1,R/'audio'/f'{n:02d}.wav'])
        offset += length
    for a,b in zip(captions,captions[1:]):
        a['end'] = min(a['end'],b['start']-.025)
    assert all(c['end']>c['start'] for c in captions)
    assert clean(''.join(c['text'] for c in captions)) == clean(''.join(r['text'] for r in rows))
    save('timeline.json',timeline)
    save('caption-timing.json',captions)
    (R/'sounds.txt').write_text('\n'.join(f"file 'audio/{n:02d}.wav'" for n in range(len(rows)+1)),encoding='utf-8')
    # Level matching preserves the generated delivery; no tempo or pitch filters are used.
    ff(['-f','concat','-safe',0,'-i','sounds.txt','-af','loudnorm=I=-18:TP=-2:LRA=10','-ar',48000,'-ac',1,'narration.wav'])
    ff(['-i','narration.wav','-c:a','libmp3lame','-b:a','192k','-metadata','title=善假于物·新版台词配音预览','-metadata','comment=AI合成通用青年男声，非田阡陌真人录音','narration.mp3'])
    ending = next(x['start'] for x in timeline if x['chapter']==6)
    ff(['-ss',ending,'-i','narration.wav','-c:a','libmp3lame','-b:a','192k','-metadata','title=善假于物·加长结尾试听','ending-preview.mp3'])
    (R/'captions.srt').write_text('\n\n'.join(f"{i+1}\n{stamp(c['start'],True)} --> {stamp(c['end'],True)}\n{c['text']}" for i,c in enumerate(captions))+'\n',encoding='utf-8-sig')
    head = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narration,KaiTi,56,&H00EAF3F7,&H00EAF3F7,&H00202523,&H80202523,0,0,0,0,100,100,1,0,1,2.6,1,2,90,90,74,1
Style: Quote,SimSun,54,&H00CDE5F5,&H00CDE5F5,&H00202523,&H80202523,0,0,0,0,100,100,1,0,1,2.6,1,2,90,90,74,1
Style: Title,KaiTi,106,&H00EAF3F7,&H00EAF3F7,&H00202523,&H80202523,0,0,0,0,100,100,14,0,1,2,1,5,100,100,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = [f"Dialogue: 0,{stamp(c['start'])},{stamp(c['end'])},{c['style']},,0,0,0,,"+r'{\fad(60,80)}'+c['text'] for c in captions]
    events.insert(0,r'Dialogue: 1,0:00:00.20,0:00:02.80,Title,,0,0,0,,{\fad(350,350)}善假于物')
    events.append(f'Dialogue: 1,{stamp(offset-2.5)},{stamp(offset)},Title,,0,0,0,,'+r'{\fad(450,450)}善假于物')
    (R/'captions.ass').write_text(head+'\n'.join(events)+'\n',encoding='utf-8-sig')
    save('audio-verification.json',dict(duration=duration(R/'narration.wav'),ending_start=ending,ending_duration=duration(R/'ending-preview.mp3'),segments=len(rows),captions=len(captions),word_timestamp_text_match=True,voice=VOICE,voice_label='通用青年男声·少年梓辛 2.0',post_production_speed_changes=0))
    print('AUDIO_ASSEMBLED',round(offset,2),'ENDING',round(offset-ending,2),flush=True)

def shot_plan():
    timeline=json.loads((R/'timeline.json').read_text(encoding='utf-8'))
    # Cuts follow the spoken transitions. A single source is held across connected phrases.
    mapping={
        1:[('', 'desk-opening.jpg'),('可看懂了','screen-question.jpg')],
        2:[('', 'pencil-pause.jpg')],
        3:[('', 'book-reading.jpg')],
        4:[('', 'indigo-dye.mp4'),('冰，','water-freezing.mp4')],
        5:[('', 'ice.jpg'),('学习，','writing-keyword.jpg')],
        6:[('', 'pencil-pause.jpg')],
        7:[('', 'low-view.jpg'),('吾尝跂','mountain-steps.jpg')],
        8:[('', 'high-view.jpg'),('顺风而呼','wind-road.jpg')],
        9:[('', 'high-view.jpg'),('AI 也能','screen-question.jpg')],
        10:[('', 'book-reading.jpg'),('比较解释','screen-revision.jpg')],
        11:[('', 'wind-road.jpg'),('假舟楫者','boat-test.mp4')],
        12:[('', 'riverbank-corrected.jpg')],
        13:[('', 'boat.png'),('可桨怎样划','paddle-test.mp4')],
        14:[('', 'paddle-adjusted.jpg'),('原来，','river-wide.png')],
        15:[('', 'high-view.jpg'),('积水成渊','river-wide.png')],
        16:[('', 'mountain-steps.jpg'),('不积小流','river-wide.png')],
        17:[('', 'writing-keyword.jpg')],
        18:[('', 'paper-revision.jpg')],
        19:[('', 'desk-return.jpg')],
        20:[('', 'book-reading.jpg')],
        21:[('', 'desk-return.jpg'),('也能通过学习','pencil-pause.jpg')],
        22:[('', 'boat-test.mp4'),('今天，','screen-question.jpg'),('工具让更多','screen-revision.jpg'),('学习让我','paper-revision.jpg')],
        23:[('', 'pencil-pause.jpg'),('分辨不同','book-reading.jpg'),('把想法真正','writing-keyword.jpg'),('一次次尝试','paddle-test.mp4'),('我也能超越','high-view.jpg')],
        24:[('', 'book-reading.jpg')],
        25:[('', 'boat-test.mp4'),('去抵达昨天','river-wide.png')],
    }
    shots=[dict(start=0,end=3,asset='desk-opening.jpg',segment=0)]
    def anchor(row, phrase):
        position=clean(row['text']).index(clean(phrase))
        length=0
        for word in row['words']:
            length+=len(clean(word['word']))
            if length>position:
                return round((row['start']+word['startTime'])*25)/25
        raise ValueError(phrase)
    for row in timeline:
        starts=[(row['start'] if not p else anchor(row,p),asset) for p,asset in mapping[row['id']]]
        for j,(start,asset) in enumerate(starts):
            end=starts[j+1][0] if j+1<len(starts) else row['end']
            shots.append(dict(start=start,end=end,asset=asset,segment=row['id']))
    # The final silent title returns to the desk, preserving the book-to-life arc.
    shots[-1]['end']-=3.0
    shots.append(dict(start=shots[-1]['end'],end=timeline[-1]['end'],asset='desk-return.jpg',segment=25))
    for i,shot in enumerate(shots):
        shot['id']=i+1
        shot['frames']=round((shot['end']-shot['start'])*25)
        assert shot['frames']>0 and (ASSETS/shot['asset']).exists()
        if i:
            assert abs(shot['start']-shots[i-1]['end'])<.002
    save('shot-plan.json',shots)
    return shots

def render_video():
    shots=shot_plan()
    def render(shot):
        source=ASSETS/shot['asset']
        target=R/'clips'/f"{shot['id']:02d}.mp4"
        seconds=shot['frames']/25
        signature=hashlib.sha256(json.dumps(shot,sort_keys=True).encode()+str(source.stat().st_mtime_ns).encode()).hexdigest()
        marker=target.with_suffix('.sha256')
        if target.exists() and marker.exists() and marker.read_text()==signature:
            return
        args=[]
        video=source.suffix=='.mp4'
        if not video:
            args=['-loop','1','-framerate','25']
        args+=['-i',source]
        vf='scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1'
        if video:
            # Slow only the visual source when needed, by at most 1.8x; then hold its last frame.
            factor=min(1.8,max(1.0,seconds/duration(source)))
            vf+=f',setpts={factor}*(PTS-STARTPTS),fps=25,tpad=stop_mode=clone:stop_duration={seconds}'
        else:
            vf+=',fps=25'
        args+=['-vf',vf,'-frames:v',shot['frames'],'-an','-c:v','libx264','-threads',2,'-preset','veryfast','-crf',20,'-pix_fmt','yuv420p',target]
        ff(args)
        marker.write_text(signature)
        print('SHOT_READY',shot['id'],flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(render,shots))
    (R/'pictures.txt').write_text('\n'.join(f"file 'clips/{s['id']:02d}.mp4'" for s in shots),encoding='utf-8')
    ff(['-f','concat','-safe',0,'-i','pictures.txt','-c','copy','-movflags','+faststart','visual-master.mp4'])
    ff(['-i','visual-master.mp4','-i','narration.wav','-map','0:v:0','-map','1:a:0','-vf','subtitles=captions.ass','-c:v','libx264','-threads',4,'-preset','veryfast','-crf',20,'-c:a','aac','-b:a','192k','-movflags','+faststart','-metadata','comment=AI通用青年男声配音预览；现有概念画面，非田阡陌真人录音','shanjia-voice-preview.mp4'])
    print('VIDEO_ASSEMBLED',round(duration(R/'shanjia-voice-preview.mp4'),2),flush=True)

def verify_and_page():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    movie=R/'shanjia-voice-preview.mp4'
    info=probe(movie)
    total=float(info['format']['duration'])
    ff(['-i',movie,'-f','null','-'])
    audioinfo=json.loads((R/'audio-verification.json').read_text(encoding='utf-8'))
    assert abs(total-audioinfo['duration'])<.09
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (video['width'],video['height'],video['avg_frame_rate'])==(1920,1080,'25/1')
    with wave.open(str(R/'narration.wav')) as wavefile:
        assert wavefile.getsampwidth()==2
        samples=np.frombuffer(wavefile.readframes(wavefile.getnframes()),dtype='<i2').astype(np.float32)/32768
    peak=float(np.max(np.abs(samples)))
    assert peak<.99
    timeline=json.loads((R/'timeline.json').read_text(encoding='utf-8'))
    captions=json.loads((R/'caption-timing.json').read_text(encoding='utf-8'))
    shots=json.loads((R/'shot-plan.json').read_text(encoding='utf-8'))
    images=[]
    for n in [1,3,4,7,8,11,13,16,17,20,21,22,23,24,25]:
        c=next(c for c in captions if c['segment']==n)
        timestamp=(c['start']+c['end'])/2
        target=R/'verify'/f'{n:02d}.jpg'
        ff(['-ss',timestamp,'-i',movie,'-frames:v',1,target])
        images.append((target,timestamp))
    sheet=Image.new('RGB',(1440,math.ceil(len(images)/3)*294),'#111c1c')
    draw=ImageDraw.Draw(sheet)
    for i,(path,timestamp) in enumerate(images):
        picture=Image.open(path).resize((480,270))
        x,y=i%3*480,i//3*294
        sheet.paste(picture,(x,y))
        draw.text((x+10,y+274),f'{path.stem} / {timestamp:.2f}s',fill='white')
    sheet.save(R/'verify/contact-sheet.jpg',quality=90)
    ff(['-ss',1.5,'-i',movie,'-frames:v',1,'poster.jpg'])
    save('verification.json',dict(duration=total,ending_start=audioinfo['ending_start'],ending_duration=audioinfo['ending_duration'],file_bytes=movie.stat().st_size,full_decode='passed',source_script_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),caption_text_match=True,service_word_timestamps=True,post_production_voice_speed_changes=0,voice=VOICE,audio_peak_dbfs=20*math.log10(peak),shots=len(shots),captions=len(captions),probe=info,limitations=['AI合成通用青年男声，非田阡陌真人原声','沿用既有概念画面，新增写字内容与完整人物动作尚未制作','服务字级文字核对与技术检查通过，不等于已完成连续人工听审']))
    chapters=[]
    for ch in range(1,7):
        selection=[x for x in timeline if x['chapter']==ch]
        chapters.append(dict(number=ch,title=selection[0]['title'],start=selection[0]['start'],end=selection[-1]['end']))
    minutes,seconds=divmod(round(total),60)
    ends=round(audioinfo['ending_duration'])
    chapter_html=''.join(f'<button class="chapter" data-time="{c["start"]}"><span>{c["number"]:02d}</span><b>{html.escape(c["title"])}</b><small>{int(c["start"])//60:02d}:{int(c["start"])%60:02d}</small></button>' for c in chapters)
    text_html=''.join(f'<section><h3>{c["number"]:02d} {html.escape(c["title"])}</h3>'+''.join(f'<p class="line {x["kind"]}" data-start="{x["start"]}" data-end="{x["end"]}" tabindex="0">{html.escape(x["text"])}</p>' for x in timeline if x['chapter']==c['number'])+'</section>' for c in chapters)
    page='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>善假于物 · 新台词配音预览</title><style>
:root{color-scheme:dark;--bg:#102021;--panel:#192e2f;--ink:#f5f0e5;--muted:#aabbb8;--accent:#e4bc77}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top right,#284544,transparent 65%),var(--bg);color:var(--ink);font:16px/1.7 "Microsoft YaHei",system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:45px 28px 70px}.eyebrow{color:var(--accent);font-size:12px;letter-spacing:3px}h1{font-family:KaiTi,serif;font-size:52px;letter-spacing:8px;margin:10px 0 0}h2{font-size:22px;margin:0 0 12px}.subtitle{color:var(--muted);margin:6px 0 20px}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.chips span{border:1px solid #496060;border-radius:30px;padding:4px 12px;font-size:13px}.player{background:#071212;border:1px solid #46605a;border-radius:18px;overflow:hidden;box-shadow:0 20px 60px #0004}video{display:block;width:100%;aspect-ratio:16/9;background:#071212}.bar{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px 20px;flex-wrap:wrap}button,a{font:inherit}button{cursor:pointer;border:1px solid #61746e;border-radius:8px;color:var(--ink);background:#263e3d;padding:8px 14px}button:hover,button:focus-visible{border-color:var(--accent)}.primary{background:var(--accent);color:#142222;border-color:var(--accent);font-weight:bold}.bar small{color:var(--muted)}.chapters{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:14px 0 30px}.chapter{display:flex;flex-direction:column;align-items:flex-start;text-align:left;padding:10px 12px}.chapter span{color:var(--accent);font-size:12px}.chapter b{font-size:14px}.chapter small{color:var(--muted);font-size:12px}.chapter.active{border-color:var(--accent);background:#3a4840}.audio-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:0 0 28px}.card{padding:22px;background:#21363588;border:1px solid #405655;border-radius:14px}.card p{color:var(--muted);margin:4px 0 14px;font-size:14px}audio{width:100%;height:42px}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.downloads{display:flex;gap:20px;flex-wrap:wrap;font-size:14px;margin-top:14px}details{background:#142828;border:1px solid #405655;border-radius:14px;padding:20px 24px}summary{cursor:pointer;font-size:18px}section{margin-top:28px}section h3{color:var(--accent);font-size:17px}.line{padding:9px 14px;margin:5px 0;border-left:2px solid transparent;border-radius:0 8px 8px 0;cursor:pointer}.line:hover{background:#304744}.line.active{background:#344c44;border-color:var(--accent)}.line.quote{font-family:SimSun,serif;color:#eed8af}.note{color:var(--muted);font-size:13px;line-height:1.8;margin-top:20px}footer{border-top:1px solid #405655;margin-top:28px;padding-top:16px;color:#859b97;font-size:12px}@media(max-width:720px){main{padding:24px 14px}h1{font-size:38px}.chapters{grid-template-columns:repeat(3,1fr)}.audio-grid{grid-template-columns:1fr}.bar{padding:12px}.card{padding:18px}.subtitle{font-size:14px}}
</style></head><body><main><div class="eyebrow">田阡陌作品 · 新版台词试听 · 2026.10.15</div><h1>善假于物</h1><p class="subtitle">借今天的舟楫，去抵达昨天还到不了的地方。</p><div class="chips"><span>完整版 __DURATION__</span><span>加长结尾 __ENDING__ 秒</span><span>通用青年男声 · AI 合成</span><span>纯人声 · 无配乐</span></div><div class="player"><video id="film" controls preload="metadata" poster="data:image/jpeg;base64,__POSTER__" src="data:video/mp4;base64,__VIDEO__"></video><div class="bar"><div><button class="primary" id="play">从头播放</button> <button id="ending">重点听结尾</button></div><small>按声音节奏重排现有画面 · 1080P / 25fps</small></div></div><nav class="chapters">__CHAPTERS__</nav><div class="audio-grid"><div class="card"><h2>只听完整配音</h2><p>先判断青年感、古文句读，以及前后段落的语气是否一致。</p><audio id="fullAudio" controls preload="metadata" src="data:audio/mpeg;base64,__AUDIO__"></audio><div class="downloads"><a id="audioDownload" download="善假于物_完整配音预览.mp3">下载 MP3</a><a id="videoDownload" download="善假于物_配音预览.mp4">下载视频</a></div></div><div class="card"><h2>单独听加长结尾</h2><p>从“我又读了一遍”开始，听情绪递进和最后一句的收束。</p><audio id="endingAudio" controls preload="metadata" src="data:audio/mpeg;base64,__ENDING_AUDIO__"></audio><div class="downloads"><a id="endingDownload" download="善假于物_结尾试听.mp3">下载结尾 MP3</a><a href="data:application/x-subrip;base64,__SRT__" download="善假于物_字幕.srt">下载字幕</a></div></div></div><details><summary>配音全文 · 点击一句可跳转试听</summary>__TEXT__</details><p class="note">声音为豆包通用音色“少年梓辛 2.0”，用于判断文案、停顿和表达，不是阡陌本人录音。古文按原字保留，已为“生（xìng）非异也、跂、跬步”等设置发音提示。字幕按合成服务返回的字级时间戳对齐。</p><p class="note">画面沿用已有分镜原画和测试视频；纸面新写内容、人物完整动作仍待正式制作。本版的重点是听配音与叙事节奏。尚未加入背景音乐。</p><footer>新版台词保持完整 · 原作品文件保留 · 单文件离线预览页</footer></main><script>
const film=document.getElementById('film'), full=document.getElementById('fullAudio'), ending=document.getElementById('endingAudio');const media=[film,full,ending];media.forEach(el=>el.addEventListener('play',()=>media.forEach(other=>{if(other!==el)other.pause()})));function seek(t){film.currentTime=t;film.play().catch(()=>{});}document.getElementById('play').onclick=()=>seek(0);document.getElementById('ending').onclick=()=>seek(__ENDING_START__);document.querySelectorAll('.chapter').forEach(b=>b.onclick=()=>seek(+b.dataset.time));document.querySelectorAll('.line').forEach(p=>{p.onclick=()=>seek(+p.dataset.start);p.onkeydown=e=>{if(e.key==='Enter')seek(+p.dataset.start)}});film.addEventListener('timeupdate',()=>{const t=film.currentTime;document.querySelectorAll('.line').forEach(p=>p.classList.toggle('active',t>=+p.dataset.start&&t<+p.dataset.end));document.querySelectorAll('.chapter').forEach((b,i,all)=>b.classList.toggle('active',t>=+b.dataset.time&&(i===all.length-1||t<+all[i+1].dataset.time)))});document.getElementById('videoDownload').href=film.src;document.getElementById('audioDownload').href=full.src;document.getElementById('endingDownload').href=ending.src;
</script></body></html>'''
    fields={'DURATION':f'{minutes} 分 {seconds:02d} 秒','ENDING':str(ends),'CHAPTERS':chapter_html,'TEXT':text_html,'ENDING_START':str(audioinfo['ending_start'])}
    for token,path in {'POSTER':'poster.jpg','VIDEO':'shanjia-voice-preview.mp4','AUDIO':'narration.mp3','ENDING_AUDIO':'ending-preview.mp3','SRT':'captions.srt'}.items():
        fields[token]=base64.b64encode((R/path).read_bytes()).decode()
    for token,value in fields.items():
        page=page.replace('__'+token+'__',value)
    assert not re.search(r'__[A-Z_]+__',page)
    (R/'index.html').write_text(page,encoding='utf-8')
    print('VERIFIED_AND_PACKAGED',round(total,2),movie.stat().st_size,'PEAK_DBFS',round(20*math.log10(peak),2),flush=True)

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else 'audio'
    try:
        if mode in ('audio', 'pilot'):
            generate(mode == 'pilot')
        if mode in ('compose', 'audio-only'):
            compose_audio()
        if mode in ('compose', 'video'):
            render_video()
        if mode in ('compose', 'verify'):
            verify_and_page()
    except Exception as error:
        print(type(error).__name__+': '+str(error), flush=True)
        raise SystemExit(1)
