"""Track the bright display against its dark bezel using constrained edge fits."""
from pathlib import Path
import json
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parent
SOURCE=Path('/path/to/user/Downloads/分析项目文档作用 (3).mp4')
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(SOURCE),'-vf','format=gray','-f','rawvideo','-'])
frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,720,1280).astype(np.float32)


def fit_edge(gray,edge):
    horizontal=edge in ('top','bottom')
    if edge=='top':positions=np.arange(635,951,7);expected=226+(positions-603)*16/378;sign=1
    elif edge=='bottom':positions=np.arange(590,920,7);expected=440+(positions-552)*51/386;sign=-1
    elif edge=='left':positions=np.arange(255,420,5);expected=603+(positions-226)*(-51)/214;sign=1
    else:positions=np.arange(267,465,5);expected=981+(positions-242)*(-43)/249;sign=-1
    picked=[];strength=[]
    for u,e in zip(positions,expected):
        candidates=np.arange(round(e)-16,round(e)+17)
        if horizontal:
            score=sign*np.array([gray[v+3,u-1:u+2].mean()-gray[v-3,u-1:u+2].mean() for v in candidates])
        else:
            score=sign*np.array([gray[u-1:u+2,v+3].mean()-gray[u-1:u+2,v-3].mean() for v in candidates])
        # Prefer a nearby high-contrast boundary, not the text within the screen.
        j=int(np.argmax(score-.12*(candidates-e)**2))
        picked.append(candidates[j]);strength.append(score[j])
    picked=np.asarray(picked);keep=np.asarray(strength)>25
    assert keep.sum()>len(positions)*.55,(edge,keep.sum())
    for _ in range(3):
        line=np.polyfit(positions[keep],picked[keep],1)
        keep=(abs(picked-np.polyval(line,positions))<3.5)&(np.asarray(strength)>25)
    return line


def intersect(horizontal,vertical):
    a,b=horizontal;c,d=vertical
    y=(a*d+b)/(1-a*c);x=c*y+d
    return [float(x),float(y)]


corners=[]
for frame in frames:
    top,bottom,left,right=[fit_edge(frame,k) for k in ['top','bottom','left','right']]
    corners.append([intersect(top,left),intersect(top,right),intersect(bottom,right),intersect(bottom,left)])
points=np.asarray(corners)
smooth=np.stack([points[max(0,i-2):min(len(points),i+3)].mean(axis=0) for i in range(len(points))])
output=[]
for n in range(91):
    position=n/25*24;i=int(position);mix=position-i
    p=smooth[i]*(1-mix)+smooth[min(i+1,len(smooth)-1)]*mix
    output.append(dict(frame=n,time=round(n/25,3),corners=p.round(3).tolist()))
reference=np.asarray([[603,226],[981,242],[938,491],[552,440]])
assert abs(smooth-reference).max()<35,'Unexpected display movement; inspect tracking'
(ROOT/'screen-tracking.json').write_text(json.dumps(dict(source=str(SOURCE),source_frames=len(frames),
    output_frames=output,method='constrained bezel gradient fits, robust line intersections, five-frame smoothing'),ensure_ascii=False,indent=2))
print(json.dumps({'first':output[0],'middle':output[45],'last':output[-1]},ensure_ascii=False))
