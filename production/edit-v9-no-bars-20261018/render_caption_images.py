from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parent
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Songti.ttc',48)
for c in json.loads((root/'caption-images.json').read_text()):
 im=Image.new('RGBA',(1920,200),(0,0,0,0));draw=ImageDraw.Draw(im)
 draw.text((960,88),c['text'],font=font,anchor='mm',fill='#f7f2e8',stroke_width=2,stroke_fill=(0,0,0,210))
 im.save(root/'captions'/c['file'])
