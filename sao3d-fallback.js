/* ALBAZ SAO v10.0.9 — robust 3D globe fallback
   Independent runtime: guarantees 2D/3D controls even if another inline block fails.
*/
(function(){
  'use strict';

  var state = { lon0: 30 * Math.PI/180, lat0: 16 * Math.PI/180, zoom: 0.92, dragging:false, px:0, py:0, raf:0 };

  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
  function wrapPi(v){ while(v<=-Math.PI)v+=2*Math.PI; while(v>Math.PI)v-=2*Math.PI; return v; }

  function ensureUI(){
    var stage = document.getElementById('mapStage');
    var mapCanvas = document.getElementById('mapCanvas');
    if(!stage || !mapCanvas) return null;

    var switcher = document.querySelector('.sao3d-switcher');
    if(!switcher){
      switcher = document.createElement('div');
      switcher.className = 'sao3d-switcher sao3d-fallback-switcher';
      switcher.innerHTML = '<button type="button" id="view2dBtn" class="secondary active">الخريطة 2D</button>'+
        '<button type="button" id="view3dBtn" class="secondary">الكرة الأرضية 3D</button>';
      stage.parentNode.insertBefore(switcher, stage);
    }

    var btn2 = document.getElementById('view2dBtn') || switcher.querySelector('button:first-child');
    var btn3 = document.getElementById('view3dBtn') || switcher.querySelector('button:last-child');

    var panel = document.getElementById('sao3dPanel');
    if(!panel){
      panel = document.createElement('section');
      panel.id = 'sao3dPanel';
      panel.innerHTML = '<div class="sao3d-head">'+
        '<div class="sao3d-title">الكرة الأرضية ثلاثية الأبعاد — طبقة رؤية الهلال SAAO</div>'+
        '<div class="sao3d-actions">'+
          '<button type="button" id="sao3dResetBtn" class="secondary">إعادة التمركز</button>'+
          '<button type="button" id="sao3dRefreshBtn" class="secondary">تحديث الطبقة</button>'+
        '</div></div>'+
        '<div class="sao3d-wrap"><canvas id="globeCanvas" width="720" height="720" aria-label="كرة أرضية ثلاثية الأبعاد"></canvas></div>'+
        '<div class="sao3d-help">اسحب الكرة بالماوس للدوران، واستخدم عجلة الماوس للتقريب. ألوان الرؤية مأخوذة مباشرة من الخريطة العلمية 2D الحالية.</div>';
      if(stage.nextSibling) stage.parentNode.insertBefore(panel, stage.nextSibling); else stage.parentNode.appendChild(panel);
    }

    var globe = document.getElementById('globeCanvas');
    if(!globe){
      var wrap = panel.querySelector('.sao3d-wrap') || panel;
      globe = document.createElement('canvas');
      globe.id = 'globeCanvas'; globe.width = 720; globe.height = 720;
      wrap.appendChild(globe);
    }

    return {stage:stage,mapCanvas:mapCanvas,switcher:switcher,btn2:btn2,btn3:btn3,panel:panel,globe:globe};
  }

  function sourceXY(lonDeg, latDeg, mapCanvas){
    try{
      if(typeof lonToX === 'function' && typeof latToY === 'function'){
        return {x:lonToX(lonDeg), y:latToY(latDeg)};
      }
    }catch(_){ }
    var x = (lonDeg + 180) / 360 * mapCanvas.width;
    var y = (90 - latDeg) / 180 * mapCanvas.height;
    return {x:x,y:y};
  }

  function render(ui){
    if(!ui || !ui.globe || !ui.mapCanvas) return;
    var canvas = ui.globe, ctx = canvas.getContext('2d', {alpha:true});
    var W = canvas.width, H = canvas.height;
    var srcCtx = ui.mapCanvas.getContext('2d', {willReadFrequently:true});
    if(!srcCtx) return;

    var src;
    try{ src = srcCtx.getImageData(0,0,ui.mapCanvas.width,ui.mapCanvas.height); }
    catch(err){ return; }

    var out = ctx.createImageData(W,H);
    var d = out.data, sd = src.data, sw = src.width, sh = src.height;
    var cx = W/2, cy = H/2, R = Math.min(W,H)*0.46*state.zoom;
    var sin0 = Math.sin(state.lat0), cos0 = Math.cos(state.lat0);

    for(var y=0;y<H;y++){
      var ny = (cy-y)/R;
      for(var x=0;x<W;x++){
        var nx = (x-cx)/R;
        var rr = nx*nx + ny*ny;
        var oi = (y*W+x)*4;
        if(rr>1){ d[oi]=3; d[oi+1]=9; d[oi+2]=16; d[oi+3]=255; continue; }

        var rho = Math.sqrt(rr), lat, lon;
        if(rho<1e-9){ lat=state.lat0; lon=state.lon0; }
        else{
          var c = Math.asin(rho), sinc=Math.sin(c), cosc=Math.cos(c);
          lat = Math.asin(cosc*sin0 + (ny*sinc*cos0)/rho);
          lon = state.lon0 + Math.atan2(nx*sinc, rho*cos0*cosc - ny*sin0*sinc);
        }
        lon = wrapPi(lon);
        var lonDeg = lon*180/Math.PI, latDeg=lat*180/Math.PI;
        var p = sourceXY(lonDeg,latDeg,ui.mapCanvas);
        var sx = clamp(Math.round(p.x),0,sw-1), sy=clamp(Math.round(p.y),0,sh-1);
        var si=(sy*sw+sx)*4;

        var limb = Math.sqrt(Math.max(0,1-rr));
        var shade = 0.72 + 0.28*limb;
        d[oi]   = Math.round(sd[si]*shade);
        d[oi+1] = Math.round(sd[si+1]*shade);
        d[oi+2] = Math.round(sd[si+2]*shade);
        d[oi+3] = 255;
      }
    }
    ctx.putImageData(out,0,0);

    ctx.save();
    ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2);
    ctx.lineWidth=Math.max(2,W/300); ctx.strokeStyle='rgba(255,228,163,.72)'; ctx.stroke();
    var g=ctx.createRadialGradient(cx-R*.25,cy-R*.28,R*.05,cx,cy,R*1.03);
    g.addColorStop(0,'rgba(255,255,255,.10)'); g.addColorStop(.65,'rgba(255,255,255,0)'); g.addColorStop(1,'rgba(0,0,0,.20)');
    ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2); ctx.fill();
    ctx.restore();
  }

  function requestRender(ui){
    if(state.raf) cancelAnimationFrame(state.raf);
    state.raf=requestAnimationFrame(function(){ state.raf=0; render(ui); });
  }

  function bind(ui){
    if(!ui || ui.switcher.dataset.sao3dFallbackBound==='1') return;
    ui.switcher.dataset.sao3dFallbackBound='1';

    function show2d(e){ if(e)e.preventDefault(); ui.stage.style.display=''; ui.panel.classList.remove('active'); ui.panel.style.display='none'; if(ui.btn2)ui.btn2.classList.add('active'); if(ui.btn3)ui.btn3.classList.remove('active'); }
    function show3d(e){ if(e)e.preventDefault(); ui.stage.style.display='none'; ui.panel.classList.add('active'); ui.panel.style.display='block'; if(ui.btn3)ui.btn3.classList.add('active'); if(ui.btn2)ui.btn2.classList.remove('active'); requestRender(ui); }

    if(ui.btn2) ui.btn2.addEventListener('click',show2d,true);
    if(ui.btn3) ui.btn3.addEventListener('click',show3d,true);

    var reset=document.getElementById('sao3dResetBtn');
    if(reset) reset.addEventListener('click',function(){ state.lon0=30*Math.PI/180; state.lat0=16*Math.PI/180; state.zoom=.92; requestRender(ui); });
    var refresh=document.getElementById('sao3dRefreshBtn');
    if(refresh) refresh.addEventListener('click',function(){ requestRender(ui); });

    var g=ui.globe;
    g.addEventListener('pointerdown',function(e){ state.dragging=true; state.px=e.clientX; state.py=e.clientY; g.classList.add('dragging'); try{g.setPointerCapture(e.pointerId);}catch(_){} });
    g.addEventListener('pointermove',function(e){ if(!state.dragging)return; var dx=e.clientX-state.px,dy=e.clientY-state.py; state.px=e.clientX;state.py=e.clientY; state.lon0=wrapPi(state.lon0-dx*.006); state.lat0=clamp(state.lat0+dy*.005,-Math.PI/2+.03,Math.PI/2-.03); requestRender(ui); });
    function stop(e){state.dragging=false;g.classList.remove('dragging');try{g.releasePointerCapture(e.pointerId);}catch(_){}}
    g.addEventListener('pointerup',stop); g.addEventListener('pointercancel',stop);
    g.addEventListener('wheel',function(e){e.preventDefault();state.zoom=clamp(state.zoom*(e.deltaY<0?1.07:.93),.64,1.12);requestRender(ui);},{passive:false});

    window.addEventListener('resize',function(){ if(ui.panel.classList.contains('active')) requestRender(ui); });
    window.SAO3D_FALLBACK = {show3d:show3d,show2d:show2d,render:function(){requestRender(ui);}};
  }

  function boot(){
    var ui=ensureUI();
    if(!ui) return false;
    bind(ui);
    return true;
  }

  function start(){
    if(boot()) return;
    var tries=0;
    var timer=setInterval(function(){ tries++; if(boot() || tries>40) clearInterval(timer); },150);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
  window.addEventListener('load',function(){ setTimeout(boot,120); },{once:true});
})();
