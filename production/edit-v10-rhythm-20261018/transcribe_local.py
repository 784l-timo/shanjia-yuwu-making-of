from pathlib import Path
import hashlib,json,re,wave
import numpy as np
import sherpa_onnx

ROOT=Path(__file__).resolve().parent
model=Path('/private/tmp/qianmo-sensevoice-q8.onnx')
assert hashlib.sha256(model.read_bytes()).hexdigest()=='6887cdd6fc94c3e4cb5aea8b62dead45229643708d20b8ec8a4a736dfb45f6af'
with wave.open('/private/tmp/qianmo-full.wav') as w:
    sr=w.getframerate();samples=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
duration=len(samples)/sr
log=Path('/private/tmp/qianmo-silences.log').read_text()
silences=[];start=None
for line in log.splitlines():
    m=re.search(r'silence_start: ([\d.]+)',line)
    if m:start=float(m[1])
    m=re.search(r'silence_end: ([\d.]+)',line)
    if m and start is not None:silences.append((start,float(m[1])));start=None
cuts=[0.0]
while duration-cuts[-1]>20:
    candidates=[(a+b)/2 for a,b in silences if cuts[-1]+8<(a+b)/2<cuts[-1]+20]
    cuts.append(candidates[-1] if candidates else cuts[-1]+18)
cuts.append(duration)
r=sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(model),tokens='/private/tmp/qianmo-sensevoice-tokens.txt',num_threads=4,language='zh',use_itn=True)
rows=[]
for a,b in zip(cuts,cuts[1:]):
    s=r.create_stream();s.accept_waveform(sr,samples[round(a*sr):round(b*sr)])
    r.decode_stream(s)
    result=dict(text=s.result.text,timestamps=list(s.result.timestamps),tokens=list(s.result.tokens))
    result.update(start=a,end=b)
    if 'timestamps' in result:result['timestamps']=[round(a+t,3) for t in result['timestamps']]
    rows.append(result)
    (ROOT/'asr-raw.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(round(a,2),round(b,2),result.get('text'),flush=True)
(ROOT/'asr-full.txt').write_text('\n'.join(x['text'] for x in rows))
(ROOT/'silences.json').write_text(json.dumps(silences))
print('DONE',duration,flush=True)
