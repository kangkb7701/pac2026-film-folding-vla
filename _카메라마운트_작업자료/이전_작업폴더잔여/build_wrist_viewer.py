"""Offline viewer of the supplied STL, with no external model downloads."""
import base64, json
import numpy as np
from inspect_wrist_source import ROOT, read_mesh

triangles=read_mesh()
normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
normals/=np.linalg.norm(normals,axis=1)[:,None]
data=np.concatenate([triangles.reshape(-1,3),np.repeat(normals,3,axis=0)],axis=1).astype('<f4')
bounds=np.stack([triangles.min(axis=(0,1)),triangles.max(axis=(0,1))])
measurement=json.loads((ROOT/'camera_face_measurements.json').read_text())
camera_centre=np.mean([h['centre_xyz_mm'] for h in measurement['hole_centres_and_diameters']],axis=0)
config={'data':base64.b64encode(data.tobytes()).decode(),'vertexCount':len(data),'centre':bounds.mean(axis=0).tolist(),'radius':float(np.ptp(bounds,axis=0).max()/2),'cameraCentre':camera_centre.tolist()}

html=r'''<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SO-101 일체형 그리퍼 · 실제 STL 보기</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#213849;font:15px/1.65 system-ui,'Malgun Gothic',sans-serif}header{padding:20px 28px;background:white;border-bottom:1px solid #d6e0e8}h1{font-size:23px;margin:0}header p{margin:5px 0 0;color:#5e7080}main{display:grid;grid-template-columns:minmax(0,1fr) 310px}#stage{position:relative}canvas{display:block;width:100%;height:calc(100vh - 114px);min-height:480px;touch-action:none}aside{padding:24px;background:white;border-left:1px solid #d6e0e8}button{cursor:pointer;padding:9px 13px;margin:4px 3px 4px 0;border:1px solid #bfd1df;border-radius:7px;background:#edf5fb;color:#213849}button:hover{background:#dceefb}.notice{padding:13px;border-radius:8px;background:#fff2d6;font-size:13px}a{color:#176b9a}.small{font-size:13px;color:#647988}#hint{position:absolute;bottom:20px;left:20px;background:#ffffffdd;border-radius:8px;padding:8px 12px;pointer-events:none}#error{display:none;padding:22px;color:#a43b32}strong{font-weight:650}hr{border:0;border-top:1px solid #e0e8ee;margin:20px 0}@media(max-width:760px){main{grid-template-columns:1fr}canvas{height:60vh;min-height:380px}aside{border-left:0}}
</style>
<header><h1>SO-101 고정 그리퍼 + 카메라 지지대</h1><p>보내준 원본 STL의 실제 형상 · 설치 없이 회전하고 확대해서 확인</p></header>
<main><section id="stage"><canvas id="view" aria-label="회전 가능한 일체형 그리퍼 3D 모델"></canvas><div id="error"></div><div id="hint">드래그: 회전 · 마우스 휠: 확대 / 축소</div></section>
<aside><strong>보는 방향</strong><p><button data-pose="iso">전체 입체</button><button data-pose="opposite">반대쪽</button><button data-pose="side">옆면</button><button data-pose="camera">카메라 장착면</button></p>
<p><button id="save">현재 모습 PNG 저장</button></p><hr>
<strong>원본 마운트에서 측정</strong><p>나사 구멍 중심 간격<br><b style="font-size:24px">27 × 27 mm</b><br>구멍 지름 약 2 mm · 구멍 4개</p>
<p><a href="camera_hole_dimensions.png" target="_blank">나사 구멍 치수 그림 보기</a><br><a href="wrist_original_preview.png" target="_blank">전체 형상 이미지 보기</a></p>
<div class="notice">카메라 기판의 32×32mm 크기와 나사 구멍 간격은 별개의 치수입니다. 카메라의 구멍 간격과 렌즈·커넥터 간섭은 아직 확인되지 않았습니다.</div>
<p class="small">움직이는 집게, 모터, 카메라는 이 STL에 포함되지 않습니다. 색상은 몸통과 카메라 지지대의 위치를 구분하기 위한 표시입니다.</p>
<p class="small">표시 중인 형상은 수정 전 공식 원본입니다. 겹친 표면을 정리한 참고 STL도 준비했습니다. 카메라별 최종 출력 파일은 아직 완성 전입니다.</p>
<p><a href="SO101_integrated_wrist_27mm_REFERENCE_mesh_cleaned.stl" download>27mm 규격 참고 STL 받기</a><br><a href="wrist_reference_ko.txt" target="_blank">참고 STL 설명 보기</a></p>
<a class="small" href="https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/Wrist_Cam_Mount_32x32_UVC_Module" target="_blank" rel="noopener">공식 원본 및 조립 설명</a>
</aside></main>
<script id="mesh" type="application/json">__DATA__</script>
<script>
'use strict';
const config=JSON.parse(document.getElementById('mesh').textContent),canvas=document.getElementById('view');
function start(){
 const gl=canvas.getContext('webgl',{antialias:true,preserveDrawingBuffer:true});
 if(!gl)throw Error('3D 표시를 사용할 수 없습니다. 옆의 전체 형상 이미지 링크를 이용하세요.');
 const vs=`attribute vec3 position;attribute vec3 normal;uniform vec3 centre;uniform vec3 right;uniform vec3 up;uniform vec3 toward;uniform float radius;uniform float aspect;varying vec3 n;varying vec3 color;void main(){vec3 p=position-centre;gl_Position=vec4(dot(p,right)/(radius*aspect),dot(p,up)/radius,-dot(p,toward)/(radius*4.0),1.0);n=normal;color=position.y>28.0?vec3(.89,.52,.18):vec3(.22,.58,.77);}`;
 const fs=`precision mediump float;varying vec3 n;varying vec3 color;void main(){vec3 nn=normalize(n);float light=.5+.5*max(dot(nn,normalize(vec3(-.3,-.6,.75))),0.0);gl_FragColor=vec4(color*light,1.0);}`;
 function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
 const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vs));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
 const raw=Uint8Array.from(atob(config.data),c=>c.charCodeAt(0));const floats=new Float32Array(raw.buffer);
 if(floats.length!==config.vertexCount*6)throw Error('모델 데이터 길이가 맞지 않습니다.');
 gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());gl.bufferData(gl.ARRAY_BUFFER,floats,gl.STATIC_DRAW);
 for(const[name,offset]of[['position',0],['normal',12]]){const loc=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,3,gl.FLOAT,false,24,offset);}
 const uniforms=Object.fromEntries(['centre','right','up','toward','radius','aspect'].map(name=>[name,gl.getUniformLocation(program,name)]));
 gl.enable(gl.DEPTH_TEST);gl.clearColor(.929,.949,.969,1);
 let az=-55*Math.PI/180,el=25*Math.PI/180,centre=config.centre.slice(),baseRadius=config.radius,zoom=1.12;
 function draw(){const density=Math.min(window.devicePixelRatio||1,2),w=Math.round(canvas.clientWidth*density),h=Math.round(canvas.clientHeight*density);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}gl.viewport(0,0,w,h);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);const ca=Math.cos(az),sa=Math.sin(az),ce=Math.cos(el),se=Math.sin(el);gl.uniform3fv(uniforms.centre,centre);gl.uniform3fv(uniforms.right,[-sa,ca,0]);gl.uniform3fv(uniforms.up,[-se*ca,-se*sa,ce]);gl.uniform3fv(uniforms.toward,[ce*ca,ce*sa,se]);gl.uniform1f(uniforms.radius,baseRadius/zoom*Math.max(1,h/w));gl.uniform1f(uniforms.aspect,w/h);gl.drawArrays(gl.TRIANGLES,0,config.vertexCount);}
 function pose(name){centre=config.centre.slice();baseRadius=config.radius;zoom=1.12;if(name==='camera'){centre=config.cameraCentre.slice();baseRadius=25;zoom=1;az=-Math.PI/2;el=65*Math.PI/180;}else if(name==='opposite'){az=125*Math.PI/180;el=25*Math.PI/180;}else if(name==='side'){az=0;el=0;}else{az=-55*Math.PI/180;el=25*Math.PI/180;}draw();}
 for(const button of document.querySelectorAll('[data-pose]'))button.onclick=()=>pose(button.dataset.pose);
 let pointer=null;canvas.onpointerdown=e=>{pointer=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};canvas.onpointermove=e=>{if(!pointer)return;az-=(e.clientX-pointer[0])*.008;el=Math.max(-1.55,Math.min(1.55,el+(e.clientY-pointer[1])*.008));pointer=[e.clientX,e.clientY];draw();};canvas.onpointerup=canvas.onpointercancel=()=>{pointer=null;};canvas.onwheel=e=>{e.preventDefault();zoom=Math.max(.35,Math.min(8,zoom*Math.exp(-e.deltaY*.001)));draw();};
 canvas.addEventListener('wheel',e=>e.preventDefault(),{passive:false});
 document.getElementById('save').onclick=()=>{draw();const a=document.createElement('a');a.download='SO101_integrated_gripper_view.png';a.href=canvas.toDataURL('image/png');a.click();};window.addEventListener('resize',draw);draw();
}
try{start();}catch(e){document.getElementById('error').style.display='block';document.getElementById('error').textContent=e.message;}
</script></html>'''
(ROOT/'SO101_integrated_gripper_viewer.html').write_text(html.replace('__DATA__',json.dumps(config,separators=(',',':'))),encoding='utf-8')
print('Created offline viewer:',len(data),'vertices; original STL geometry embedded.')
