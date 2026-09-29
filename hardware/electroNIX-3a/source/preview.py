#!/usr/bin/env python3
"""Render vector/ in the source image's colours next to the source JPEG."""
import os, subprocess, tempfile, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, 'vector'); P = 'electroNIX3a-'
tmp = tempfile.mkdtemp()
def render(layers, out, dpi=600):
    cmd = ['gerbv', '-x', 'png', '--dpi=%d' % dpi, '-B', '0', '-b', '#FFFFFF']
    for f, col in layers: cmd += ['-f', col, os.path.join(V, P + f)]
    cmd += ['-o', out]; subprocess.run(cmd, stderr=subprocess.DEVNULL); return Image.open(out).convert('RGB')
edge = ('Edge_Cuts.gm1', '#000000FF')
comp = render([edge, ('PTH.drl', '#000000FF'), ('NPTH.drl', '#000000FF'),
               ('F_Cu.gtl', '#F80204FF'), ('B_Cu.gbl', '#0D0289FF')], os.path.join(tmp, 'c.png'))
bare = render([edge, ('PTH.drl', '#000000FF'), ('NPTH.drl', '#000000FF'),
               ('F_Cu.gtl', '#F80204FF'), ('B_Cu.gbl', '#0D0289FF')], os.path.join(tmp, 'b.png'))
top = render([edge, ('PTH.drl', '#000000FF'), ('NPTH.drl', '#000000FF'), ('F_Cu.gtl', '#C00000FF')], os.path.join(tmp, 't.png'))
bot = render([edge, ('PTH.drl', '#000000FF'), ('NPTH.drl', '#000000FF'), ('B_Cu.gbl', '#0D0289FF')], os.path.join(tmp, 'bo.png'))
W, H = comp.size
src = Image.open(os.path.join(ROOT, 'source', 'electroNIX-3a_layout.jpg')).convert('RGB').crop((27, 97, 799, 567)).resize((W, H), Image.LANCZOS)
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 40)
except Exception: font = None
def sheet(items, name, cols=2):
    rows = (len(items) + cols - 1) // cols
    o = Image.new('RGB', (cols * (W + 30), rows * (H + 70)), 'white'); d = ImageDraw.Draw(o)
    for i, (im, t) in enumerate(items):
        x, y = (i % cols) * (W + 30), (i // cols) * (H + 70)
        o.paste(im, (x, y + 60)); d.text((x + 5, y + 10), t, fill='black', font=font)
    o.save(os.path.join(ROOT, 'preview', name))
sheet([(src, 'Source JPEG'), (comp, 'Vector rebuild, same colours')], 'vector_vs_source.png')
top.save(os.path.join(ROOT, 'preview', 'vector_top.png'))
bot.save(os.path.join(ROOT, 'preview', 'vector_bottom_seen_from_top.png'))
bare.save(os.path.join(ROOT, 'preview', 'vector_both_no_silk.png'))
