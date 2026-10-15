#!/usr/bin/env python3
"""Generate the electroNIX-USB (Z573M) KiCad project.

Usage: gen.py OUTDIR
Every connection is either a pin touching a pin, an explicit wire, or a wire
stub ending in a net label / power symbol. Nets that appear on more than one
sheet become global labels automatically.
"""
import sys, os, json, shutil
import libs, kisch
from kisch import Sheet, Sym, uid, txt, dump, r1

HERE = os.path.dirname(os.path.abspath(__file__))
libs.EXTRA['electronix'] = os.path.join(HERE, '..', 'kicad', 'electronix.kicad_sym')

FP_R = 'Resistor_SMD:R_0805_2012Metric'
FP_RHV = 'Resistor_SMD:R_1206_3216Metric'      # 200 V rated, anything on +170V
FP_C = 'Capacitor_SMD:C_0805_2012Metric'
FP_C1206 = 'Capacitor_SMD:C_1206_3216Metric'
FP_C1210 = 'Capacitor_SMD:C_1210_3225Metric'
FP_SOT23 = 'Package_TO_SOT_SMD:SOT-23'
FP_SOD123 = 'Diode_SMD:D_SOD-123'
FP_SMA = 'Diode_SMD:D_SMA'

_cnt = {}
def ref(p):
    _cnt[p] = _cnt.get(p, 0) + 1
    return f'{p}{_cnt[p]}'

# ---- small part helpers ------------------------------------------------------
# Device:R / C / L are vertical at rot 0 (pin 1 on top), horizontal at rot 90
# (pin 1 on the left). Device:D is horizontal at rot 0 (K left, A right).
def R(sh, val, x, y, n1, n2, rot=0, fp=FP_R, **kw):
    return sh.part(ref('R'), 'Device', 'R', val, x, y, {'1': n1, '2': n2}, rot, fp, **kw)
def C(sh, val, x, y, n1, n2, rot=0, fp=FP_C, **kw):
    return sh.part(ref('C'), 'Device', 'C', val, x, y, {'1': n1, '2': n2}, rot, fp, **kw)
def CP(sh, val, x, y, plus, minus, fp, **kw):
    return sh.part(ref('C'), 'Device', 'C_Polarized', val, x, y, {'1': plus, '2': minus}, 0, fp, **kw)
def D(sh, val, x, y, k, a, rot=0, sym='D', fp=FP_SOD123, **kw):
    return sh.part(ref('D'), 'Device', sym, val, x, y, {'1': k, '2': a}, rot, fp, **kw)
def NPN(sh, val, x, y, b, c, e, sym='MMBTA42', **kw):
    return sh.part(ref('Q'), 'Transistor_BJT', sym, val, x, y, {'B': b, 'C': c, 'E': e}, 0, FP_SOT23, **kw)
def flag(sh, net, x, y):
    sh.part(f'#FLG{sh.page}{len(sh.syms):02d}', 'power', 'PWR_FLAG', 'PWR_FLAG', x, y, {'1': net}, 0, '', show_val=False)

def npn_driver(sh, x, y, inp, coll, rb='15k', val='MMBTA42', sym='MMBTA42'):
    """Base resistor touching the base of an NPN switch, emitter to GND."""
    R(sh, rb, x - 8.89, y, inp, '-', rot=90)
    NPN(sh, val, x, y, '-', coll, 'GND', sym=sym)

# =============================================================================
# Sheet 2: USB-C input, protection, 3.3 V regulator, USB-UART
# =============================================================================
def sheet_power():
    sh = Sheet('Power & USB', 'power_usb.kicad_sch', 'electroNIX-USB - USB-C power, 3.3 V, USB-UART', 2)
    sh.box(20, 25, 175, 165, 'USB-C input (5 V only, sink: 5k1 on CC1/CC2)')
    sh.part(ref('J'), 'Connector', 'USB_C_Receptacle_USB2.0_16P', 'USB-C (USB 2.0)', 45, 90,
            {'VBUS': 'VBUS', 'CC1': 'CC1', 'CC2': 'CC2', 'D+': 'USB_DP', 'D-': 'USB_DN',
             'GND': 'GND', 'SHIELD': 'GND'},
            fp='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',
            refpos=(33, 62), valpos=(33, 120))
    R(sh, '5k1', 90, 125, 'CC1', 'GND')
    R(sh, '5k1', 100, 125, 'CC2', 'GND')
    sh.part(ref('F'), 'Device', 'Polyfuse', '1.1 A hold', 115, 50, {'1': 'VBUS', '2': '+5V'}, 90,
            'Fuse:Fuse_1206_3216Metric')
    D(sh, 'SMBJ5.0CA', 140, 60, '+5V', 'GND', rot=270, sym='D_TVS', fp='Diode_SMD:D_SMB')
    C(sh, '22u 10V', 155, 60, '+5V', 'GND', fp=FP_C1206)
    flag(sh, 'VBUS', 100, 40); flag(sh, '+5V', 130, 40); flag(sh, 'GND', 160, 140)
    sh.part(ref('U'), 'Power_Protection', 'USBLC6-2SC6', 'USBLC6-2SC6', 130, 105,
            {'1': 'USB_DP', '6': 'USB_DP', '3': 'USB_DN', '4': 'USB_DN', 'VBUS': 'VBUS', 'GND': 'GND'},
            fp='Package_TO_SOT_SMD:SOT-23-6', refpos=(124, 93), valpos=(124, 118))
    sh.text('VBUS feeds the boost converter and the 3.3 V LDO only.\n'
            'Budget from a 500 mA port: ESP32 ~250 mA avg (500 mA WiFi peaks),\n'
            'HV supply ~150 mA at 4 tubes. A USB-C source gives 1.5-3 A at 5V.', 25, 140)

    sh.box(185, 25, 300, 95, '3.3 V regulator')
    C(sh, '10u', 200, 60, '+5V', 'GND', fp=FP_C1206)
    sh.part(ref('U'), 'Regulator_Linear', 'AMS1117-3.3', 'AMS1117-3.3', 235, 55,
            {'VI': '+5V', 'VO': '+3V3', 'GND': 'GND'}, fp='Package_TO_SOT_SMD:SOT-223-3_TabPin2', refpos=(229, 47), valpos=(240, 66))
    C(sh, '22u', 265, 60, '+3V3', 'GND', fp=FP_C1206)
    C(sh, '100n', 280, 60, '+3V3', 'GND')

    sh.box(185, 105, 300, 165, 'USB-UART (programming + serial log)')
    sh.part(ref('U'), 'Interface_USB', 'CH340C', 'CH340C', 235, 135,
            {'VCC': '+3V3', 'V3': '+3V3', 'GND': 'GND', 'UD+': 'USB_DP', 'UD-': 'USB_DN',
             'TXD': 'U0RXD', 'RXD': 'U0TXD', '~{DTR}': 'DTR', '~{RTS}': 'RTS'},
            fp='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', refpos=(250, 118), valpos=(250, 121))
    C(sh, '100n', 205, 130, '+3V3', 'GND')
    sh.text('CH340C runs from 3V3 (V3 tied to VCC) so TXD/RXD are 3.3 V logic.\n'
            'Net names are from the ESP32 side: U0RXD = ESP32 RXD0 (IO3).', 190, 152)
    return sh

# =============================================================================
# Sheet 3: ESP32, reset/boot, RTC, buzzer, light sensor, button
# =============================================================================
def sheet_mcu():
    sh = Sheet('ESP32', 'mcu.kicad_sch', 'electroNIX-USB - ESP32-WROOM-32E and peripherals', 3)
    io = {'IO13': 'C_0', 'IO14': 'C_1', 'IO21': 'C_2', 'IO22': 'C_3', 'IO23': 'C_4',
          'IO25': 'C_5', 'IO26': 'C_6', 'IO27': 'C_7', 'IO32': 'C_8', 'IO33': 'C_9',
          'IO16': 'W_1', 'IO17': 'W_2', 'IO18': 'W_3', 'IO19': 'W_4',
          'IO4': 'SEC_0', 'IO5': 'SEC_1', 'IO2': 'PWM', 'IO35': 'KOMP_170V', 'IO34': 'JASNOSC',
          'IO12': 'MEL', 'IO15': 'IO15_SDA', 'IO0': 'IO0_SCL', 'SENSOR_VP': 'BTN',
          'RXD0/IO3': 'U0RXD', 'TXD0/IO1': 'U0TXD', 'EN': 'EN', 'VDD': '+3V3', 'GND': 'GND'}
    sh.box(20, 25, 205, 190, 'ESP32 module (GPIO map = firmware BOARD_ELECTRONIX_3, except MEL/RTC)')
    sh.part(ref('U'), 'RF_Module', 'ESP32-WROOM-32E', 'ESP32-WROOM-32E-N4', 110, 105, io,
            fp='RF_Module:ESP32-WROOM-32D', refpos=(100, 66), valpos=(115, 148))
    C(sh, '22u', 40, 55, '+3V3', 'GND', fp=FP_C1206)
    C(sh, '100n', 52, 55, '+3V3', 'GND')
    sh.text('Strapping pins at reset:\n'
            ' IO0  high = run   (4k7 SCL pull-up; BOOT / auto-reset pull it low)\n'
            ' IO2  low/float    (boost gate pull-down on HV sheet)\n'
            ' IO12 low = 3.3 V flash  (100k pull-down on MEL)\n'
            ' IO15 high         (4k7 SDA pull-up)\n'
            ' IO5  SEC_1 neon driver base - default state is harmless', 25, 160)

    sh.box(215, 25, 400, 95, 'Reset, boot and auto-program (DTR/RTS)')
    R(sh, '10k', 230, 50, '+3V3', 'EN')
    C(sh, '1u', 242, 50, 'EN', 'GND')
    sh.part(ref('SW'), 'Switch', 'SW_Push', 'RESET', 262, 45, {'1': 'EN', '2': 'GND'}, fp='Button_Switch_SMD:SW_SPST_PTS645')
    sh.part(ref('SW'), 'Switch', 'SW_Push', 'BOOT', 262, 65, {'1': 'IO0_SCL', '2': 'GND'}, fp='Button_Switch_SMD:SW_SPST_PTS645')
    # classic two-transistor auto-reset
    R(sh, '10k', 301.11, 50, 'DTR', '-', rot=90)
    NPN(sh, 'MMBT3904', 310, 50, '-', 'EN', 'RTS', sym='MMBT3904')
    R(sh, '10k', 341.11, 50, 'RTS', '-', rot=90)
    NPN(sh, 'MMBT3904', 350, 50, '-', 'IO0_SCL', 'DTR', sym='MMBT3904')
    sh.text('DTR RTS | EN IO0\n 1   1  |  1   1\n 0   0  |  1   1\n 1   0  |  0   1\n 0   1  |  1   0', 300, 70)

    sh.box(215, 105, 400, 190, 'Peripherals')
    # RTC
    sh.part(ref('U'), 'Timer_RTC', 'DS3231M', 'DS3231M', 255, 135,
            {'VCC': '+3V3', 'GND': 'GND', 'VBAT': 'VBAT', 'SDA': 'IO15_SDA', 'SCL': 'IO0_SCL'},
            fp='Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm', refpos=(270, 145), valpos=(270, 148))
    C(sh, '100n', 235, 160, '+3V3', 'GND')
    R(sh, '4k7', 225, 125, '+3V3', 'IO15_SDA')
    R(sh, '4k7', 235, 125, '+3V3', 'IO0_SCL')
    sh.part(ref('BT'), 'Device', 'Battery_Cell', 'CR2032', 285, 160, {'+': 'VBAT', '-': 'GND'},
            fp='Battery:BatteryHolder_Keystone_3034_1x20mm')
    sh.text('DS3231M: optional (DNP for NTP-only builds).\nI2C on IO15 (SDA) / IO0 (SCL).', 222, 178)
    # buzzer
    sh.part(ref('LS'), 'Device', 'Buzzer', '5 V magnetic', 320, 125, {'+': '+5V', '-': 'BUZ_N'},
            fp='Buzzer_Beeper:Buzzer_12x9.5RM7.6')
    D(sh, '1N4148W', 330, 125, '+5V', 'BUZ_N', rot=270)
    npn_driver(sh, 325, 145, 'MEL', 'BUZ_N', rb='1k', val='BC847', sym='BC847')
    R(sh, '100k', 305, 155, 'MEL', 'GND')
    # light sensor
    R(sh, '1M', 355, 125, '+3V3', 'JASNOSC')
    sh.part(ref('D'), 'Device', 'D_Photo', 'BPW34 / HPDB3J', 360, 145, {'K': 'JASNOSC', 'A': 'GND'}, 270,
            'OptoDevice:Osram_DIL2_4.3x4.65mm_P5.08mm')
    C(sh, '100n', 372, 145, 'JASNOSC', 'GND')
    # user button
    R(sh, '10k', 385, 125, '+3V3', 'BTN')
    sh.part(ref('SW'), 'Switch', 'SW_Push', 'SET', 385, 160, {'1': 'BTN', '2': 'GND'}, 90,
            'Button_Switch_THT:SW_PUSH_6mm')
    C(sh, '100n', 395, 145, 'BTN', 'GND')
    return sh

# =============================================================================
# Sheet 4: 5 V boost + Cockcroft-Walton ladder to 170 V, feedback
# =============================================================================
def sheet_hv():
    sh = Sheet('HV supply', 'hv_supply.kicad_sch', 'electroNIX-USB - 170 V supply (boost + multiplier)', 4)
    sh.box(20, 25, 150, 120, 'Boost switch (as PCB-036)')
    C(sh, '22u 10V', 35, 60, '+5V', 'GND', fp=FP_C1206)
    C(sh, '100n', 47, 60, '+5V', 'GND')
    sh.part(ref('L'), 'Device', 'L', '33u WE 7447715330', 70, 50, {'1': '+5V', '2': 'HV_SW'}, 0,
            'Inductor_SMD:L_Wuerth_WE-PD-Typ-LS')
    sh.part(ref('Q'), 'Device', 'Q_NMOS_GDS', 'IRLR3110ZPBF', 100, 80, {'G': '-', 'D': 'HV_SW', 'S': 'GND'}, 0,
            'Package_TO_SOT_SMD:TO-252-2')
    R(sh, '10R', 91.11, 80, 'PWM', '-', rot=90)
    R(sh, '10k', 85, 95, 'PWM', 'GND')
    sh.text('IO2 drives the logic-level FET directly, 32 kHz,\nduty clamped to ~41 % by firmware (HV_DUTY_MAX).\n'
            '10k keeps the gate (and IO2) low during boot.', 25, 105)

    sh.box(160, 25, 400, 120, 'Cockcroft-Walton multiplier, 7 x 10MQ100N, 7 x 1u/100V (as PCB-036)')
    # DC column (top) and AC column (bottom), drawn like the original
    top = ['+170V', 'CW_T3', 'CW_T2', 'CW_T1', 'GND']
    bot = ['CW_B3', 'CW_B2', 'CW_B1', 'HV_SW']
    x0, yt, yb = 185, 50, 95
    for i in range(4):
        C(sh, '1u 100V', x0 + 15 + i * 50, yt, top[i], top[i + 1], rot=90, fp=FP_C1210)
    for i in range(3):
        C(sh, '1u 100V', x0 + 40 + i * 50, yb, bot[i], bot[i + 1], rot=90, fp=FP_C1210)
    # diodes, alternate direction: HV_SW -> T1 -> B1 -> T2 -> B2 -> T3 -> B3 -> +170V
    chain = [('HV_SW', 'CW_T1'), ('CW_T1', 'CW_B1'), ('CW_B1', 'CW_T2'), ('CW_T2', 'CW_B2'),
             ('CW_B2', 'CW_T3'), ('CW_T3', 'CW_B3'), ('CW_B3', '+170V')]
    for i, (a, k) in enumerate(reversed(chain)):
        x = x0 + i * 25
        up = (i % 2 == 0)            # cathode on the top row
        D(sh, '10MQ100N', x, (yt + yb) / 2, k, a, rot=270 if up else 90, sym='D_Schottky', fp=FP_SMA)
    sh.text('Each stage adds one boost peak (~45 V at 170 V out); no part sees more than ~100 V.', 165, 110)

    sh.box(20, 130, 400, 200, 'Output, feedback (KOMP_170V) and ADC clamp')
    CP(sh, '2u2 250V', 45, 165, '+170V', 'GND', 'Capacitor_THT:CP_Radial_D6.3mm_P2.50mm')
    flag(sh, '+170V', 60, 150)
    R(sh, '430k', 100, 160, '+170V', 'KOMP_170V', fp=FP_RHV)
    R(sh, '6k2', 100, 180, 'KOMP_170V', 'GND')
    C(sh, '100n', 115, 175, 'KOMP_170V', 'GND')
    sh.part(ref('D'), 'Diode', 'BAT54S', 'BAT54S', 145, 175, {'A': 'GND', 'K': '+3V3', 'COM': 'KOMP_170V'}, 0, FP_SOT23)
    sh.text('Divider ratio (430k+6k2)/6k2 = 70.35 = HV_DIV_RATIO in display_testa.cpp.\n'
            '170 V -> 2.42 V at IO35. BAT54S clamps to 3V3 (the original clamped to 5 V).\n'
            'Use 1 % parts; 430k in 1206 for working voltage.', 170, 160)
    return sh

# =============================================================================
# Sheet 5: tubes, anode/cathode drivers, colon neons
# =============================================================================
def sheet_display():
    sh = Sheet('Display', 'display.kicad_sch', 'electroNIX-USB - 4 x Z573M, multiplexed', 5, paper='A2')
    sh.box(20, 25, 400, 105, 'Anode switches (one per tube, MMBTA42 level shift + MMBTA92 high side)')
    for n in range(4):
        X, Y = r1(50 + n * 90), r1(80)
        R(sh, '15k', X - 8.89, Y, f'W_{n+1}', '-', rot=90)
        NPN(sh, 'MMBTA42', X, Y, '-', '-', 'GND')
        R(sh, '430k', X + 2.54, Y - 8.89, '-', '-', fp=FP_RHV)
        R(sh, '100k', X + 2.54, Y - 16.51, '+170V', '-', fp=FP_RHV)
        sh.part(ref('Q'), 'Transistor_BJT', 'MMBTA92', 'MMBTA92', X + 7.62, Y - 12.7,
                {'B': '-', 'E': '+170V', 'C': '-'}, 0, FP_SOT23, mirror='x')
        R(sh, '10k', X + 10.16, Y - 3.81, '-', f'A_{n+1}', fp=FP_RHV)
        sh.junction(round(X + 2.54, 2), round(Y - 12.7, 2))
    sh.text('W_n high -> tube n anode at +170V through 10k. Anode current ~2 mA peak.', 25, 98)

    sh.box(20, 115, 400, 210, 'Tubes (RFT Z573M, B13D base, pin 7 at front)')
    for n in range(4):
        conns = {'13': f'A_{n+1}', '12': 'K_0', '1': 'K_1', '2': 'K_2', '3': 'K_3', '5': 'K_4',
                 '6': 'K_5', '7': 'K_6', '8': 'K_7', '9': 'K_8', '11': 'K_9'}
        sh.part(ref('N'), 'electronix', 'Z573M', 'Z573M', 60 + n * 90, 160, conns, 0, '',
                refpos=(60 + n * 90 - 16, 151), valpos=(60 + n * 90 + 4, 151), byname=False)
    sh.text('Pin 4 = internal connection (leave open). Pin 10 = PR sign (unused).\n'
            'Pinout from tube-tester.com Z573M page; check against a real tube before layout.', 25, 195)

    sh.box(20, 220, 400, 300, 'Cathode switches (MMBTA42, shared by all tubes)')
    for k in range(10):
        X, Y = r1(45 + k * 36), r1(270)
        npn_driver(sh, X, Y, f'C_{k}', f'K_{k}')

    sh.box(410, 25, 575, 140, 'Colon neons (SEC_0 upper / SEC_1 lower)')
    for i in range(2):
        X, Y = r1(450 + i * 60), r1(110)
        R(sh, '100k', X - 8.89, Y, f'SEC_{i}', '-', rot=90)
        NPN(sh, 'MMBTA42', X, Y, '-', '-', 'GND')
        sh.part(ref('NE'), 'Device', 'Lamp_Neon', 'NE-2 / INS-1', X + 2.54, Y - 10.16, {'1': '-', '2': '-'}, 0, '')
        R(sh, '150k', X + 2.54, Y - 19.05, '+170V', '-', fp=FP_RHV)
    sh.text('Original Z573M kit fits one neon (SEC_0). Fit the second for a two-dot colon;\n'
            'firmware drives them independently. 150k: ~0.6 mA at 170 V.', 415, 125)

    sh.box(410, 150, 575, 300, 'Off-cathode clamp (anti-ghosting, as PCB-036)')
    xs = [r1(425 + k * 13.97) for k in range(10)]
    yd = r1(200)
    for k, x in enumerate(xs):
        D(sh, '1N4148W', x, yd, '-', f'K_{k}', rot=90)
    yk = round(yd + 3.81, 2)
    sh.wire([(x, yk) for x in xs] + [(round(xs[-1] + 10.16, 2), yk)], 'kbus')
    for x in xs[1:]: sh.junction(x, yk)
    sh.label('KBIAS', round(xs[-1] + 10.16, 2), yk, 0)
    R(sh, '430k', 450, 250, '+170V', 'KBIAS', fp=FP_RHV)
    R(sh, '100k', 470, 250, 'KBIAS', 'GND')
    C(sh, '2u2 50V', 490, 250, 'KBIAS', 'GND', fp=FP_C1206)
    sh.text('KBIAS = 170 V x 100k/530k = ~32 V. Off cathodes are held at or below it,\n'
            'so the lit anode cannot glow them and the MMBTA42s stay well under VCEO.', 415, 280)
    return sh

# =============================================================================
def root(sheets):
    sh = Sheet('Root', 'electroNIX-USB.kicad_sch', 'electroNIX-USB (Z573M) - overview', 1)
    blocks = []
    for i, s in enumerate(sheets):
        x, y, w, h = 30 + (i % 2) * 120, 50 + (i // 2) * 60, 90, 40
        blocks.append([Sym('sheet'), [Sym('at'), x, y], [Sym('size'), w, h], [Sym('fields_autoplaced')],
                       [Sym('stroke'), [Sym('width'), 0.1524], [Sym('type'), Sym('solid')]],
                       [Sym('fill'), [Sym('color'), 0, 0, 0, 0.0]], [Sym('uuid'), s.sheet_uuid],
                       [Sym('property'), 'Sheetname', s.name, [Sym('at'), x, y - 0.7, 0], txt(justify='left bottom')],
                       [Sym('property'), 'Sheetfile', s.fname, [Sym('at'), x, y + h + 0.6, 0], txt(justify='left top')],
                       [Sym('instances'), [Sym('project'), kisch.PROJECT, [Sym('path'), f'/{kisch.ROOT_UUID}', [Sym('page'), str(s.page)]]]]])
    sh.text('electroNIX-USB: USB-C powered ESP32 nixie clock, 4 x Z573M\n\n'
            'Electrical design follows TESTA-QUADRA electroNIXclock 3 (PCB-036, 2013),\n'
            'the micro-USB powered board: 5 V boost + 7-diode multiplier to 170 V,\n'
            'MMBTA42/MMBTA92 discrete tube drivers, neon colon, buzzer, light sensor.\n\n'
            'Changes from PCB-036:\n'
            ' - ATmega16 replaced by ESP32-WROOM-32E with the firmware\'s electroNIX 3 GPIO map\n'
            ' - USB-C (5k1 sink) + polyfuse + TVS + USBLC6, CH340C for programming\n'
            ' - DS3231M + CR2032 instead of the 32 kHz crystal and supercap\n'
            ' - HV feedback clamp to 3V3, base resistors resized for 3.3 V drive\n'
            ' - buzzer moved IO0 -> IO12 (IO0 pull-down through the buzzer base forced download mode)\n'
            ' - two independent colon neons (SEC_0, SEC_1)', 30, 180, 1.5)
    return sh, blocks

def main(out):
    os.makedirs(out, exist_ok=True)
    sheets = [sheet_power(), sheet_mcu(), sheet_hv(), sheet_display()]
    for s in sheets:  # mounting holes on the root later
        pass
    use = {}
    for s in sheets:
        for net, *_ in s.labels: use.setdefault(net, set()).add(s.fname)
    glob = {n for n, f in use.items() if len(f) > 1}
    single = sorted(n for n, f in use.items() if len(f) == 1)
    rt, blocks = root(sheets)
    for i in range(4):
        rt.part(ref('H'), 'Mechanical', 'MountingHole', 'M3', 290 + i * 15, 60, {}, 0, 'MountingHole:MountingHole_3.2mm_M3')
    date = '2026-10-15'
    open(os.path.join(out, rt.fname), 'w').write(rt.render(glob, blocks, date=date))
    for s in sheets:
        open(os.path.join(out, s.fname), 'w').write(s.render(glob, date=date))
    if os.path.abspath(libs.EXTRA['electronix']) != os.path.abspath(os.path.join(out, 'electronix.kicad_sym')):
        shutil.copy(libs.EXTRA['electronix'], os.path.join(out, 'electronix.kicad_sym'))
    open(os.path.join(out, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (version 7)\n  (lib (name "electronix")(type "KiCad")(uri "${KIPRJMOD}/electronix.kicad_sym")(options "")(descr "electroNIX project symbols"))\n)\n')
    pro = {"meta": {"filename": "electroNIX-USB.kicad_pro", "version": 1},
           "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
           "sheets": [[kisch.ROOT_UUID, ""]] + [[s.sheet_uuid, s.name] for s in sheets],
           "boards": [], "text_variables": {}}
    json.dump(pro, open(os.path.join(out, 'electroNIX-USB.kicad_pro'), 'w'), indent=2)
    print('global nets:', sorted(glob))
    print('single-sheet label nets:', single)

if __name__ == '__main__':
    main(sys.argv[1])
