"""Build a local, installation-free WebGL assembly viewer.

Official binary meshes load from GitHub in the user's browser. Camera geometry
and camera bracket placement are a visualization, not a physical fit validation.
"""
from pathlib import Path
import base64
import json
import struct
import numpy as np
import generate_adapter as adapter

ROOT = Path(__file__).resolve().parent


def stl_bytes(vertices, faces):
    triangles = vertices[faces].astype(np.float32)
    result = bytearray(b'Camera exterior visualization'.ljust(80, b' '))
    result.extend(struct.pack('<I', len(triangles)))
    for t in triangles:
        n = np.cross(t[1]-t[0], t[2]-t[0])
        n /= np.linalg.norm(n)
        result.extend(struct.pack('<12fH', *n, *t.ravel(), 0))
    return bytes(result)


def encode(data):
    return base64.b64encode(data).decode('ascii')


plate_name = 'SO101_PiCameraV2_adapter_27mm_v0.1.stl'
board_outline = np.array([[-12.5, -15.612], [12.5, -15.612], [12.5, 8.25], [-12.5, 8.25]])
holes = [(np.array(c), 1.1) for c in adapter.hole_centres(21, 12.5)]
board_v, board_f = adapter.extrude(board_outline, holes, 1.12)
data = {
    'plate': encode((ROOT / plate_name).read_bytes()),
    'spacer': encode((ROOT / 'M2_spacer_5mm_v0.1.stl').read_bytes()),
    'pcb': encode(stl_bytes(board_v, board_f)),
}

HTML = r'''<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SO-101 · 라즈베리파이 V2 장착 미리보기</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#edf1f5;color:#20313e;font:15px/1.65 system-ui,'Malgun Gothic',sans-serif}
header{padding:18px 26px;background:white;border-bottom:1px solid #d7e0e8}h1{margin:0;font-size:23px}header p{margin:5px 0 0;color:#596b79}
main{display:grid;grid-template-columns:minmax(0,1fr) 330px;min-height:calc(100vh - 105px)}#view{position:relative;min-height:550px}canvas{display:block;width:100%;height:calc(100vh - 105px);min-height:550px;touch-action:none}
#hint{position:absolute;bottom:20px;left:24px;padding:8px 12px;background:#ffffffd9;border-radius:8px;pointer-events:none}
aside{background:#fff;padding:20px;border-left:1px solid #d7e0e8}p{margin:8px 0 14px}button{padding:9px 13px;background:#edf4f8;border:1px solid #c1d4e0;border-radius:7px;cursor:pointer;color:#20313e}button:hover{background:#dceaf3}button.active{background:#c7e2f3}input[type=range]{width:100%}
.row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 18px}.legend{display:flex;align-items:center;gap:9px;padding:5px 0}.dot{height:12px;width:12px;border-radius:50%;display:inline-block}.small{font-size:12px;color:#647482}.notice{padding:12px;background:#fff4d9;border-radius:8px;font-size:13px}.status{font-size:13px;margin:12px 0;white-space:pre-line}a{color:#1473a3}details{margin-top:18px}summary{cursor:pointer}#fatal{display:none;color:#a43b32;padding:15px}
@media(max-width:800px){main{grid-template-columns:1fr}canvas{height:65vh;min-height:420px}#view{min-height:420px}aside{border-left:0;border-top:1px solid #d7e0e8}}
</style>
<header><h1>SO-101 그리퍼에 V2 카메라를 달면</h1><p>그리퍼 · 공식 마운트 · 변환판 · 스페이서 · 카메라를 한 화면에서 확인하세요.</p></header>
<main><section id="view"><canvas id="canvas"></canvas><div id="fatal"></div><div id="hint">드래그: 회전 · 휠: 확대 / 축소</div></section>
<aside><b>보는 방향</b><div class="row"><button data-view="iso">입체</button><button data-view="front">정면</button><button data-view="side">옆면</button><button data-view="back">뒷면</button></div>
<label>부품 사이 벌리기 <span id="explode-value">0 mm</span><input id="explode" type="range" min="0" max="30" value="0"></label>
<label>그리퍼 벌리기 <span id="jaw-value">25°</span><input id="jaw" type="range" min="0" max="75" value="25"></label>
<div id="legend"></div><div class="row"><button id="reset">처음 화면</button><button id="save">이미지 저장</button></div>
<div class="notice"><b>장착 모습을 설명하는 시제품 미리보기</b><br>그리퍼 형상과 내부 배치는 공식 도면을 사용합니다. 마운트의 그리퍼 장착 위치는 커뮤니티 조립 자료에 따른 참고 배치입니다. 카메라 외형은 단순화했습니다. 실물 나사 체결과 간섭 검증은 아직 하지 않았습니다.</div>
<div id="status" class="status">공식 그리퍼 부품을 불러오는 중…</div><button id="retry">공식 부품 다시 불러오기</button>
<details><summary>공식 부품이 로드되지 않을 때</summary><p class="small">아래 파일을 내려받은 뒤 ‘STL 파일 선택’을 눌러 모두 선택하세요. 이 목록의 파일은 조립 위치가 정해진 공식 시뮬레이션 부품입니다.</p><div id="downloads"></div><input id="local" type="file" accept=".stl" multiple aria-label="STL 파일 선택"></details>
<details><summary>도면 출처</summary><p class="small"><a href="https://github.com/TheRobotStudio/SO-ARM100/tree/main/Simulation/SO101" target="_blank" rel="noopener">공식 그리퍼 도면과 조립 좌표</a><br><a href="https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/SO101_Wrist_Cam_Hex-Nut_Mount_32x32_UVC_Module" target="_blank" rel="noopener">공식 손목 카메라 마운트</a><br><a href="https://github.com/livekit-examples/so-frame/blob/main/simulation/urdf/so101_on_frame.urdf" target="_blank" rel="noopener">마운트 장착 위치 참고 자료</a><br><a href="https://datasheets.raspberrypi.com/camera/camera-module-2-mechanical-drawing.pdf" target="_blank" rel="noopener">라즈베리파이 V2 기구 도면</a></p></details>
</aside></main>
<script id="embedded" type="application/json">__EMBEDDED__</script>
<script>
'use strict';
const $=id=>document.getElementById(id), embedded=JSON.parse($('embedded').textContent);
const SOURCES={
 body:{name:'고정 그리퍼',file:'wrist_roll_follower_so101_v1.stl',url:'https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/Simulation/SO101/assets/wrist_roll_follower_so101_v1.stl',color:[.94,.56,.13],scale:1000},
 jaw:{name:'움직이는 집게',file:'moving_jaw_so101_v1.stl',url:'https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/Simulation/SO101/assets/moving_jaw_so101_v1.stl',color:[.94,.56,.13],scale:1000},
 servo:{name:'그리퍼 모터',file:'sts3215_03a_v1.stl',url:'https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/Simulation/SO101/assets/sts3215_03a_v1.stl',color:[.21,.25,.29],scale:1000},
 mount:{name:'공식 카메라 마운트',file:'SO-ARM101_camera_wrist_mount.stl',url:'https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/Optional/SO101_Wrist_Cam_Hex-Nut_Mount_32x32_UVC_Module/stl/SO-ARM101_camera_wrist_mount.stl',color:[.35,.62,.81],scale:1}
};
const meshData={}, loadStates={};
let yaw=.7,pitch=.35,zoom=.012,jawAngle=25,explode=0,vertexCount=0;
const target=[0,25,-37];
function base64Buffer(s){return Uint8Array.from(atob(s),c=>c.charCodeAt(0)).buffer}
function parseSTL(buffer,scale=1){
 const d=new DataView(buffer), positions=[];
 if(buffer.byteLength>=84 && 84+d.getUint32(80,true)*50===buffer.byteLength){
  const n=d.getUint32(80,true);for(let i=0;i<n;i++)for(let j=0;j<9;j++)positions.push(d.getFloat32(84+i*50+12+j*4,true)*scale);
 }else{
  const text=new TextDecoder().decode(buffer),re=/vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)/g;
  for(const match of text.matchAll(re))positions.push(...match.slice(1,4).map(v=>Number(v)*scale));
 }
 if(!positions.length || positions.length%9 || positions.some(v=>!Number.isFinite(v)))throw Error('유효한 STL이 아닙니다.');
 return new Float32Array(positions);
}
function rotate(p,r){let[x,y,z]=p;let[a,b,c]=r;[y,z]=[Math.cos(a)*y-Math.sin(a)*z,Math.sin(a)*y+Math.cos(a)*z];[x,z]=[Math.cos(b)*x+Math.sin(b)*z,-Math.sin(b)*x+Math.cos(b)*z];return[Math.cos(c)*x-Math.sin(c)*y,Math.sin(c)*x+Math.cos(c)*y,z]}
function rigid(p,t,r){return rotate(p,r).map((v,i)=>v+t[i])}
const bracketT=[-15,24,-31.5],bracketR=[-Math.PI/2,-.0008,-Math.PI/2];
const mountCentre=[-47.57375352365805,-34.30890951779805,17.5];
const bx=[.90630778703665,-.42261826174070,0],by=[0,0,1],bn=[-.42261826174070,-.90630778703665,0];
function cameraPose(p,extra=0){return rigid(mountCentre.map((v,i)=>v+bx[i]*p[0]+by[i]*p[1]+bn[i]*(p[2]+extra)),bracketT,bracketR)}
function box(w,h,d){const p=[[-w/2,-h/2,0],[w/2,-h/2,0],[w/2,h/2,0],[-w/2,h/2,0],[-w/2,-h/2,d],[w/2,-h/2,d],[w/2,h/2,d],[-w/2,h/2,d]],f=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];return new Float32Array(f.flatMap(t=>t.flatMap(i=>p[i])))}
meshData.plate=parseSTL(base64Buffer(embedded.plate));meshData.spacer=parseSTL(base64Buffer(embedded.spacer));meshData.pcb=parseSTL(base64Buffer(embedded.pcb));meshData.lens=box(8,8,5);meshData.connector=box(20.8,5.5,2.7);
const canvas=$('canvas'),gl=canvas.getContext('webgl',{antialias:true,preserveDrawingBuffer:true});
if(!gl){$('fatal').style.display='block';$('fatal').textContent='이 브라우저에서 3D 화면을 열지 못했습니다. 크롬 또는 엣지로 열어보세요.';throw Error('WebGL unavailable')}
function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
const vs=shader(gl.VERTEX_SHADER,`attribute vec3 position;attribute vec3 normal;attribute vec3 color;uniform vec3 target;uniform float yaw;uniform float pitch;uniform float zoom;uniform float aspect;varying vec3 shade;void main(){vec3 p=position-target;float x=cos(yaw)*p.x-sin(yaw)*p.y;float y=sin(yaw)*p.x+cos(yaw)*p.y;float v=cos(pitch)*p.z-sin(pitch)*y;float depth=sin(pitch)*p.z+cos(pitch)*y;gl_Position=vec4(x*zoom/aspect,v*zoom,-depth/500.0,1.0);float light=.48+.52*abs(dot(normalize(normal),normalize(vec3(-.35,.6,.8))));shade=color*light;}`);
const fs=shader(gl.FRAGMENT_SHADER,`precision mediump float;varying vec3 shade;void main(){gl_FragColor=vec4(shade,1.0);}`);
const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
for(const[name,offset]of[['position',0],['normal',12],['color',24]]){const loc=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,3,gl.FLOAT,false,36,offset)}
const uniforms=Object.fromEntries(['target','yaw','pitch','zoom','aspect'].map(k=>[k,gl.getUniformLocation(program,k)]));gl.enable(gl.DEPTH_TEST);gl.clearColor(.925,.945,.965,1);
function rebuild(){
 const packed=[];
 function add(data,color,transform){if(!data)return;for(let i=0;i<data.length;i+=9){const t=[0,3,6].map(j=>transform(Array.from(data.slice(i+j,i+j+3))));const a=t[1].map((v,j)=>v-t[0][j]),b=t[2].map((v,j)=>v-t[0][j]);let n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];const length=Math.hypot(...n);if(length<1e-12)continue;n=n.map(v=>v/length);for(const p of t)packed.push(...p,...n,...color)}}
 add(meshData.body,SOURCES.body.color,p=>rigid(p,[0,-.218214,.949706],[-Math.PI,0,0]));
 add(meshData.servo,SOURCES.servo.color,p=>rigid(p,[7.7,.1,-23.4],[-Math.PI/2,0,0]));
 add(meshData.jaw,SOURCES.jaw.color,p=>rigid(rotate([p[0],p[1],p[2]+18.9],[0,0,jawAngle*Math.PI/180]),[20.2,18.8,-23.4],[Math.PI/2,0,0]));
 add(meshData.mount,SOURCES.mount.color,p=>rigid(p,bracketT,bracketR));
 add(meshData.plate,[.85,.33,.29],p=>cameraPose(p,explode));
 for(const x of[-10.5,10.5])for(const y of[-6.25,6.25])add(meshData.spacer,[.7,.72,.74],p=>cameraPose([p[0]+x,p[1]+y,p[2]+3],explode*2));
 add(meshData.pcb,[.22,.55,.32],p=>cameraPose([p[0],p[1],p[2]+8],explode*3));
 add(meshData.lens,[.14,.17,.2],p=>cameraPose([p[0]+1.3,p[1]-1.212,p[2]+9.12],explode*3));
 add(meshData.connector,[.88,.87,.79],p=>cameraPose([p[0],p[1]-12.86,p[2]+9.12],explode*3));
 gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(packed),gl.STATIC_DRAW);vertexCount=packed.length/9;draw();
}
function draw(){const ratio=Math.min(devicePixelRatio||1,2),w=Math.round(canvas.clientWidth*ratio),h=Math.round(canvas.clientHeight*ratio);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}gl.viewport(0,0,w,h);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniform3fv(uniforms.target,target);gl.uniform1f(uniforms.yaw,yaw);gl.uniform1f(uniforms.pitch,pitch);gl.uniform1f(uniforms.zoom,zoom);gl.uniform1f(uniforms.aspect,w/h);gl.drawArrays(gl.TRIANGLES,0,vertexCount)}
function status(){const missing=Object.keys(SOURCES).filter(k=>loadStates[k]!=='ok');$('status').textContent=missing.length?'아직 '+missing.length+'개 공식 부품이 표시되지 않았습니다.\n'+missing.map(k=>SOURCES[k].name+': '+(loadStates[k]==='error'?'불러오기 실패':'불러오는 중')).join('\n'):'공식 그리퍼·모터·마운트 로드 완료.\n카메라 장착 위치는 참고 배치입니다.'}
async function loadPart(key){loadStates[key]='loading';status();try{const response=await fetch(SOURCES[key].url,{signal:AbortSignal.timeout(20000)});if(!response.ok)throw Error('HTTP '+response.status);meshData[key]=parseSTL(await response.arrayBuffer(),SOURCES[key].scale);loadStates[key]='ok';rebuild()}catch(e){loadStates[key]='error';console.warn(SOURCES[key].name,e)}status()}
async function loadAll(){await Promise.allSettled(Object.keys(SOURCES).filter(k=>loadStates[k]!=='ok').map(loadPart))}
let drag=null;canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)});canvas.addEventListener('pointermove',e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-drag[1])*.008));drag=[e.clientX,e.clientY];draw()});canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.003,Math.min(.07,zoom*Math.exp(-e.deltaY*.001)));draw()},{passive:false});window.addEventListener('resize',draw);
$('explode').oninput=e=>{explode=+e.target.value;$('explode-value').textContent=explode+' mm';rebuild()};$('jaw').oninput=e=>{jawAngle=+e.target.value;$('jaw-value').textContent=jawAngle+'°';rebuild()};
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{[yaw,pitch]=({iso:[.7,.35],front:[0,0],side:[Math.PI/2,0],back:[Math.PI,0]})[b.dataset.view];draw()};
$('reset').onclick=()=>{yaw=.7;pitch=.35;zoom=.012;explode=0;jawAngle=25;$('explode').value=0;$('jaw').value=25;$('explode-value').textContent='0 mm';$('jaw-value').textContent='25°';rebuild()};
$('save').onclick=()=>{draw();const a=document.createElement('a');a.download='SO101_PiV2_assembly_preview.png';a.href=canvas.toDataURL('image/png');a.click()};$('retry').onclick=loadAll;
$('local').onchange=async e=>{for(const f of e.target.files){const key=Object.keys(SOURCES).find(k=>SOURCES[k].file.toLowerCase()===f.name.toLowerCase());if(!key)continue;try{meshData[key]=parseSTL(await f.arrayBuffer(),SOURCES[key].scale);loadStates[key]='ok'}catch(err){loadStates[key]='error'}}rebuild();status()};
for(const[name,color]of[['그리퍼',[.94,.56,.13]],['공식 마운트',[.35,.62,.81]],['변환판',[.85,.33,.29]],['스페이서',[.7,.72,.74]],['카메라 PCB',[.22,.55,.32]]]){const row=document.createElement('div');row.className='legend';const dot=document.createElement('span');dot.className='dot';dot.style.background='rgb('+color.map(v=>Math.round(v*255)).join(',')+')';row.append(dot,document.createTextNode(name));$('legend').append(row)}
for(const source of Object.values(SOURCES)){const p=document.createElement('p'),a=document.createElement('a');a.href=source.url;a.textContent=source.file;a.className='small';a.target='_blank';a.rel='noopener';p.append(a);$('downloads').append(p)}
rebuild();loadAll();
window.assemblyPreview={parseSTL,rotate,rigid,cameraPose,SOURCES,getMeshData:()=>meshData};
</script></html>'''

html = HTML.replace('__EMBEDDED__', json.dumps(data, separators=(',', ':')))
output = ROOT/'SO101_PiV2_assembly_viewer.html'
output.write_text(html, encoding='utf-8')
print(f'Created {output.name}: {output.stat().st_size} bytes')
