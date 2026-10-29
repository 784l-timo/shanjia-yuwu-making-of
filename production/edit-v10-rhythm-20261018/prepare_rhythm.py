from pathlib import Path
import difflib,json,re,wave,subprocess
import numpy as np

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'edit-v6-20261017'
segments=json.loads((BASE/'script-plan.json').read_text())
changes={
1:'AI 几秒钟就能解释“善假于物”。可看懂了解释，我又冒出了一个问题：',
10:'省下来的时间，我可以用来阅读原文、比较解释，把没想通的地方接着想。',
13:'舟能帮我渡河，可桨怎么划，还得看水流。',
21:'这句话让我想到：一个普通的人，也能通过学习、借助外物，做到以前做不到的事情。',
22:'以前，人们借舟楫渡过江河。今天，我也可以借助 AI 接触更多知识，尝试更多想法。工具让更多事情成为可能，学习让我把这些帮助，一点点变成自己的本领。',
}
for s in segments:s['text']=changes.get(s['id'],s['text'])
def norm(t):return ''.join(c.lower() for c in t if c.isalnum())
raw=json.loads((ROOT/'asr-raw.json').read_text())
observed=[];times=[]
for r in raw:
 for token,t in zip(r['tokens'],r['timestamps']):
  for c in norm(token):observed.append(c);times.append(t)
reference=''.join(norm(s['text']) for s in segments)
actual=''.join(observed)
# Full Levenshtein alignment, preserving the raw recognition separately.
n,m=len(reference),len(actual)
dp=np.empty((n+1,m+1),dtype=np.int16);dp[:,0]=np.arange(n+1);dp[0,:]=np.arange(m+1)
for i in range(1,n+1):
 for j in range(1,m+1):dp[i,j]=min(dp[i-1,j]+1,dp[i,j-1]+1,dp[i-1,j-1]+(reference[i-1]!=actual[j-1]))
mapping={};i,j=n,m
while i or j:
 if i and j and dp[i,j]==dp[i-1,j-1]+(reference[i-1]!=actual[j-1]):mapping[i-1]=j-1;i-=1;j-=1
 elif i and dp[i,j]==dp[i-1,j]+1:i-=1
 else:j-=1
known=sorted(mapping)
for i in range(n):
 if i not in mapping:
  left=max((k for k in known if k<i),default=None);right=min((k for k in known if k>i),default=None)
  mapping[i]=mapping[left] if left is not None else mapping[right]
char_times=[times[mapping[i]] for i in range(n)]
source_audio=ROOT.parents[1]/'素材入库/真人口播_整段_20261018/原始录音.m4a'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(source_audio),'-ar','48000','-ac','1','/private/tmp/qianmo-source48.wav'],check=True)
with wave.open('/private/tmp/qianmo-source48.wav') as w:
 sr=w.getframerate();samples=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16)
duration=len(samples)/sr
silences=json.loads((ROOT/'silences.json').read_text())
offset=0
for s in segments:
 length=len(norm(s['text']));s['raw_start']=char_times[offset];s['raw_end']=min(duration,char_times[offset+length-1]+.15)
 s['char_offset']=offset;offset+=length
# Adjust genuine detected silence only; never time-stretch or cut inside speech.
edits=[]
chapter_starts={3,7,11,15,20}
for s in segments[1:]:
 near=[(a,b) for a,b in silences if a<=s['raw_start']+.18 and b>=s['raw_start']-.4 and b-a>.35]
 if not near:continue
 a,b=min(near,key=lambda ab:abs(ab[1]-s['raw_start']))
 if any(abs(e['start']-a)<.01 for e in edits):continue
 target=.9 if s['id'] in chapter_starts else (.85 if s['id']==24 else .50)
 target=round(target*sr)/sr
 edits.append(dict(start=a,end=b,original=b-a,target=target,delta=target-(b-a),before_segment=s['id']))
edits.sort(key=lambda e:e['start'])
chunks=[];cursor=0
for e in edits:
 a,b=round(e['start']*sr),round(e['end']*sr);chunks.append(samples[cursor:a])
 original=samples[a:b];size=round(e['target']*sr)
 if size<len(original):
  half=size//2;quiet=np.concatenate([original[:half],original[-(size-half):]])
 else:
  half=len(original)//2;quiet=np.concatenate([original[:half],np.zeros(size-len(original),dtype=np.int16),original[half:]])
 chunks.append(quiet);cursor=b
chunks.append(samples[cursor:]);voice=np.concatenate(chunks)
with wave.open(str(ROOT/'narration-rhythm.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(voice.tobytes())
def adjusted(t):
 result=t
 for e in edits:
  if t>=e['end']:result+=e['delta']
  elif t>e['start']:result+=(t-e['start'])/(e['end']-e['start'])*e['delta']
 return result
for s in segments:s['start']=3+adjusted(s['raw_start']);s['end']=3+adjusted(s['raw_end'])
caption_rows=[]
for s in segments:
 index=s['char_offset'];parts=re.findall(r'[^，。；：！？、]+[，。；：！？、]?',s['text'])
 for part in parts:
  if not norm(part):continue
  # Short punctuation-based cues keep every line comfortably within the frame.
  subparts=[part[i:i+23] for i in range(0,len(part),23)]
  for text in subparts:
   length=len(norm(text))
   if not length:continue
   start=3+adjusted(char_times[index]);end=3+adjusted(min(duration,char_times[index+length-1]+.20))
   caption_rows.append(dict(start=start,end=max(start+.35,end),text=text,segment=s['id'],chapter=s['chapter']))
   index+=length
for a,b in zip(caption_rows,caption_rows[1:]):a['end']=min(a['end'],b['start']-.025)
endvoice=3+len(voice)/sr;total=round((endvoice+3)*25)/25
old=json.loads((BASE/'timeline.json').read_text())
anchors=[(0,0),(3,3)]+[(a['start'],b['start']) for a,b in zip(old,segments)]+[(212.64,endvoice),(215.64,total)]
def map_time(t):
 for (a,x),(b,y) in zip(anchors,anchors[1:]):
  if a<=t<=b:return x+(t-a)/(b-a)*(y-x)
 return total
def q(t):return round(t*25)/25
shots=json.loads((BASE/'shot-plan.json').read_text())
for s in shots:s['original_start']=s['start'];s['original_end']=s['end'];s['start']=q(map_time(s['start']));s['end']=q(map_time(s['end']))
for a,b in zip(shots,shots[1:]):a['end']=b['start']
shots[-1]['end']=total
# Reuse matching existing motion where it serves the same action.
reuse={5:'生成素材_v2/04_翻读劝学_5秒动态.mp4',9:'生成素材_v2/06_写下关键词_5秒动态.mp4',10:'生成素材_v2/03_停笔凝视_5秒动态.mp4',17:'生成素材_v2/04_翻读劝学_5秒动态.mp4',19:'生成素材_v2/10_风与远路_8秒动态.mp4',21:'人物校准_v2/阡陌_4秒人物稳定性测试.mp4',24:'渡河样片_v2/03_握桨入水_4秒测试.mp4',25:'渡河样片_v2/05_江面舟行_4秒测试.mp4',26:'生成素材_v2/10_风与远路_8秒动态.mp4',28:'生成素材_v2/08_登高台阶_8秒动态.mp4',30:'生成素材_v2/06_写下关键词_5秒动态.mp4',31:'生成素材_v2/15_纸面批注_5秒动态.mp4',32:'生成素材_v2/06_写下关键词_5秒动态.mp4',33:'生成素材_v2/04_翻读劝学_5秒动态.mp4',39:'生成素材_v2/15_纸面批注_5秒动态.mp4',40:'生成素材_v2/03_停笔凝视_5秒动态.mp4',41:'生成素材_v2/04_翻读劝学_5秒动态.mp4',42:'生成素材_v2/06_写下关键词_5秒动态.mp4',44:'生成素材_v2/10_风与远路_8秒动态.mp4',45:'生成素材_v2/04_翻读劝学_5秒动态.mp4',48:'生成素材_v2/06_写下关键词_5秒动态.mp4'}
for s in shots:
 if s['id'] in reuse:s['reuse']=reuse[s['id']]
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2))
save('speech-plan.json',segments);save('caption-timing.json',caption_rows);save('shot-plan.json',shots);save('pause-edits.json',edits)
save('rhythm-meta.json',dict(original_audio=duration,adjusted_audio=len(voice)/sr,total=total,alignment_edit_distance=int(dp[n,m]),reference_chars=n,recognized_chars=m,voice_speed_unchanged=True))
def stamp(t):
 ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
(ROOT/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(caption_rows))+'\n',encoding='utf-8-sig')
lines=['# 真人录音校订与节奏稿','\n按新录音转写并校订。古文同音误识按原句恢复；原始识别另存 asr-full.txt。正文未换成合成音。','\n“／”为短停，“//”为段落停顿；重音只作后续朗读参考，不改变现有人声音高。']
for s in segments:
 if s['id']==1 or s['chapter']!=segments[s['id']-2]['chapter']:lines+=['\n## '+s['title']+' //']
 lines.append('\n'+s['text'].replace('，','，／'))
lines+=['\n## 需要复听确认的细节','\n- “写到这里”被识别为“学到这里”，字幕按现行稿校为“写到这里”。','- “做到以前做不到的事情”按上下文校订；机器原识别为“说到以前”。','- 末句在“昨天”前可能有轻微口误，保留原声；字幕按完整句意整理，未擅自拼接词音。']
(ROOT/'真人录音校订与节奏稿.md').write_text('\n'.join(lines))
print(json.dumps(dict(meta=json.loads((ROOT/'rhythm-meta.json').read_text()),segments=[{k:s[k] for k in ['id','start','end','text']} for s in segments]),ensure_ascii=False,indent=2))
