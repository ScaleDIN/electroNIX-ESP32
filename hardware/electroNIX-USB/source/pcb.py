#!/usr/bin/env python3
"""Build the electroNIX-USB board from the schematic netlist.

  python3 source/pcb.py kicad            # 4 tubes
  python3 source/pcb.py kicad-6tube      # 6 tubes

Steps: export the netlist (kicad-cli), place every footprint (tubes, neons and
the light sensor on top, everything else on the bottom), export Specctra DSN,
autoroute with Freerouting, read the session back, add GND pours, fill, run
DRC. Writes <dir>/electroNIX-USB.kicad_pcb and <dir>/drc.rpt.

Needs KiCad 7+ python (pcbnew), Java 25 and the Freerouting 2.x jar
(FREEROUTING_JAR, default ./freerouting.jar).
"""
import json, math, os, subprocess, sys, xml.etree.ElementTree as ET
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse

FM, MM = pcbnew.FromMM, pcbnew.ToMM
STOCK = '/usr/share/kicad/footprints'
NAME = 'electroNIX-USB'

# ---------------------------------------------------------------- netlist
class Netlist:
    def __init__(self, path):
        r = ET.parse(path).getroot()
        self.comps = {}
        for c in r.iter('comp'):
            sp = c.find('sheetpath')
            self.comps[c.get('ref')] = dict(value=c.findtext('value'), fp=c.findtext('footprint'),
                                            sheet=sp.get('names') if sp is not None else '/',
                                            path=(sp.get('tstamps') if sp is not None else '/') + c.findtext('tstamps'))
        self.nets, self.pinnet = {}, {}
        for n in r.iter('net'):
            name = n.get('name')
            for x in n.iter('node'):
                self.nets.setdefault(name, []).append((x.get('ref'), x.get('pin')))
                self.pinnet[(x.get('ref'), x.get('pin'))] = name

    def net(self, short):
        """Full net name from its short name (label name without sheet path)."""
        for n in self.nets:
            if n == short or n.split('/')[-1] == short: return n
        raise KeyError(short)

    def on(self, short, prefix=None, pin=None):
        refs = [r for r, p in self.nets[self.net(short)]
                if (prefix is None or (r.startswith(prefix) and r[len(prefix):].isdigit()))
                and (pin is None or p == pin)]
        return sorted(set(refs), key=lambda s: int(''.join(ch for ch in s if ch.isdigit())))

    def one(self, short, prefix=None, pin=None):
        r = self.on(short, prefix, pin)
        assert len(r) == 1, (short, prefix, pin, r)
        return r[0]

    def pnet(self, ref, pin): return self.pinnet[(ref, pin)].split('/')[-1]

    def pick(self, taken, sheet, value, net=None):
        """First unplaced part on `sheet` with `value` (and on `net`)."""
        for r in sorted(self.comps, key=lambda s: (s.rstrip('0123456789'), int(''.join(ch for ch in s if ch.isdigit()) or 0))):
            c = self.comps[r]
            if r in taken or sheet not in c['sheet'] or c['value'] != value: continue
            if net and r not in self.on(net): continue
            return r
        raise KeyError((sheet, value, net))

# ---------------------------------------------------------------- placement
def placement(nl, tubes):
    """Return {ref: (x, y, rot, side)}; side 'F' or 'B'. Origin is the top-left
    board corner, +y toward the FRONT edge (the side the digits face).
    Bottom-side coordinates are as seen from the top."""
    W, H = (102.0, 66.0) if tubes == 4 else (150.0, 66.0)
    mid, TY = W / 2, 35.0
    if tubes == 4: tx = [mid - 37, mid - 15, mid + 15, mid + 37]; colons = [mid]
    else: tx = [mid - 63, mid - 41, mid - 11, mid + 11, mid + 41, mid + 63]; colons = [mid - 26, mid + 26]
    P = {}
    def put(ref, x, y, rot=0, side='B'):
        assert ref not in P, ref
        P[ref] = (round(x, 3), round(y, 3), rot, side)
    pk = lambda sheet, value, net=None: nl.pick(P, sheet, value, net)
    val = lambda r: nl.comps[r]['value']

    # ---------------- top side: tubes, colon neons, light sensor, holes
    for i, x in enumerate(tx):
        put(nl.one(f'A_{i + 1}', 'N'), x, TY, 0, 'F')
    if tubes == 4: stacks = [(colons[0], [nl.one('NEK_0', 'NE'), nl.one('NEK_1', 'NE')])]
    else: stacks = [(colons[0], nl.on('NEK_0', 'NE')), (colons[1], nl.on('NEK_1', 'NE'))]
    for cx, refs in stacks:                # upper dot behind, lower dot in front
        for j, r in enumerate(refs):
            put(r, cx, TY - 2.5 + j * 5.0, 0, 'F')
    put(nl.one('JASNOSC', 'D'), colons[0] - 2.54, 25.5, 0, 'F')     # BPW34 behind the colon
    for r, (x, y) in zip(sorted(r for r in nl.comps if r.startswith('H')),
                         [(4, 4), (W - 4, 4), (4, H - 4), (W - 4, H - 4)]):
        put(r, x, y, 0, 'F')

    # ---------------- back band, left: boost converter (compact switching loop)
    # +5V enters on the left (input caps, L1 pin 1); the switch node (L1 pin 2,
    # FET drain tab) faces right, straight into the ladder's first diode.
    L = nl.one('HV_SW', 'L'); put(L, 14.5, 8.0, 180)
    Q = nl.one('HV_SW', 'Q'); put(Q, 15.5, 21.0, 180)
    put(pk('HV', '22u 10V'), 3.6, 11.2, 90); put(pk('HV', '100n', '+5V'), 3.6, 15.4, 90)
    Rg = nl.one('PWM', 'R')                   # 10R series gate resistor
    put(Rg, 6.6, 19.0, 90); put([r for r in nl.on(nl.pnet(Q, '1'), 'R') if r != Rg][0], 6.6, 23.6, 90)
    # multiplier ladder right beside the switch: diode column + capacitor column,
    # in chain order from the switch node (top) to +170 V (bottom)
    cw_d = {nl.pnet(r, '2'): r for r in nl.comps if r.startswith('D') and val(r) == '10MQ100N'}   # anode net -> diode
    chain, node = [], 'HV_SW'
    while node in cw_d:
        d = cw_d[node]; chain.append(d); node = nl.pnet(d, '1')
    for i, d in enumerate(chain): put(d, 26.0, 2.2 + i * 3.7, 0)
    caps = [r for r in nl.comps if r.startswith('C') and val(r) == '2u2 100V']
    order = ['HV_SW', 'CW_T1', 'CW_B1', 'CW_T2', 'CW_B2', 'CW_T3', 'CW_B3', '+170V']
    rank = lambda c: min(order.index(nl.pnet(c, p)) if nl.pnet(c, p) in order else 9 for p in ('1', '2'))
    for i, c in enumerate(sorted(caps, key=lambda c: (rank(c), c))): put(c, 33.4, 2.2 + i * 3.7, 0)

    # ---------------- back band, centre: USB-C, protection, LDO
    put(nl.one('CC1', 'J'), mid, 3.675, 180)
    put(nl.one('CC1', 'R'), mid - 6.0, 12.0, 90); put(nl.one('CC2', 'R'), mid + 6.0, 12.0, 90)
    put([r for r in nl.on('USB_DP', 'U') if val(r).startswith('USBLC6')][0], mid, 12.0, 0)
    put(nl.one('VBUS', 'F'), mid - 9.5, 5.5, 90)
    put(pk('Power', '22u 10V'), mid - 12.2, 5.5, 90)
    put([r for r in nl.on('+5V', 'D') if 'SMBJ' in val(r)][0], mid - 10.8, 11.5, 0)
    put(pk('Power', '10u'), mid - 11.0, 20.0, 90)
    put([r for r in nl.on('+3V3', 'U') if 'AMS1117' in val(r)][0], mid - 4.5, 20.0, 0)
    put(pk('Power', '22u'), mid + 2.3, 20.0, 90); put(pk('Power', '100n', '+3V3'), mid + 5.2, 20.0, 90)
    # light sensor pull-up + filter beside the BPW34 pads
    put(pk('ESP32', '1M'), colons[0] - 7.0, 25.8, 0); put(pk('ESP32', '100n', 'JASNOSC'), colons[0] + 7.0, 25.8, 0)

    # ---------------- back band, right: CH340C, auto-reset, ESP32
    EX = W - 18.5
    U3 = [r for r in nl.on('USB_DP', 'U') if val(r) == 'CH340C'][0]; put(U3, EX - 19.5, 9.0, 90)
    put(pk('Power', '100n', '+3V3'), EX - 19.5, 15.0, 0)
    sx = EX - 11.6                         # between CH340C (TXD/RXD side) and the module's UART/IO0 pins
    q1 = nl.one('EN', 'Q', '3'); q2 = nl.one('IO0', 'Q', '3')
    put(q1, sx, 3.2, 0); put(nl.one(nl.pnet(q1, '1'), 'R'), sx, 6.9, 0)
    put(q2, sx, 10.4, 0); put(nl.one(nl.pnet(q2, '1'), 'R'), sx, 14.1, 0)
    put(pk('ESP32', '10k', 'IO0'), sx, 23.0, 0)                 # IO0 pull-up, next to pin 25
    U4 = nl.one('EN', 'U'); put(U4, EX, 15.79, 0)
    # strip between the module's right-hand pins (3V3, EN, IO34, IO35) and the board edge
    ca, cb = EX + 10.9, EX + 14.5
    put(pk('ESP32', '100n', '+3V3'), ca, 9.4, 90); put(pk('ESP32', '22u'), cb, 10.2, 90)       # 3V3, pin 2
    put(pk('ESP32', '1u'), ca, 13.0, 90); put(pk('ESP32', '10k', 'EN'), cb, 14.4, 90)          # EN RC, pin 3
    Rtop = [r for r in nl.on('KOMP_170V', 'R') if val(r) == '430k'][0]                           # HV sense at IO35
    put(nl.one('KOMP_170V', 'C'), ca, 16.6, 90)
    put([r for r in nl.on('KOMP_170V', 'R') if r != Rtop][0], ca, 20.2, 90)
    put(nl.on('KOMP_170V', 'D')[0], cb, 18.6, 90)
    put(Rtop, cb, 23.6, 90)

    # ---------------- colon gap(s): neon drivers
    for i in range(2):
        q = nl.one(f'NEK_{i}', 'Q'); rb = nl.one(nl.pnet(q, '1'), 'R')
        rss = [nl.one(nl.pnet(ne, '2'), 'R') for ne in nl.on(f'NEK_{i}', 'NE')]
        if tubes == 4: cx, side = colons[0], (-1 if i == 0 else 1)
        else: cx, side = colons[i], -1
        x = cx + side * 5.3 if tubes == 4 else cx - 5.3
        put(q, x, 30.0, 0); put(rb, x, 34.4, 90)
        for j, rs in enumerate(rss):
            xx = x if tubes == 4 else cx + 5.3
            put(rs, xx, 39.4 if tubes == 4 else 30.5 + j * 6.0, 90)

    # ---------------- front band: output cap + KBIAS at the left end
    Cout = [r for r in nl.on('+170V', 'C') if '250V' in val(r)][0]; put(Cout, 6.6, 47.5, 0)
    kr = nl.on('KBIAS', 'R'); kr430 = [r for r in kr if val(r) == '430k'][0]; kr100 = [r for r in kr if r != kr430][0]
    put(kr430, 4.8, 52.3, 0); put(kr100, 10.6, 55.5, 90)
    # 4 x 470n in series, KBIAS -> GND, as a short row
    c, node, string = nl.one('KBIAS', 'C'), 'KBIAS', []
    while True:
        string.append(c); pin = '2' if nl.pnet(c, '1') == node else '1'; node = nl.pnet(c, pin)
        if node == 'GND': break
        c = [x for x in nl.on(node, 'C') if x not in string][0]
    for i, c in enumerate(string): put(c, 1.8 + i * 2.2, 55.6, 90)

    # ---------------- front band: cathode switches (R | Q over clamp D)
    x0, x1 = 14.0, W - 8.0
    for k in range(10):
        x = x0 + k * (x1 - x0) / 9
        q = nl.one(f'K_{k}', 'Q'); put(q, x, 46.0, 0)
        put(nl.one(nl.pnet(q, '1'), 'R'), x - 3.1, 46.0, 90)
        put(nl.one(f'K_{k}', 'D'), x, 50.6, 90)

    # ---------------- front band: anode switches, one cluster under each tube
    for i in range(tubes):
        rb = nl.one(f'W_{i + 1}', 'R'); qlo = nl.one(nl.pnet(rb, '2'), 'Q')
        r430 = nl.one(nl.pnet(qlo, '3'), 'R'); qhi = nl.on(nl.pnet(r430, '1'), 'Q')[0]
        r100 = [r for r in nl.on(nl.pnet(qhi, '1'), 'R') if r != r430][0]
        ra = nl.one(f'A_{i + 1}', 'R')
        cx = min(max(tx[i], 19.5), W - 13.0)
        put(rb, cx - 5.5, 56.6, 0); put(qlo, cx - 1.0, 56.6, 0); put(qhi, cx + 3.6, 56.6, 0)
        put(r430, cx - 4.6, 61.2, 0); put(r100, cx + 0.4, 61.2, 0); put(ra, cx + 4.4, 61.2, 0)

    rest = [r for r in nl.comps if r not in P]
    return P, (W, H), dict(tx=tx, TY=TY, colons=colons, esp=(EX, 15.79), mid=mid), rest

# ---------------------------------------------------------------- board
def fp_load(spec, kdir):
    lib, name = spec.split(':')
    path = os.path.join(kdir, lib + '.pretty') if lib == 'electronix' else os.path.join(STOCK, lib + '.pretty')
    f = pcbnew.FootprintLoad(path, name)
    assert f is not None, spec
    return f

X0, Y0 = 100.0, 100.0          # board origin on the KiCad page

def hv_nets(nl):
    """Nets that can sit near +170 V: get the HV netclass (0.4 mm clearance)."""
    hv = {'+170V', 'HV_SW', 'KBIAS'} | {n.split('/')[-1] for n in nl.nets
                                       if n.split('/')[-1].startswith(('CW_', 'A_', 'NEK_'))}
    for r, c in nl.comps.items():
        if c['value'] == 'MMBTA92':
            hv |= {nl.pnet(r, '1'), nl.pnet(r, '3')}
        if c['value'] == '430k':
            hv |= {nl.pnet(r, '1'), nl.pnet(r, '2')}
        if r.startswith('NE'):
            hv |= {nl.pnet(r, '1'), nl.pnet(r, '2')}
    return hv - {'GND', 'KOMP_170V'}

POWER_NETS = {'GND', '+5V', '+3V3', 'VBUS'}

def netclass(name, clear, track, via=0.6, drill=0.3):
    nc = pcbnew.NETCLASS(name)
    nc.SetClearance(FM(clear)); nc.SetTrackWidth(FM(track))
    nc.SetViaDiameter(FM(via)); nc.SetViaDrill(FM(drill))
    return nc

CLASSES = {'Default': (0.2, 0.25), 'Power': (0.2, 0.5), 'HV': (0.4, 0.3)}

def outline(board, W, H, r=3.0):
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(FM(X0 + a[0]), FM(Y0 + a[1]))); s.SetEnd(pcbnew.VECTOR2I(FM(X0 + b[0]), FM(Y0 + b[1])))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FM(0.1)); board.Add(s)
    def arc(c, a0):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
        pt = lambda a: pcbnew.VECTOR2I(FM(X0 + c[0] + r * math.cos(math.radians(a))), FM(Y0 + c[1] - r * math.sin(math.radians(a))))
        s.SetArcGeometry(pt(a0), pt(a0 + 45), pt(a0 + 90)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FM(0.1)); board.Add(s)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc((W - r, r), 0); arc((r, r), 90); arc((r, H - r), 180); arc((W - r, H - r), 270)

def zone(board, layers, pts, net=None, rule=False, prio=0, name=''):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls)
    o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(FM(X0 + x), FM(Y0 + y))
    if rule:
        z.SetIsRuleArea(True); z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        z.SetZoneName(name)
    else:
        z.SetNet(net); z.SetLocalClearance(FM(0.3)); z.SetMinThickness(FM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FM(0.4)); z.SetThermalReliefSpokeWidth(FM(0.4))
        z.SetAssignedPriority(prio); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z

def build(kdir, tubes):
    netxml = os.path.join(kdir, 'netlist.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', netxml,
                    os.path.join(kdir, NAME + '.kicad_sch')], check=True, capture_output=True)
    nl = Netlist(netxml)
    P, (W, H), geo, rest = placement(nl, tubes)
    if rest: print('UNPLACED:', rest)
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FM(1.6))
    ns = ds.m_NetSettings
    for n, (c, t) in CLASSES.items():
        if n == 'Default':
            d = ns.m_DefaultNetClass; d.SetClearance(FM(c)); d.SetTrackWidth(FM(t)); d.SetViaDiameter(FM(0.6)); d.SetViaDrill(FM(0.3))
        else:
            ns.m_NetClasses[n] = netclass(n, c, t)
    hv = hv_nets(nl)
    nets = {}
    for name in nl.nets:
        if name.startswith('unconnected-'): continue
        ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); nets[name] = ni
        short = name.split('/')[-1]
        if short in hv: ni.SetNetClass(ns.m_NetClasses['HV'])
        elif short in POWER_NETS: ni.SetNetClass(ns.m_NetClasses['Power'])
        else: ni.SetNetClass(ns.m_DefaultNetClass)
    for ref, c in nl.comps.items():
        f = fp_load(c['fp'], kdir)
        f.SetReference(ref); f.SetValue(c['value'])
        f.SetPath(pcbnew.KIID_PATH(c['path']))
        x, y, rot, side = P[ref]
        f.SetPosition(pcbnew.VECTOR2I(FM(X0 + x), FM(Y0 + y)))
        board.Add(f)
        if side == 'B': f.Flip(f.GetPosition(), True)
        # KiCad stores a left-right flip as mirror-Y + 180 deg; undo the 180 so
        # bottom parts are a pure X mirror of their top-side orientation.
        f.SetOrientationDegrees((rot + 180) % 360 if side == 'B' else rot)
        f.Reference().SetTextSize(pcbnew.VECTOR2I(FM(0.8), FM(0.8))); f.Reference().SetTextThickness(FM(0.12))
        for p in f.Pads():
            n = nl.pinnet.get((ref, p.GetNumber()))
            if n and n in nets: p.SetNet(nets[n])
    outline(board, W, H)
    ex, ey = geo['esp']
    zone(board, [pcbnew.F_Cu, pcbnew.B_Cu], [(ex - 10, 0), (ex + 10, 0), (ex + 10, ey - 9.3), (ex - 10, ey - 9.3)],
         rule=True, name='ESP32 antenna keepout')
    return board, nl, P, (W, H), geo

def courtyard_overlaps(board):
    fps = list(board.GetFootprints()); out = []
    polys = {}
    for f in fps:
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = f.GetCourtyard(lay)
            if c.OutlineCount() and f.GetFPID().GetLibItemName() != 'ESP32-WROOM-32D': polys.setdefault(f.GetReference(), []).append((lay, c))
    refs = list(polys)
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            for la, a in polys[refs[i]]:
                for lb, b in polys[refs[j]]:
                    if la != lb: continue
                    t = a.Collide(b.Outline(0)) if False else None
                    ia = a.BBox(); ib = b.BBox()
                    if ia.Intersects(ib):
                        inter = pcbnew.SHAPE_POLY_SET(a); inter.BooleanIntersection(b, pcbnew.SHAPE_POLY_SET.PM_FAST)
                        if inter.OutlineCount() and inter.Area() > FM(0.05) * FM(1):
                            out.append((refs[i], refs[j], 'F' if la == pcbnew.F_CrtYd else 'B'))
    # bottom courtyards against through-hole pads of top-side parts
    for f in fps:
        if f.GetLayer() != pcbnew.F_Cu: continue
        for p in f.Pads():
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_PTH: continue
            for ref, lst in polys.items():
                if ref == f.GetReference(): continue
                for lay, c in lst:
                    if lay == pcbnew.B_CrtYd and c.Collide(p.GetPosition(), int(p.GetSize().x / 2 + FM(0.2))):
                        out.append((ref, f.GetReference() + '.' + p.GetNumber(), 'THT'))
    # ESP32 module body against everything else on the bottom
    esp = [f for f in fps if f.GetFPID().GetLibItemName() == 'ESP32-WROOM-32D'][0]
    eb = esp.GetBoundingBox(False, False)
    body = pcbnew.BOX2I(pcbnew.VECTOR2I(esp.GetPosition().x - FM(9.05), esp.GetPosition().y - FM(15.79)),
                        pcbnew.VECTOR2I(FM(18.1), FM(25.6)))
    for ref, lst in polys.items():
        for lay, c in lst:
            if lay == pcbnew.B_CrtYd and c.BBox().Intersects(body):
                out.append((ref, esp.GetReference(), 'ESP body'))
    return out

# ---------------------------------------------------------------- routing
FR_JAR = os.environ.get('FREEROUTING_JAR', os.path.join(os.getcwd(), 'freerouting.jar'))
JAVA = os.environ.get('FREEROUTING_JAVA', 'java')

def autoroute(board, workdir, passes=100, timeout=3000):
    workdir = os.path.abspath(workdir)
    dsn, ses = os.path.join(workdir, 'board.dsn'), os.path.join(workdir, 'board.ses')
    if os.path.exists(ses): os.remove(ses)
    assert pcbnew.ExportSpecctraDSN(board, dsn)
    cmd = [JAVA, '-jar', FR_JAR, '-de', dsn, '-do', ses, '-mp', str(passes), '--gui.enabled=false']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=workdir)
    log = (r.stdout or '') + (r.stderr or '')
    open(os.path.join(workdir, 'freerouting.log'), 'w').write(log)
    assert os.path.exists(ses), log[-3000:]
    return ses

def import_ses(board, ses):
    """Read a Specctra session back into the board (tracks + vias)."""
    t = parse(open(ses).read())
    def f(x, tag): return [e for e in x if isinstance(e, list) and e and e[0] == tag]
    routes = f(t, 'routes')[0]
    res = f(routes, 'resolution')[0]          # (resolution um 10)
    scale = {'um': 1e-3, 'mm': 1.0, 'mil': 0.0254, 'inch': 25.4}[str(res[1])] / float(res[2])
    lib = f(routes, 'library_out')
    padstacks = {}
    for ps in (f(lib[0], 'padstack') if lib else []):
        shp = f(ps, 'shape')[0][1]            # (circle F.Cu 600)
        padstacks[ps[1]] = float(shp[2]) * scale
    nets = {n.GetNetname(): n for n in board.GetNetsByName().values()}
    netinfo = board.GetNetInfo()
    layers = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
    P = lambda x, y: pcbnew.VECTOR2I(FM(float(x) * scale), FM(-float(y) * scale))
    ntr = nvia = 0
    for net in f(f(routes, 'network_out')[0], 'net'):
        ni = netinfo.GetNetItem(net[1])
        for w in f(net, 'wire'):
            path = f(w, 'path')[0]
            lay, width, xy = layers[path[1]], float(path[2]) * scale, path[3:]
            pts = [P(xy[i], xy[i + 1]) for i in range(0, len(xy) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                tr = pcbnew.PCB_TRACK(board); tr.SetStart(a); tr.SetEnd(b); tr.SetWidth(FM(width))
                tr.SetLayer(lay); tr.SetNet(ni); board.Add(tr); ntr += 1
        for v in f(net, 'via'):
            via = pcbnew.PCB_VIA(board); via.SetPosition(P(v[2], v[3]))
            dia = padstacks.get(v[1], 0.6)
            via.SetWidth(FM(dia)); via.SetDrill(FM(0.3)); via.SetNet(ni)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(via); nvia += 1
    return ntr, nvia

def pours(board, W, H, inset=0.4):
    gnd = board.GetNetInfo().GetNetItem('GND')
    pts = [(inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)]
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(board, [lay], pts, net=gnd)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

def write_project(kdir, nl):
    """Put the netclasses into the .kicad_pro so KiCad's GUI uses them too."""
    pro = os.path.join(kdir, NAME + '.kicad_pro')
    d = json.load(open(pro)) if os.path.exists(pro) else {}
    def cls(name, clear, track):
        return {'name': name, 'clearance': clear, 'track_width': track, 'via_diameter': 0.6, 'via_drill': 0.3,
                'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25,
                'diff_pair_width': 0.2, 'line_style': 0, 'bus_width': 12, 'wire_width': 6,
                'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)'}
    hv = sorted(hv_nets(nl))
    pats = [{'netclass': 'HV', 'pattern': n if n.startswith('Net-') else '*' + n} for n in hv]
    pats += [{'netclass': 'Power', 'pattern': n} for n in sorted(POWER_NETS)]
    d['net_settings'] = {'classes': [cls(n, c, t) for n, (c, t) in CLASSES.items()],
                         'meta': {'version': 3}, 'net_colors': None,
                         'netclass_assignments': None, 'netclass_patterns': pats}
    json.dump(d, open(pro, 'w'), indent=2)

if __name__ == '__main__':
    kdir = sys.argv[1]
    tubes = 6 if '6tube' in os.path.basename(os.path.abspath(kdir)) else 4
    pcbpath = os.path.join(kdir, NAME + '.kicad_pcb')
    if '--route-only' not in sys.argv:
        board, nl, P, (W, H), geo = build(kdir, tubes)
        ov = courtyard_overlaps(board)
        print('courtyard overlaps:', len(ov)); [print('  ', o) for o in ov]
        board.Save(pcbpath)
        write_project(kdir, nl)        # after Save: saving rewrites the .kicad_pro
        if '--place-only' in sys.argv: sys.exit(0)
        # route in a fresh process so the project's netclass patterns are read
        sys.exit(subprocess.call([sys.executable, __file__, kdir, '--route-only']))
    nl = Netlist(os.path.join(kdir, 'netlist.xml'))
    board = pcbnew.LoadBoard(pcbpath)
    W, H = (102.0, 66.0) if tubes == 4 else (150.0, 66.0)
    cls = {}
    for n, ni in board.GetNetsByName().items():
        cls.setdefault(ni.GetNetClassName(), []).append(str(n))
    print('netclasses:', {k: len(v) for k, v in cls.items()})
    assert 'HV' in cls, 'netclass patterns not applied'
    work = os.path.join(kdir, '.route'); os.makedirs(work, exist_ok=True)
    ses = autoroute(board, work)
    print('tracks/vias:', import_ses(board, ses))
    pours(board, W, H)
    board.Save(pcbpath)
    write_project(kdir, nl)
    pcbnew.WriteDRCReport(board, os.path.join(kdir, 'drc.rpt'), pcbnew.EDA_UNITS_MILLIMETRES, True)
    print(open(os.path.join(kdir, 'drc.rpt')).read()[-1500:])
