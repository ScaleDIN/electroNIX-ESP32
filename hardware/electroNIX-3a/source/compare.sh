#!/bin/sh
# compare.sh x0 x1 y0 y1 out.png : image crop | vector top | vector bottom
cd "$(dirname "$0")/../vector"
D=$(mktemp -d)
gerbv -x png --dpi=1000 -B 0 -b '#FFFFFF' -f '#D01010' F_Cu.gtl -f '#FFFFFF' frame.gm1 -o $D/vt.png 2>/dev/null
gerbv -x png --dpi=1000 -B 0 -b '#FFFFFF' -f '#1428A0' B_Cu.gbl -f '#FFFFFF' frame.gm1 -o $D/vb.png 2>/dev/null
python3 - "$@" <<PY
import sys
from PIL import Image
x0,x1,y0,y1=map(float,sys.argv[1:5]); out=sys.argv[5]
t=Image.open('$D/vt.png').convert('RGB'); b=Image.open('$D/vb.png').convert('RGB')
o=Image.open('../source/electroNIX-3a_layout.jpg').convert('RGB').crop((27.5+x0*8.375,97.5+y0*8.375,27.5+x1*8.375,97.5+y1*8.375)).resize(t.size,Image.LANCZOS)
w=Image.new('RGB',(t.width*3+16,t.height),'white')
for i,im in enumerate((o,t,b)): w.paste(im,(i*(t.width+8),0))
w.save(out); print(w.size)
PY
