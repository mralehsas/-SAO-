from pathlib import Path
import re, sys

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/original.html')
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/tmp/index.html')
s = SRC.read_text(encoding='utf-8')

# Scientific invariants from the audited SAAO build must survive unchanged.
required_science = [
    'const SAAO_DALT_TABLE',
    'function saaoLimitsFromDAZ(daz)',
    '[0.0,8.19,6.29]',
    '[20.0,4.53,2.63],[20.5,4.43,2.53],[21.0,4.33,2.43]',
    'const saoVisualMargin = dAltLowerLimb - lim.upper;',
    'const saoOpticalMargin = dAltLowerLimb - lim.lower;',
    'BASEMAP_DATA',
    'baseImg.src = BASEMAP_DATA;'
]
for marker in required_science:
    if marker not in s:
        raise SystemExit('Scientific/source invariant missing: ' + marker)

# Remove legacy 3D integrations if this transformer is re-run.
s = re.sub(r'\n?<script[^>]+src=["\'][^"\']*sao3d[^"\']*["\'][^>]*></script>\s*', '\n', s, flags=re.I)
s = re.sub(r'\n?<script[^>]+id=["\']sao3dScript["\'][\s\S]*?</script>\s*', '\n', s, count=1, flags=re.I)
s = re.sub(r'\n?<style[^>]+id=["\']sao3dStyles["\'][\s\S]*?</style>\s*', '\n', s, count=1, flags=re.I)

# Normalize public version label without touching scientific equations.
s = s.replace('v10.0.8', 'v10.0.9').replace('10.0.8', '10.0.9')

CSS = r'''
<style id="sao3dCleanStyles">
.sao3d-switcher{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin:0 0 12px}
.sao3d-switcher button{width:auto!important;min-width:165px!important;padding:10px 16px!important}
.sao3d-switcher button.active{outline:2px solid rgba(255,228,163,.86);box-shadow:0 0 0 4px rgba(228,196,119,.13)!important}
#sao3dPanel{display:none;margin:12px 0 0;border:1px solid rgba(228,196,119,.30);border-radius:20px;overflow:hidden;background:radial-gradient(circle at 50% 38%,#18304c 0,#081521 58%,#02060b 100%);box-shadow:0 18px 55px rgba(0,0,0,.38)}
#sao3dPanel.active{display:block}
.sao3d-head{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:10px 12px;background:rgba(8,18,30,.92);border-bottom:1px solid rgba(228,196,119,.20)}
.sao3d-title{color:#ffe4a3;font-weight:700;font-size:14px}
.sao3d-actions{display:flex;gap:7px;flex-wrap:wrap}
.sao3d-actions button{width:auto!important;min-width:0!important;padding:8px 11px!important;min-height:38px!important;font-size:12px!important}
.sao3d-wrap{position:relative;width:100%;min-height:420px;display:grid;place-items:center;overflow:hidden;touch-action:none;user-select:none;padding:10px}
#globeCanvas{display:block;width:min(100%,760px);height:auto;aspect-ratio:1/1;cursor:grab;touch-action:none;filter:drop-shadow(0 18px 38px rgba(0,0,0,.52))}
#globeCanvas.dragging{cursor:grabbing}
.sao3d-help{padding:9px 12px;text-align:center;color:#aebfd4;font-size:12px;line-height:1.75;border-top:1px solid rgba(49,75,107,.55)}
@media(max-width:720px){.sao3d-switcher button{flex:1 1 145px}.sao3d-wrap{min-height:300px}}
</style>
'''
head_end = s.rfind('</head>')
if head_end < 0: raise SystemExit('Final </head> not found')
s = s[:head_end] + CSS + '\n' + s[head_end:]

SWITCHER = r'''
<div id="sao3dSwitcher" class="sao3d-switcher" aria-label="اختيار نوع الخريطة">
  <button type="button" id="saoView2DBtn" class="secondary active">الخريطة 2D</button>
  <button type="button" id="saoView3DBtn" class="secondary">الكرة الأرضية 3D</button>
</div>
'''
# Insert before the first real mapStage in the document body.
body_start = s.find('<body')
if body_start < 0: raise SystemExit('Body not found')
map_match = re.search(r'<div\s+[^>]*id=["\']mapStage["\'][^>]*>', s[body_start:], flags=re.I)
if map_match:
    pos = body_start + map_match.start()
else:
    can_match = re.search(r'<canvas\s+[^>]*id=["\']mapCanvas["\'][^>]*>', s[body_start:], flags=re.I)
    if not can_match: raise SystemExit('mapStage/mapCanvas not found')
    pos = body_start + can_match.start()
s = s[:pos] + SWITCHER + s[pos:]

PANEL = r'''
<section id="sao3dPanel" aria-label="الكرة الأرضية ثلاثية الأبعاد">
  <div class="sao3d-head">
    <div class="sao3d-title">الكرة الأرضية ثلاثية الأبعاد — نفس طبقة نتائج معيار SAAO</div>
    <div class="sao3d-actions">
      <button type="button" id="sao3dResetBtn" class="secondary">إعادة التمركز</button>
      <button type="button" id="sao3dRefreshBtn" class="secondary">تحديث الطبقة</button>
      <button type="button" id="sao3dExportBtn" class="secondary">تصدير PNG</button>
    </div>
  </div>
  <div class="sao3d-wrap"><canvas id="globeCanvas" width="680" height="680" aria-label="كرة أرضية تفاعلية"></canvas></div>
  <div class="sao3d-help">اسحب بالماوس لتدوير الكرة، واستخدم عجلة الماوس للتقريب. الألوان تُقرأ مباشرة من خريطة 2D العلمية الحالية ولا يعاد حساب معيار مستقل للعرض ثلاثي الأبعاد.</div>
</section>
'''

JS = r'''
<script id="sao3dCleanRuntime">
(function(){
'use strict';
var state={lon0:25*Math.PI/180,lat0:15*Math.PI/180,zoom:.94,drag:false,px:0,py:0,raf:0};
function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function wrapPi(v){while(v<=-Math.PI)v+=Math.PI*2;while(v>Math.PI)v-=Math.PI*2;return v;}
function boot(){
  var stage=document.getElementById('mapStage'), map=document.getElementById('mapCanvas');
  var panel=document.getElementById('sao3dPanel'), globe=document.getElementById('globeCanvas');
  var b2=document.getElementById('saoView2DBtn'), b3=document.getElementById('saoView3DBtn');
  if(!stage||!map||!panel||!globe||!b2||!b3)return;
  if(stage.nextSibling)stage.parentNode.insertBefore(panel,stage.nextSibling);else stage.parentNode.appendChild(panel);
  function sourceXY(lon,lat){
    try{if(typeof window.lonToX==='function'&&typeof window.latToY==='function')return{x:window.lonToX(lon),y:window.latToY(lat)};}catch(e){}
    return{x:(lon+180)/360*map.width,y:(90-lat)/180*map.height};
  }
  function render(){
    state.raf=0;
    var ctx=globe.getContext('2d'), sctx=map.getContext('2d',{willReadFrequently:true});
    if(!ctx||!sctx)return;
    var src;try{src=sctx.getImageData(0,0,map.width,map.height);}catch(e){return;}
    var W=globe.width,H=globe.height,out=ctx.createImageData(W,H),d=out.data,sd=src.data,sw=src.width,sh=src.height;
    var cx=W/2,cy=H/2,R=Math.min(W,H)*.465*state.zoom,R2=R*R,s0=Math.sin(state.lat0),c0=Math.cos(state.lat0);
    for(var py=0;py<H;py++){
      var yy=(cy-py)/R;
      for(var px=0;px<W;px++){
        var xx=(px-cx)/R,rr=xx*xx+yy*yy,di=(py*W+px)*4;
        if(rr>1){d[di]=2;d[di+1]=7;d[di+2]=13;d[di+3]=0;continue;}
        var z=Math.sqrt(Math.max(0,1-rr));
        var lat=Math.asin(clamp(yy*c0+z*s0,-1,1));
        var lon=state.lon0+Math.atan2(xx,z*c0-yy*s0);
        var ld=((lon*180/Math.PI+540)%360)-180, bd=lat*180/Math.PI,sp=sourceXY(ld,bd);
        var sx=Math.round(sp.x),sy=Math.round(sp.y);
        if(sx<0||sx>=sw||sy<0||sy>=sh){d[di]=8;d[di+1]=18;d[di+2]=30;d[di+3]=255;continue;}
        var si=(sy*sw+sx)*4;
        var shade=.72+.28*Math.max(0,xx*(-.42)+yy*.22+z*.86);
        d[di]=Math.min(255,sd[si]*shade);d[di+1]=Math.min(255,sd[si+1]*shade);d[di+2]=Math.min(255,sd[si+2]*shade);d[di+3]=255;
      }
    }
    ctx.putImageData(out,0,0);
    ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.strokeStyle='rgba(255,228,163,.72)';ctx.lineWidth=2;ctx.stroke();ctx.restore();
  }
  function requestRender(){if(!state.raf)state.raf=requestAnimationFrame(render);}
  function show2(){stage.style.display='';panel.classList.remove('active');b2.classList.add('active');b3.classList.remove('active');}
  function show3(){stage.style.display='none';panel.classList.add('active');b3.classList.add('active');b2.classList.remove('active');requestRender();}
  b2.addEventListener('click',show2);b3.addEventListener('click',show3);
  document.getElementById('sao3dResetBtn').addEventListener('click',function(){state.lon0=25*Math.PI/180;state.lat0=15*Math.PI/180;state.zoom=.94;requestRender();});
  document.getElementById('sao3dRefreshBtn').addEventListener('click',requestRender);
  document.getElementById('sao3dExportBtn').addEventListener('click',function(){requestRender();setTimeout(function(){var a=document.createElement('a');a.download='SAO_SAAO_3D.png';a.href=globe.toDataURL('image/png');a.click();},80);});
  globe.addEventListener('pointerdown',function(e){state.drag=true;state.px=e.clientX;state.py=e.clientY;globe.classList.add('dragging');try{globe.setPointerCapture(e.pointerId);}catch(_){} });
  globe.addEventListener('pointermove',function(e){if(!state.drag)return;var dx=e.clientX-state.px,dy=e.clientY-state.py;state.px=e.clientX;state.py=e.clientY;state.lon0=wrapPi(state.lon0-dx*.006);state.lat0=clamp(state.lat0+dy*.005,-Math.PI/2+.02,Math.PI/2-.02);requestRender();});
  function stop(e){state.drag=false;globe.classList.remove('dragging');try{globe.releasePointerCapture(e.pointerId);}catch(_){} }
  globe.addEventListener('pointerup',stop);globe.addEventListener('pointercancel',stop);
  globe.addEventListener('wheel',function(e){e.preventDefault();state.zoom=clamp(state.zoom*(e.deltaY<0?1.07:.93),.66,1.12);requestRender();},{passive:false});
  window.addEventListener('resize',function(){if(panel.classList.contains('active'))requestRender();});
  show2();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
</script>
'''

body_end=s.rfind('</body>')
if body_end<0: raise SystemExit('Final </body> not found')
s=s[:body_end]+'\n'+PANEL+'\n'+JS+'\n'+s[body_end:]

# Clean-runtime checks.
for marker in ['id="saoView2DBtn"','id="saoView3DBtn"','id="globeCanvas"','id="sao3dCleanRuntime"']:
    if s.count(marker)!=1: raise SystemExit('Expected exactly one '+marker)
for marker in required_science:
    if marker not in s: raise SystemExit('Scientific invariant lost: '+marker)
if 'sao3d-fallback.js' in s: raise SystemExit('Legacy fallback dependency survived')

DST.write_text(s,encoding='utf-8')
print('clean build bytes=',DST.stat().st_size)
