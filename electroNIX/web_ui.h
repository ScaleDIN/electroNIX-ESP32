// ============================================================================
//  web_ui.h — the single HTML string served at "/"
//
//  Kept in its own header so design changes are a search-and-edit in one file
//  and the C++ that serves it stays readable. The page is deliberately one
//  static resource: it fetches JSON from /api/config and /api/status on load
//  and every second thereafter, so this file never changes at runtime and
//  every user-facing string that isn't a live value is here.
//
//  Sections controlled by BOARD_HAS_* flags are wrapped in <div class="cap
//  cap-hv"> etc.; the loader adds a class to <body> for each capability the
//  running board declares, and CSS then hides irrelevant sections. That way
//  the same HTML works for every board and only rendering differs.
// ============================================================================
#pragma once

static const char WEB_UI_HTML[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>electroNIX</title>
<style>
:root{--bg:#0d0b09;--panel:#17130f;--line:#2b2118;--amber:#ffab40;--glow:#ff7a1a;
--dim:#8a7a68;--txt:#e8ddd0;--ok:#7fc97f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.5 Georgia,'Times New Roman',serif}
.wrap{max-width:700px;margin:0 auto;padding:18px}
h1{font-size:15px;letter-spacing:.35em;text-transform:uppercase;color:var(--dim);
font-weight:400;text-align:center;margin:8px 0 2px}
.sub{text-align:center;color:var(--dim);font-size:12px;margin-bottom:14px}

/* --- tube preview --- */
.tubes{display:flex;justify-content:center;align-items:center;gap:8px;
background:radial-gradient(ellipse at 50% 120%,#1c130a 0%,#0d0b09 70%);
border:1px solid var(--line);border-radius:14px;padding:22px 8px;margin-bottom:16px}
.tube{width:52px;height:88px;border-radius:10px 10px 14px 14px;
border:1px solid #3a2c1c;background:linear-gradient(180deg,#141008,#0a0806);
display:flex;align-items:center;justify-content:center;
box-shadow:inset 0 0 18px rgba(255,122,26,.07)}
.tube.small{width:38px;height:64px}
.tube span{font-family:'Courier New',monospace;font-size:50px;color:var(--amber);
text-shadow:0 0 6px var(--glow),0 0 18px var(--glow),0 0 40px rgba(255,122,26,.6);
transition:opacity .35s}
.tube.small span{font-size:34px}
.tube.off span{opacity:.06;text-shadow:none}
.colon{display:flex;flex-direction:column;gap:14px;align-items:center}
body.cap-ws2812 .colon{gap:7px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--amber);
box-shadow:0 0 8px var(--glow),0 0 18px var(--glow);transition:opacity .3s,background .3s,box-shadow .3s}
.dot.off{opacity:.08 !important;box-shadow:none !important}

/* --- status grid --- */
.stat{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));
gap:4px 14px;color:var(--dim);font-size:12px;margin:-4px 0 12px;
font-variant-numeric:tabular-nums}
.stat div{display:flex;justify-content:space-between;gap:8px;
white-space:nowrap;overflow:hidden;border-bottom:1px dotted #1e170f;padding-bottom:2px}
.stat b{color:var(--txt);font-weight:400;text-align:right}

/* --- form --- */
fieldset{border:1px solid var(--line);border-radius:10px;background:var(--panel);
margin:0 0 14px;padding:12px 14px}
legend{padding:0 8px;color:var(--amber);font-size:12px;letter-spacing:.25em;
text-transform:uppercase}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px;
padding:7px 0;border-bottom:1px dotted #241c14;flex-wrap:nowrap}
.row label{flex:1 1 auto;min-width:0}
.row>input,.row>select,.row>span,.row>div{flex-shrink:0}
.row:last-child{border-bottom:0}
small{color:var(--dim);display:block}
input,select{background:#0c0a08;color:var(--txt);border:1px solid var(--line);
border-radius:6px;padding:6px 8px;font:inherit;font-size:14px}
input[type=range]{accent-color:var(--amber);width:150px}
input[type=checkbox]{accent-color:var(--amber);width:18px;height:18px}
input[type=color]{width:56px;height:32px;padding:2px;cursor:pointer}
input[type=text],input[type=password]{width:200px}
input.num{width:70px}
.trims{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.trims label{font-size:11px;color:var(--dim);text-align:center}
.trims input{width:56px}
button{background:#241a10;border:1px solid #3d2d1b;color:var(--amber);
border-radius:8px;padding:8px 16px;font:inherit;cursor:pointer;letter-spacing:.08em}
button:hover{background:#2e2113}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin:2px 0 18px;justify-content:center}
#msg{text-align:center;min-height:20px;color:var(--ok);font-size:13px}

/* --- capability hiding ---
   The body gets a class per BOARD_HAS_* flag on load. Any element wearing a
   cap-* class only shows when the matching body class is present. */
body:not(.cap-hv)      .cap-hv,
body:not(.cap-sensor)  .cap-sensor,
body:not(.cap-buzzer)  .cap-buzzer,
body:not(.cap-led)     .cap-led,
body:not(.cap-ws2812)  .cap-ws2812,
body:not(.cap-neon1opt) .cap-neon1opt,
body:not(.cap-sec)     .cap-sec,
body:not(.cap-rtc)     .cap-rtc { display:none }
/* Neon colon brightness is only meaningful on boards that don't have
   addressable WS2812 LEDs — those boards already have their own per-colour
   brightness control in the Colon LEDs fieldset. */
body.cap-ws2812 .cap-neon-colon { display:none }
</style></head><body><div class="wrap">
<h1 id="boardname">electroNIX</h1><div class="sub">nixie clock &middot; esp32</div>

<div class="tubes">
 <div class="tube" id="t0"><span>0</span></div>
 <div class="tube" id="t1"><span>0</span></div>
 <div class="colon" id="colonCol">
   <div class="dot cap-ws2812" id="ca0"></div>
   <div class="dot" id="c0"></div>
   <div class="dot cap-ws2812" id="ca1"></div>
   <div class="dot" id="c0b"></div>
   <div class="dot cap-ws2812" id="ca2"></div>
 </div>
 <div class="tube" id="t2"><span>0</span></div>
 <div class="tube" id="t3"><span>0</span></div>
 <div class="colon cap-sec"><div class="dot" id="c1"></div><div class="dot" id="c1b"></div></div>
 <div class="tube small cap-sec" id="t4"><span>0</span></div>
 <div class="tube small cap-sec" id="t5"><span>0</span></div>
</div>

<div class="stat">
 <div>date <b id="sdate">&ndash;</b></div>
 <div class="cap-hv">HV <b id="shv">&ndash;</b></div>
 <div class="cap-hv">duty <b id="sduty">&ndash;</b></div>
 <div>bright <b id="sbr">&ndash;</b></div>
 <div class="cap-sensor">light <b id="slight">&ndash;</b></div>
 <div class="cap-sensor">sensor noise <b id="slightpp">&ndash;</b></div>
 <div>wifi <b id="swifi">&ndash;</b></div>
 <div>time <b id="sntp">&ndash;</b></div>
 <div class="cap-rtc">RTC <b id="srtc">&ndash;</b></div>
 <div>core 0 net <b id="scpu0">&ndash;</b></div>
 <div>core 1 disp <b id="scpu1">&ndash;</b></div>
 <div>mux <b id="smux">&ndash;</b></div>
 <div>mux min <b id="smuxmin">&ndash;</b></div>
 <div class="cap-hv">hv cuts <b id="shvcuts">&ndash;</b></div>
 <div>heap <b id="sheap">&ndash;</b></div>
</div>
<div id="msg"></div>

<div class="btns">
 <button onclick="save()">Save settings</button>
 <button onclick="act('toggle')">Tubes on/off</button>
 <button onclick="act('poison')">Run cleaning cycle</button>
 <button onclick="setTime()">Set time from this device</button>
 <button class="cap-buzzer" onclick="act('beep')">Test buzzer</button>
 <button onclick="act('restart')">Restart</button>
 <button onclick="expCfg()">Back up settings</button>
 <button onclick="$('impf').click()">Restore</button>
 <input type="file" id="impf" accept="application/json" style="display:none">
</div>

<fieldset><legend>Display</legend>
 <div class="row"><label>24-hour clock</label><input type="checkbox" id="use24"></div>
 <div class="row"><label>Leading zero</label><input type="checkbox" id="leadZero"></div>
 <div class="row cap-sec"><label>Seconds tubes</label><input type="checkbox" id="secEn"></div>
 <div class="row cap-sec"><label>Seconds behaviour</label><select id="secMode">
   <option value="0">Count every second</option>
   <option value="1">Keep dark</option>
   <option value="2">Show briefly each minute</option></select></div>
 <div class="row cap-neon1opt"><label>Second colon neon fitted<small>SEC_1 -- only if you've wired the bodge, see WIRING.md</small></label>
   <input type="checkbox" id="neon1Fitted"></div>
 <div class="row"><label>Colon behaviour</label><select id="colon">
   <option value="0">Off</option><option value="1">Steady</option>
   <option value="2">Blink</option><option value="3">Alternate</option>
   <option value="4">Breathe</option>
   <option value="5">Centre glow (WS2812)</option></select></div>
 <div class="row"><label>Digit cross-fade<small id="fadenote">0 = instant</small></label>
   <span><input type="range" id="fadeMs" min="0" max="2000" step="50">
   <b id="fadeMsV"></b> ms</span></div>
 <div class="row"><label>Show date<small>every N minutes, 0 = never</small></label>
   <input class="num" type="number" id="dateEvery" min="0" max="60"></div>
 <div class="row"><label>Date duration<small>display time in seconds</small></label>
   <span><input class="num" type="number" id="dateDur" min="1" max="30"> s</span></div>
 <div class="row"><label>Date format</label><select id="dateFmt"></select></div>
</fieldset>

<fieldset><legend>Brightness</legend>
 <div class="row cap-sensor"><label>Auto (light sensor)</label>
   <input type="checkbox" id="brAuto"></div>
 <div class="row"><label>Manual level</label>
   <span><input type="range" id="brMan" min="5" max="100"><b id="brManV"></b>%</span></div>
 <div class="row cap-neon-colon"><label>Colon brightness<small>neon lamp level, 0 = off</small></label>
   <span><input type="range" id="colonBrNeon" min="0" max="100"><b id="colonBrNeonV"></b>%</span></div>
 <div class="row cap-sensor"><label>Auto range min/max %</label>
   <span><input class="num" type="number" id="brMin" min="5" max="100">
   <input class="num" type="number" id="brMax" min="5" max="100"></span></div>
 <div class="row cap-sensor"><label>Response speed<small>how quickly it follows room lighting</small></label>
   <span><input type="range" id="brSpeed" min="0" max="100">
   <b id="brSpeedV"></b></span></div>
 <div class="row cap-sensor"><label style="align-self:flex-start">Preview<small>step response for the current setting</small></label>
   <canvas id="brPrev" width="260" height="70"
     style="background:#0a0806;border:1px solid var(--line);border-radius:6px"></canvas></div>
 <div class="row cap-sensor"><label>Sensor calibration<small>reading in mV when dark / when lit</small></label>
   <span><input class="num" type="number" id="lightDark" min="0" max="3300">
   <input class="num" type="number" id="lightBright" min="0" max="3300"></span></div>
 <div class="row cap-sensor"><label>Calibration span<small>under ~300 mV makes the sensor noisy</small></label>
   <span style="color:var(--dim);font-size:12px" id="cspan">&ndash;</span></div>
 <div class="row cap-sensor"><label>Capture now<small>captured values are stored at once</small></label>
   <span class="trims">
   <button onclick="act('calbdark')">use current as dark</button>
   <button onclick="act('calbright')">as bright</button></span></div>
 <div class="row"><label>Per-tube trim %</label>
   <span class="trims" id="trimbox"></span></div>
 <div class="row"><label>Night mode</label><input type="checkbox" id="nightEn"></div>
 <div class="row"><label>Turn off colon at night</label><input type="checkbox" id="colonNightOff"></div>
 <div class="row"><label>Night from / to</label>
   <span><input type="time" id="nightS"> <input type="time" id="nightE"></span></div>
 <div class="row"><label>Night brightness<small>0 = tubes off</small></label>
   <span><input type="range" id="nightBr" min="0" max="100"><b id="nightBrV"></b>%</span></div>
</fieldset>

<fieldset class="cap-led"><legend>Under-tube backlight</legend>
 <div class="row"><label>LEDs on</label><input type="checkbox" id="ledEn"></div>
 <div class="row"><label>Level</label>
   <span><input type="range" id="ledBr" min="0" max="100"><b id="ledBrV"></b>%</span></div>
 <div class="row"><label>Follow night mode</label><input type="checkbox" id="ledNight"></div>
</fieldset>

<fieldset class="cap-ws2812"><legend>Colon LEDs</legend>
 <div class="row"><label>Colour<small>same for all five LEDs</small></label>
   <input type="color" id="colonHex"></div>
 <div class="row"><label>Brightness</label>
   <span><input type="range" id="colonBr" min="0" max="100"><b id="colonBrV"></b>%</span></div>
 <div class="row"><label>Centre glow outer LEDs<small>dot brightness in Centre glow mode</small></label>
   <span><input type="range" id="colonOuterPct" min="0" max="100"><b id="colonOuterPctV"></b>%</span></div>
 <div class="row"><label>Spare LEDs<small>the three that aren't colon dots</small></label>
   <select id="colonAccent">
   <option value="0">Off</option>
   <option value="1">Dim glow</option>
   <option value="2">Match the colon</option></select></div>
 <div class="row"><label>Dim glow / breathe floor<small>ambient level for dim glow; minimum brightness at the bottom of breathe</small></label>
   <span><input type="range" id="accentDim" min="0" max="50"><b id="accentDimV"></b>%</span></div>
 <div class="row"><label>Fade curve<small>brightness shape for blink &amp; alternate transitions</small></label>
   <select id="fadeCurve">
   <option value="0">Gamma (x&sup3;) &mdash; slow start, quick finish</option>
   <option value="1">Square root (&radic;x) &mdash; quick start, slow finish</option>
   <option value="2">Smoothstep &mdash; symmetric S-curve</option></select></div>
 <div class="row"><label>Min brightness floor<small>0 = fully dark between blinks; raise to keep the colon always glowing</small></label>
   <span><input type="range" id="fadeCurveFloor" min="0" max="100"><b id="fadeCurveFloorV"></b>%</span></div>
 <div class="row"><label>Reverse LED order<small>if the wrong end of the strip lights up</small></label>
   <input type="checkbox" id="colonReversed"></div>
 <div class="row"><small>Five LEDs in a line between digits 2 and 3; the 2nd and
  4th are the colon dots, so <b>alternate</b> steps the upper dot then the lower 
  (note: "Match the colon" has no effect when Alternate is selected).
  The bottommost LED blinks on its own if the clock's time isn't trusted (no
  NTP or browser sync yet) &mdash; that's independent of the settings above.</small></div>
</fieldset>

<fieldset><legend>Time &amp; NTP</legend>
 <div class="row"><label>NTP server 1</label><input type="text" id="ntp1"></div>
 <div class="row"><label>NTP server 2</label><input type="text" id="ntp2"></div>
 <div class="row"><label>Timezone</label><select id="tzsel">
   <option value="<+08>-8">Singapore / SGT</option>
   <option value="CET-1CEST,M3.5.0,M10.5.0/3">Central Europe</option>
   <option value="GMT0BST,M3.5.0/1,M10.5.0">UK / Ireland</option>
   <option value="EST5EDT,M3.2.0,M11.1.0">US Eastern</option>
   <option value="CST6CDT,M3.2.0,M11.1.0">US Central</option>
   <option value="MST7MDT,M3.2.0,M11.1.0">US Mountain</option>
   <option value="PST8PDT,M3.2.0,M11.1.0">US Pacific</option>
   <option value="JST-9">Japan</option>
   <option value="AEST-10AEDT,M10.1.0,M4.1.0/3">Sydney</option>
   <option value="IST-5:30">India</option>
   <option value="UTC0">UTC</option>
   <option value="custom">Custom&hellip;</option></select></div>
 <div class="row"><label>POSIX TZ string</label><input type="text" id="tz"></div>
 <div class="row"><label>Check NTP every<small>minutes; 60 is plenty</small></label>
   <span><input class="num" type="number" id="ntpEvery" min="5" max="1440"> min
   <button onclick="act('resync')">sync now</button></span></div>
 <div class="row"><label>Correct smoothly<small>slew instead of jumping the seconds</small></label>
   <input type="checkbox" id="ntpSmooth"></div>
</fieldset>

<fieldset><legend>Maintenance</legend>
 <div class="row"><label>Pin check &mdash; digits<small>hold one digit on every tube for 15 s</small></label>
   <span class="trims" id="testbox"></span></div>
 <div class="row"><label>Pin check &mdash; tubes<small>light one position at a time</small></label>
   <span class="trims" id="tubebox"></span></div>
 <div class="row"><label>Cleaning cycle<small>every N minutes, 0 = off</small></label>
   <input class="num" type="number" id="poisonMin" min="0" max="120"></div>
 <div class="row"><label>Cycle length<small>seconds the digits keep moving -- "try it" previews this and the style below, even unsaved</small></label>
   <span><input class="num" type="number" id="poisonSec" min="1" max="60"> s
   <button onclick="act('poison&sec='+$('poisonSec').value+'&style='+$('poisonStyle').value)">try it</button></span></div>
 <div class="row"><label>Cycle style</label><select id="poisonStyle">
   <option value="0">Slot machine (spin and settle)</option>
   <option value="1">Every digit in turn (thorough)</option></select></div>
 <div class="row cap-buzzer"><label>Hourly chime</label><input type="checkbox" id="chime"></div>
 <div class="row cap-hv"><label>HV target (V)</label>
   <input class="num" type="number" id="hvSet" min="150" max="180"></div>
 <div class="row cap-hv"><label>HV sense trim<small>measured &divide; reported</small></label>
   <input class="num" type="number" id="hvTrim" min="0.80" max="1.20" step="0.01"></div>
</fieldset>

<fieldset><legend>Wiring order</legend>
 <div class="row"><small>Use <b>Pin check</b> above to ask for a digit or a
  tube position, then type what actually showed. If a field already reads
  back what you'd expect after saving — <code>0,1,2&hellip;9</code> for
  digits, <code>1,2,3&hellip;</code> for tube positions — that part is
  correct.</small></div>
 <div class="row"><label>Digits shown for 0&ndash;9</label>
   <input type="text" id="seenDigits" style="width:230px"></div>
 <div class="row"><label>Tube positions<small>numbered 1&ndash;N like the buttons above, left to right</small></label>
   <input type="text" id="seenTubes" style="width:230px"></div>
 <div class="row"><label>Quick fixes</label><span class="trims">
   <button onclick="rot('seenDigits',1)">digits +1</button>
   <button onclick="rot('seenDigits',-1)">digits &minus;1</button>
   <button onclick="rev('seenTubes')">reverse tubes</button></span></div>
 <div class="row"><label>Stored mapping</label>
   <span style="color:var(--dim);font-size:12px" id="curOrder">&ndash;</span></div>
</fieldset>

<fieldset><legend>WiFi</legend>
 <div class="row"><label>Network name (SSID)</label>
   <div style="display:flex;gap:4px">
     <input type="text" id="ssid" style="width:140px">
     <button type="button" onclick="scanWifi()" id="scanBtn" style="padding:4px 8px">Scan</button>
   </div>
 </div>
 <div class="row" id="wifi-select-row" style="display:none">
   <label>Found networks</label>
   <select id="wifi-select" style="width:140px" onchange="$('ssid').value=this.value"></select>
 </div>
 <div class="row"><label>Password</label><input type="password" id="pass"
   placeholder="(unchanged)"></div>
 <div class="row"><label>Hostname<small id="hostHint">http://&lt;name&gt;.local</small></label>
   <input type="text" id="host"></div>
 <div class="row"><label>Portal window at boot<small>seconds the setup AP opens before connecting; 0 = immediate</small></label>
   <span><input class="num" type="number" id="portalSec" min="0" max="300"> s</span></div>
 <div class="row"><label>Go offline<small>clears credentials and restarts; use the setup AP (192.168.4.1) to reconfigure</small></label>
   <button onclick="clearWifi()">Clear WiFi</button></div>
</fieldset>

<script>
const $=id=>document.getElementById(id);
let NT=4;
const KB=['use24','leadZero','brAuto','nightEn','colonNightOff','chime','secEn','ledEn','ledNight','ntpSmooth','colonReversed','neon1Fitted'];
const KV=['colon','fadeMs','dateEvery','dateFmt','dateDur','brMan','brMin','brMax','nightBr',
'poisonMin','hvSet','hvTrim','ntp1','ntp2','tz','ssid','host','secMode','ledBr',
'lightDark','lightBright','ntpEvery','poisonSec','poisonStyle','brSpeed','colonBr',
'colonAccent','accentDim','portalSec','colonBrNeon','colonOuterPct',
'fadeCurve','fadeCurveFloor'];
const KT=['nightS','nightE'];

const m2t=m=>String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0');
const t2m=t=>{const[a,b]=t.split(':');return(+a)*60+(+b)};
const hex2=n=>n.toString(16).padStart(2,'0');

// -- brightness slider maths (must match the firmware) --
function tauFromSpeed(v){return 0.5*Math.pow(60,(100-v)/100)}
function drawPreview(){
 const c=$('brPrev'),g=c.getContext('2d'),W=c.width,H=c.height;
 const tau=tauFromSpeed(+$('brSpeed').value);
 g.clearRect(0,0,W,H);
 const T=Math.max(2,tau*4);
 g.strokeStyle='#241c14';g.lineWidth=1;
 g.beginPath();g.moveTo((tau/T)*W,0);g.lineTo((tau/T)*W,H);g.stroke();
 g.fillStyle='#8a7a68';g.font='10px Georgia';
 g.fillText(tau.toFixed(1)+' s',(tau/T)*W+4,12);
 g.fillText('window '+T.toFixed(0)+' s',6,H-4);
 g.strokeStyle='#ffab40';g.lineWidth=2;g.beginPath();
 let y=0,dt=T/W,slew=100/tau;
 for(let x=0;x<W;x++){
  const step=Math.max(-slew*dt,Math.min(slew*dt,(100-y)*(1-Math.exp(-dt/tau))));
  y+=step;
  const py=H-4-(y/100)*(H-10);
  x?g.lineTo(x,py):g.moveTo(x,py);
 }
 g.stroke();
}
function mirror(){
 ['fadeMs','brMan','nightBr','ledBr','colonBr','accentDim','colonBrNeon','colonOuterPct','fadeCurveFloor'].forEach(k=>{
   const e=$(k+'V'); if(e) e.textContent=$(k).value;
 });
 const t=tauFromSpeed(+$('brSpeed').value);
 $('brSpeedV').textContent=t<1?t.toFixed(1)+' s':Math.round(t)+' s';
 drawPreview();
 // Reflect colon colour on the preview dots -- but only on boards that have
 // addressable WS2812 LEDs where the colour is actually user-settable. On
 // TESTA boards the colon is a neon lamp (always amber) and colonHex lives in
 // a hidden section; its DOM default of #000000 would paint all dots black.
 const c=$('colonHex')?$('colonHex').value:null;
 if(c && document.body.classList.contains('cap-ws2812')) document.querySelectorAll('.dot').forEach(d=>{
   if(!d.classList.contains('off')){d.style.background=c;d.style.boxShadow='0 0 8px '+c+',0 0 18px '+c}
 });
 const acc=$('colonAccent')?+$('colonAccent').value:0;
 const dimVal=$('accentDim')?+$('accentDim').value:15;
 ['ca0','ca1','ca2'].forEach(id=>{const e=$(id);if(e)e.style.opacity=acc?(acc==1?(dimVal/100):1):0.06});
}
['fadeMs','brMan','nightBr','ledBr','brSpeed','colonBr','colonHex','colonAccent','accentDim','colonBrNeon','colonOuterPct','fadeCurve','fadeCurveFloor'].forEach(
 k=>$(k)&&$(k).addEventListener('input',mirror));

// -- Wiring-order helpers --
// Tube POSITIONS are shown and typed as 1..N to match the "1 H, 2 H, 3 M..."
// pin-check buttons below, but the firmware's anodeOrder[] array (and the
// permutation maths in clock_core.cpp) is 0-indexed like any C array. These
// two convert at the display boundary; nothing server-side changes. Digit
// VALUES (seenDigits, 0-9) are left alone -- those already match what's
// printed on the pin-check buttons above them.
const toDisplay1 = csv => csv.split(',').map(x => (+x.trim()) + 1).join(',');
const toWire0     = csv => csv.split(',').map(x => (+x.trim()) - 1).join(',');

function rot(id,n){
 const a=$(id).value.split(',').map(x=>+x.trim());
 $(id).value=a.map((_,i)=>a[(i+n+a.length*2)%a.length]).join(',');
}
function rev(id){$(id).value=$(id).value.split(',').reverse().join(',')}

// -- Pin-check buttons --
function mkbtn(box,label,fn){
 const t=document.createElement('button');t.textContent=label;
 t.style.padding='4px 9px';t.onclick=fn;box.appendChild(t);
}
function buildTest(){
 const b=$('testbox');b.innerHTML='';
 for(let i=0;i<10;i++)mkbtn(b,i,()=>act('test&d='+i));
 mkbtn(b,'exit',()=>act('testoff'));
 const u=$('tubebox');u.innerHTML='';
 const nm=NT>=6?['H','H','M','M','S','S']:['H','H','M','M'];
 for(let i=1;i<=NT;i++)mkbtn(u,i+' '+nm[i-1],()=>act('tube&d='+i));
 mkbtn(u,'exit',()=>act('testoff'));
}
function buildTrims(n){
 $('trimbox').innerHTML='';
 for(let i=0;i<n;i++){
  const w=document.createElement('label');
  w.innerHTML=(i+1)+'<br><input class="num" type="number" id="trim'+i+'" min="20" max="100">';
  $('trimbox').appendChild(w);
 }
}

// -- Load/save --
async function load(){
 const c=await(await fetch('/api/config')).json();
 NT=c.tubes; buildTrims(NT); buildTest();
 (c.caps||[]).forEach(cap=>document.body.classList.add('cap-'+cap));
 $('boardname').textContent=c.board;
 document.title=c.board;

// to make the seconds the same size on the electronix 4+S
if (c.board === 'electroNIX 4+S') {
  $('t4').classList.remove('small');
  $('t5').classList.remove('small');
}

 // Populate date format options BEFORE setting KV values
 const hasSec6=document.body.classList.contains('cap-sec');
 const dtSel=$('dateFmt');
 if(dtSel){
  dtSel.innerHTML='';
  const opts = hasSec6 ? 
    [['0','DD\u00b7MM\u00b7YY'],['1','MM\u00b7DD\u00b7YY'],['2','YY\u00b7MM\u00b7DD']] :
    [['0','DD\u00b7MM'],['1','MM\u00b7DD']];
  opts.forEach(([v,t])=>dtSel.add(new Option(t,v)));
 }

 KB.forEach(k=>$(k)&&($(k).checked=!!c[k]));
 KV.forEach(k=>{if($(k)&&(k in c))$(k).value=c[k]});
 if(c.effHost && $('hostHint')) $('hostHint').textContent = 'http://' + c.effHost + '.local';
 KT.forEach(k=>$(k)&&($(k).value=m2t(c[k])));
 c.trim.slice(0,NT).forEach((v,i)=>{const e=$('trim'+i);if(e)e.value=v});

 const o=[...$('tzsel').options].find(o=>o.value==c.tz);
 $('tzsel').value=o?o.value:'custom';
 const idn=n=>[...Array(n).keys()].join(',');
 $('seenDigits').value=idn(10); $('seenTubes').value=toDisplay1(idn(NT));
 $('curOrder').textContent='digits '+c.cathOrder+'   tubes '+toDisplay1(c.anodeOrder);
 const sp=Math.abs(c.lightDark-c.lightBright);
 if($('cspan')){$('cspan').textContent=sp+' mV'+(sp<300?'  \u2014 very narrow':'');
  $('cspan').style.color=sp<300?'#ff7a1a':''}
 if(c.hasWs2812)$('colonHex').value='#'+hex2(c.colonR)+hex2(c.colonG)+hex2(c.colonB);
 if(NT>=6)$('fadenote').textContent='0 = instant; capped at 700 ms while seconds run';
 mirror();
}
$('tzsel').onchange=()=>{if($('tzsel').value!='custom')$('tz').value=$('tzsel').value};

async function save(){
 const p=new URLSearchParams();
 KB.forEach(k=>$(k)&&p.set(k,$(k).checked?1:0));
 KV.forEach(k=>$(k)&&p.set(k,$(k).value));
 KT.forEach(k=>$(k)&&p.set(k,t2m($(k).value)));
 for(let i=0;i<NT;i++){const e=$('trim'+i);if(e)p.set('trim'+i,e.value)}
 p.set('seenDigits',$('seenDigits').value); p.set('seenTubes',toWire0($('seenTubes').value));
 if($('colonHex').value){
  const h=$('colonHex').value;
  p.set('colonR',parseInt(h.substr(1,2),16));
  p.set('colonG',parseInt(h.substr(3,2),16));
  p.set('colonB',parseInt(h.substr(5,2),16));
 }
 if($('pass').value)p.set('pass',$('pass').value);
 const r=await fetch('/api/config',{method:'POST',body:p});
 $('msg').textContent=await r.text();
 $('pass').value=''; load();
 setTimeout(()=>$('msg').textContent='',4000);
}

async function act(d){
 const r=await fetch('/api/action?do='+d,{method:'POST'});
 $('msg').textContent=await r.text();
 if(d=='calbdark'||d=='calbright'){
  const c=await(await fetch('/api/config')).json();
  $('lightDark').value=c.lightDark; $('lightBright').value=c.lightBright;
 }
 setTimeout(()=>$('msg').textContent='',3000);
}

async function clearWifi(){
 if(!confirm('Delete saved WiFi credentials?\n\nThe clock will restart in offline (AP-only) mode.\nReconnect to the setup AP and open 192.168.4.1 to configure WiFi again.'))return;
 const r=await fetch('/api/action?do=clearwifi',{method:'POST'});
 $('msg').textContent=await r.text();
 setTimeout(()=>$('msg').textContent='',8000);
}

async function scanWifi() {
  $('scanBtn').textContent = '...';
  try {
    const r = await fetch('/api/wifi');
    if (r.status === 202) {
      setTimeout(scanWifi, 500);
      return;
    }
    const nets = await r.json();
    const sel = $('wifi-select');
    sel.innerHTML = '<option value="">Select a network...</option>' + 
                    nets.map(n => '<option value="'+n+'">'+n+'</option>').join('');
    $('wifi-select-row').style.display = 'flex';
    $('scanBtn').textContent = 'Scan';
  } catch(e) {
    $('scanBtn').textContent = 'Err';
  }
}

// -- Time + settings backup --
let autoSynced=false;
async function setTime(auto){
 const r=await fetch('/api/time?epoch='+(Date.now()/1000),{method:'POST'});
 const m=await r.text();
 if(!auto){$('msg').textContent=m;setTimeout(()=>$('msg').textContent='',3000)}
}
async function expCfg(){
 const c=await(await fetch('/api/config')).text();
 const a=document.createElement('a');
 a.href=URL.createObjectURL(new Blob([c],{type:'application/json'}));
 a.download='electronix-settings.json';a.click();
 $('msg').textContent='Settings downloaded.';
 setTimeout(()=>$('msg').textContent='',3000);
}
$('impf').onchange=async e=>{
 const f=e.target.files[0];if(!f)return;
 try{
  const c=JSON.parse(await f.text());
  const p=new URLSearchParams();
  const skip=['board','tubes','caps','hasLed','hasWs2812','trim','cathOrder','anodeOrder'];
  for(const k in c)if(!skip.includes(k))p.set(k,typeof c[k]=='boolean'?(c[k]?1:0):c[k]);
  if(c.trim)c.trim.forEach((v,i)=>p.set('trim'+i,v));
  if(c.cathOrder)p.set('cathOrderRaw',c.cathOrder);
  if(c.anodeOrder)p.set('anodeOrderRaw',c.anodeOrder);
  const r=await fetch('/api/config',{method:'POST',body:p});
  $('msg').textContent=await r.text();load();
 }catch(err){$('msg').textContent='That file could not be read.'}
 e.target.value='';
 setTimeout(()=>$('msg').textContent='',4000);
};

// -- 1 Hz status poll --
async function poll(){
 try{
  const s=await(await fetch('/api/status')).json();
  s.digits.split('').forEach((d,i)=>{const e=$('t'+i);if(!e)return;
    e.querySelector('span').textContent=d==' '?'0':d;
    e.classList.toggle('off',!s.on||d==' ')});
  // Colon dot assignment depends on the board's physical wiring:
  //
  //  cap-dupcolon (e.g. electroNIX 4+S): both colon gap positions are wired
  //    in parallel — SEC_0 drives every top neon, SEC_1 every bottom neon.
  //    Both gaps look identical, so the preview mirrors the HH:MM pair onto
  //    MM:SS: c0→colon0, c0b→colon1, c1→colon0, c1b→colon1.
  //
  //  cap-sec without cap-dupcolon (e.g. electroNIX 2): colon0 and colon1
  //    are two SEPARATE gap lamps (HH:MM and MM:SS respectively).  Each gap
  //    is drawn as a symmetric pair so both dots in that pair share one
  //    status: c0=c0b=colon0 (HH:MM), c1=c1b=colon1 (MM:SS).
  //
  //  4-tube dual-neon (e.g. electroNIX 4): one gap, two lamps.  c0 is the
  //    upper lamp (colon0), c0b is the lower (colon1); they differ on
  //    ALTERNATE and during the untrusted-time warning.
  //
  //  Single-neon (electroNIX 3 without the SEC_1 bodge): one gap, one lamp.
  //    colon1On is always false, so c0b must follow colon0 to stay visible.
  const hasSec   = document.body.classList.contains('cap-sec');
  const dupColon = document.body.classList.contains('cap-dupcolon');
  const dualNeon = !document.body.classList.contains('cap-neon1opt') ||
                   !!($('neon1Fitted') && $('neon1Fitted').checked);
  $('c0').classList.toggle('off', !s.on || !s.colon0);
  // c0b — lower dot of HH:MM colon:
  //   dupcolon → colon1 (bottom neon, same signal as the other gap's bottom)
  //   6-tube non-dup → colon0 (both HH:MM dots share the single HH:MM lamp)
  //   4-tube single-neon → colon0 (mirror c0, only one lamp exists)
  //   4-tube dual-neon → colon1 (the separate lower lamp)
  $('c0b').classList.toggle('off', !s.on || ((hasSec && !dupColon) ? !s.colon0 : (!dualNeon ? !s.colon0 : !s.colon1)));
  // c1 — upper dot of MM:SS colon:
  //   dupcolon → colon0 (top neon shared with HH:MM top; mirrors c0)
  //   otherwise → colon1 (the independent MM:SS lamp)
  $('c1').classList.toggle('off', !s.on || (dupColon ? !s.colon0 : !s.colon1));
  $('c1b').classList.toggle('off', !s.on || !s.colon1);
  
  // Check the accent setting and current colon mode
  const acc = $('colonAccent') ? +$('colonAccent').value : 0;
  const isAlt = $('colon') ? $('colon').value === '3' : false;
  
  ['ca0', 'ca1', 'ca2'].forEach((id, idx) => { 
    const e = $(id); 
    if (!e) return;
    
    let accentOff = !s.on || acc === 0;
    
    if (acc === 2) {
      if (isAlt) {
        // Disable "Match the colon" entirely when "Alternate" is active
        accentOff = true;
      } else {
        accentOff = !s.on || !s.colon0;
      }
    }
    
    e.classList.toggle('off', accentOff); 
  });
  
  $('sdate').textContent=s.date;
  if(s.hv!==undefined){$('shv').textContent=s.hv.toFixed(0)+' V'+(s.hvFault?' FAULT':'');
    $('sduty').textContent=s.duty.toFixed(0)+'%';
    $('shvcuts').textContent=s.hvcuts;
    $('shvcuts').style.color=(s.hvcuts>0)?'#ff7a1a':''}
  $('sbr').textContent=s.bright+'%';
  if(s.lightmv!==undefined){
    const pin=s.lightmv>3050;
    $('slight').textContent=Math.round(s.lightmv)+' mV \u00b7 '+(pin?'railed':s.lightpct+'%');
    $('slightpp').textContent='\u00b1'+s.lightpp+' mV';
    $('slightpp').style.color=(s.lightpp>60)?'#ff7a1a':'';
  }
  $('swifi').textContent=s.mode=='ap'?'AP mode':s.rssi+' dBm';
  // src enum: 0=NONE, 1=SAVED, 2=RTC, 3=BROWSER, 4=NTP
  // Trusted threshold is >=2 (RTC and above); below that the time is a guess.
  const SRC=['not set','estimated','RTC','browser','NTP'];
  const age=s.age<0?'':(s.age<90?' \u00b7 just now':' \u00b7 '+Math.round(s.age/60)+'m ago');
  $('sntp').textContent=(SRC[s.src]||'?')+(s.src>=2?age:'');
  $('sntp').style.color=s.src===0?'#ff7a1a':s.src===1?'var(--amber)':'var(--ok)';
  if(s.rtcOk!==undefined){
    $('srtc').textContent=s.rtcOk?'ok':'no module';
    $('srtc').style.color=s.rtcOk?'var(--ok)':'#ff7a1a';
  }
  $('scpu0').textContent=s.cpu0+'%';
  $('scpu1').textContent=s.cpu1+'%';
  $('smux').textContent=s.mux+'%';
  $('smux').style.color=(s.mux<98||s.mux>102)?'#ff7a1a':'';
  $('smuxmin').textContent=s.muxmin+'%';
  $('smuxmin').style.color=(s.muxmin<98)?'#ff7a1a':'';
  $('sheap').textContent=Math.round(s.heap/1024)+' kB';
  // Auto-sync from the browser when time isn't trusted (src < 2, i.e. NONE
  // or SAVED).  src=2 is RTC, which is already trustworthy -- no override.
  if(s.src<2&&!autoSynced){autoSynced=true;await setTime(true)}
 }catch(e){}
 setTimeout(poll,1000);
}
load();poll();
</script></div></body></html>)HTML";