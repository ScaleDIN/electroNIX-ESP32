"""Tiny KiCad 7 schematic writer: symbols get short wire stubs ending in
labels / power symbols, so every connection is explicit and checkable."""
import math, uuid as _uuid, copy
from sexp import Sym, dump, find, find1
import libs

PROJECT = 'electroNIX-USB'
_ns = _uuid.UUID('6f1c1d2e-8f00-4e4e-9a52-6d3c7c0b1a00')
def uid(*k): return str(_uuid.uuid5(_ns, '/'.join(map(str, k))))

POWER = {'GND': ('power', 'GND', 270), '+5V': ('power', '+5V', 90),
         '+3V3': ('power', '+3V3', 90), '+170V': ('electronix', '+170V', 90),
         'VBUS': ('power', 'VBUS', 90)}

def r1(v): return round(v / 1.27) * 1.27

def rot(px, py, a):
    t = math.radians(a)
    return (px * math.cos(t) - py * math.sin(t), px * math.sin(t) + py * math.cos(t))

def txt(size=1.27, hide=False, justify=None):
    e = [Sym('effects'), [Sym('font'), [Sym('size'), size, size]]]
    if justify: e.append([Sym('justify')] + [Sym(j) for j in justify.split()])
    if hide: e.append(Sym('hide'))
    return e

class Sheet:
    def __init__(self, name, fname, title, page, paper='A3'):
        self.name, self.fname, self.title, self.page, self.paper = name, fname, title, page, paper
        self.items = []; self.libsyms = {}; self.syms = []
        self.nets = {}          # net -> count of label uses (for global/local decision)
        self.labels = []        # (net, x, y, angle)
        self.uuid = uid('file', fname)
        self.sheet_uuid = uid('sheet', fname)  # instance uuid in root
        self.texts = []

    def libsym(self, lib, sym):
        key = f'{lib}:{sym}'
        if key not in self.libsyms:
            s = libs.flat(lib, sym); s = copy.deepcopy(s); s[1] = key
            self.libsyms[key] = s
        return key

    def part(self, ref, lib, sym, value, x, y, conns, rot_=0, fp='', mirror=None,
             dnp=False, extra=None, byname=True, show_val=True, refpos=None, valpos=None):
        key = self.libsym(lib, sym)
        pins = libs.pins(lib, sym)
        x, y = r1(x), r1(y)
        # pin endpoints
        groups = {}
        for num, plist in pins.items():
            p = plist[0]
            py_ = -p['y'] if mirror == 'x' else p['y']
            px_ = -p['x'] if mirror == 'y' else p['x']
            rx, ry = rot(px_, py_, rot_)
            ex, ey = round(x + rx, 2), round(y - ry, 2)
            a = p['a']
            if mirror == 'x': a = (-a) % 360
            if mirror == 'y': a = (180 - a) % 360
            out = (a + 180 + rot_) % 360
            groups.setdefault((ex, ey), []).append((num, out, p))
        used = set()
        for (ex, ey), lst in groups.items():
            nets = {conns.get(n) for n, _, _ in lst} | ({conns.get(p['name']) for _, _, p in lst} if byname else set())
            nets.discard(None)
            if len(nets) > 1: raise ValueError(f'{ref}: stacked pins with different nets {nets}')
            for n, _, p in lst: used.add(n); used.add(p['name'])
            out = lst[0][1]
            if not nets:
                if any(p['type'] != 'no_connect' for _, _, p in lst) or True:
                    self.items.append([Sym('no_connect'), [Sym('at'), ex, ey], [Sym('uuid'), uid(self.fname, ref, ex, ey, 'nc')]])
                continue
            net = nets.pop()
            if net == '-': continue
            self.stub(ex, ey, out, net, ref)
        for k in conns:
            if k not in used: raise ValueError(f'{ref}: unknown pin {k}')
        # bbox for field placement
        xs = [e[0] for e in groups] + [x]; ys = [e[1] for e in groups] + [y]
        props = [('Reference', ref), ('Value', value), ('Footprint', fp), ('Datasheet', '~')]
        if extra: props += list(extra.items())
        node = [Sym('symbol'), [Sym('lib_id'), key], [Sym('at'), x, y, rot_]]
        if mirror: node.append([Sym('mirror'), Sym(mirror)])
        node += [[Sym('unit'), 1], [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')],
                 [Sym('dnp'), Sym('yes' if dnp else 'no')], [Sym('uuid'), uid(self.fname, ref)]]
        bx = max(xs) + 1.27
        w = max(xs) - min(xs); h = max(ys) - min(ys)
        horiz = len(pins) <= 3 and w > h and h < 3
        for i, (k, v) in enumerate(props):
            just = 'right' if rot_ in (180, 270) else 'left'
            if horiz and k in ('Reference', 'Value'):
                px, py = (x, y - 2.54) if k == 'Reference' else (x, y + 2.54)
                just = None
            elif k == 'Reference': px, py = refpos or (bx, y - 1.27)
            elif k == 'Value': px, py = valpos or (bx, y + 1.27)
            else: px, py = x, y
            if k == 'Reference' and refpos: px, py = refpos
            if k == 'Value' and valpos: px, py = valpos
            hide = k not in ('Reference', 'Value') or (k == 'Value' and not show_val) or (k == 'Reference' and ref.startswith('#'))
            node.append([Sym('property'), k, v, [Sym('at'), px, py, FIELD_ANGLE(rot_)], txt(hide=hide, justify=just)])
        for num in pins:
            node.append([Sym('pin'), num, [Sym('uuid'), uid(self.fname, ref, 'pin', num)]])
        node.append([Sym('instances'), [Sym('project'), PROJECT,
                     [Sym('path'), self.inst_path(), [Sym('reference'), ref], [Sym('unit'), 1]]]])
        self.syms.append(node)
        return node

    def inst_path(self):
        return f'/{ROOT_UUID}/{self.sheet_uuid}' if self.page != 1 else f'/{ROOT_UUID}'

    def stub(self, ex, ey, out, net, ref, length=2.54):
        dx, dy = round(math.cos(math.radians(out))), -round(math.sin(math.radians(out)))
        sx, sy = round(ex + dx * length, 2), round(ey + dy * length, 2)
        if length:
            self.items.append([Sym('wire'), [Sym('pts'), [Sym('xy'), ex, ey], [Sym('xy'), sx, sy]],
                               [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('default')]],
                               [Sym('uuid'), uid(self.fname, ref, ex, ey, 'w')]])
        if net in POWER:
            lib, sym, base = POWER[net]
            key = self.libsym(lib, sym)
            r = (out - base) % 360
            n = len([s for s in self.syms if s[1][1] == key])
            pref = f'#PWR{self.page}{len(self.syms):03d}'
            node = [Sym('symbol'), [Sym('lib_id'), key], [Sym('at'), sx, sy, r], [Sym('unit'), 1],
                    [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('no')],
                    [Sym('uuid'), uid(self.fname, ref, ex, ey, 'p')],
                    [Sym('property'), 'Reference', pref, [Sym('at'), sx, sy, 0], txt(hide=True)],
                    [Sym('property'), 'Value', net, [Sym('at'), sx, sy + (3.2 if base == 270 and r == 0 else -3.2 if r == 0 else 0), 0], txt(hide=(r != 0))],
                    [Sym('property'), 'Footprint', '', [Sym('at'), sx, sy, 0], txt(hide=True)],
                    [Sym('property'), 'Datasheet', '', [Sym('at'), sx, sy, 0], txt(hide=True)],
                    [Sym('pin'), '1', [Sym('uuid'), uid(self.fname, ref, ex, ey, 'pp')]],
                    [Sym('instances'), [Sym('project'), PROJECT, [Sym('path'), self.inst_path(), [Sym('reference'), pref], [Sym('unit'), 1]]]]]
            self.syms.append(node)
        else:
            self.labels.append((net, sx, sy, out, uid(self.fname, ref, ex, ey, 'l')))

    def wire(self, pts, tag=''):
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            self.items.append([Sym('wire'), [Sym('pts'), [Sym('xy'), x1, y1], [Sym('xy'), x2, y2]],
                               [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('default')]],
                               [Sym('uuid'), uid(self.fname, 'wire', tag, x1, y1, x2, y2)]])

    def junction(self, x, y):
        self.items.append([Sym('junction'), [Sym('at'), x, y], [Sym('diameter'), 0], [Sym('color'), 0, 0, 0, 0],
                           [Sym('uuid'), uid(self.fname, 'junc', x, y)]])

    def label(self, net, x, y, out, tag=''):
        self.stub(x, y, out, net, 'lbl' + tag, length=0)

    def text(self, s, x, y, size=1.27, bold=False):
        e = [Sym('effects'), [Sym('font'), [Sym('size'), size, size]] + ([Sym('bold')] if bold else []), [Sym('justify'), Sym('left'), Sym('top')]]
        self.texts.append([Sym('text'), s, [Sym('at'), x, y, 0], e, [Sym('uuid'), uid(self.fname, 'txt', s[:40], x, y)]])

    def box(self, x1, y1, x2, y2, title):
        self.texts.append([Sym('rectangle'), [Sym('start'), x1, y1], [Sym('end'), x2, y2],
                           [Sym('stroke'), [Sym('width'), 0.15], [Sym('type'), Sym('dash')]],
                           [Sym('fill'), [Sym('type'), Sym('none')]], [Sym('uuid'), uid(self.fname, 'box', x1, y1)]])
        self.text(title, x1 + 1.27, y1 + 1.27, 2.0, True)

    def render(self, global_nets, sheets=None, rev='0.1', date=''):
        out = [Sym('kicad_sch'), [Sym('version'), 20230121], [Sym('generator'), Sym('eeschema')],
               [Sym('uuid'), ROOT_UUID if self.page == 1 else self.uuid], [Sym('paper'), self.paper],
               [Sym('title_block'), [Sym('title'), self.title], [Sym('date'), date], [Sym('rev'), rev],
                [Sym('company'), 'electroNIX-USB (Z573M)'],
                [Sym('comment'), 1, 'ESP32 rework of TESTA-QUADRA electroNIXclock 3 (PCB-036), USB powered'],
                [Sym('comment'), 2, 'Licensed with the repository; see LICENSE']],
               [Sym('lib_symbols')] + list(self.libsyms.values())]
        out += self.items
        for net, x, y, a, u in self.labels:
            ang = {0: 0, 90: 90, 180: 180, 270: 270}[int(a)]
            just = 'left' if ang in (0, 90) else 'right'
            if net in global_nets:
                out.append([Sym('global_label'), net, [Sym('shape'), Sym('passive')], [Sym('at'), x, y, ang],
                            [Sym('fields_autoplaced')], txt(justify=just), [Sym('uuid'), u],
                            [Sym('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [Sym('at'), x, y, 0], txt(hide=True)]])
            else:
                out.append([Sym('label'), net, [Sym('at'), x, y, ang], [Sym('fields_autoplaced')],
                            txt(justify=just + ' bottom'), [Sym('uuid'), u]])
        out += self.texts
        out += self.syms
        if sheets is not None:
            out += sheets
            out.append([Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]])
        return dump(out) + '\n'

ROOT_UUID = uid('root')
FIELD_ANGLE = lambda r: r % 180
