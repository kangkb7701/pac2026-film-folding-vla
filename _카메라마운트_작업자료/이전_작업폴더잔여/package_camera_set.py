"""Publish the printing files and move previous task material into one archive."""
from pathlib import Path
import ast, base64, hashlib, json, re, shutil, zipfile
import numpy as np

ROOT=Path(__file__).resolve().parent
WORK=Path.cwd().resolve()
SOURCE=ROOT/'camera_set_v0.2'
PRINT=WORK/'3D프린팅_STL'
ARCHIVE=WORK/'_카메라마운트_작업자료'
GUIDE=ARCHIVE/'미리보기와설명'
GUIDE.mkdir(parents=True,exist_ok=True)

mapping={
 '01_탑뷰_OPEN/01_기둥_3개.stl':'OPEN_TS11_002/topview/column_180mm_x3.stl',
 '01_탑뷰_OPEN/02_기둥연결판_4개.stl':'OPEN_TS11_002/topview/joint_strap_x4.stl',
 '01_탑뷰_OPEN/03_책상클램프_2개.stl':'OPEN_TS11_002/topview/desk_clamp_10_to_45mm_x2.stl',
 '01_탑뷰_OPEN/04_상단카메라암_1개.stl':'OPEN_TS11_002/topview/top_arm_camera_slots_x1.stl',
 '01_탑뷰_OPEN/05_클램프압착패드_2개.stl':'OPEN_TS11_002/topview/clamp_pressure_pad_x2.stl',
 '01_탑뷰_OPEN/06_카메라스페이서3mm_4개.stl':'common/M2_spacer_3mm.stl',
 '02_그리퍼_OPEN/01_카메라마운트일체형그리퍼_1개.stl':'OPEN_TS11_002/SO101_fixed_gripper_camera_slots_v0.2.stl',
 '02_그리퍼_OPEN/02_카메라스페이서3mm_4개.stl':'common/M2_spacer_3mm.stl',
 '03_그리퍼_PyBrain/01_카메라마운트일체형그리퍼_1개.stl':'PyBrain/SO101_fixed_gripper_camera_slots_v0.2.stl',
 '03_그리퍼_PyBrain/02_카메라스페이서3mm_4개.stl':'common/M2_spacer_3mm.stl',
}
validation=json.loads((SOURCE/'mesh_validation.json').read_text(encoding='utf-8'))
for dest,src in mapping.items():
    assert hashlib.sha256((SOURCE/src).read_bytes()).hexdigest()==validation[src]['sha256']
    target=PRINT/dest;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SOURCE/src,target)
print('출력용 STL 10개 정리 완료: '+str(PRINT),flush=True)

guide='''SO-101 카메라 마운트 v0.2 — 출력·조립 안내

출력 파일 위치: 바탕화면\\4-2\\3D프린팅_STL
파일 이름 끝의 “1개 / 2개 / 3개 / 4개”가 출력 수량입니다.
STL 폴더에는 최신 출력 부품만 있습니다. 코드, 이전 버전, 검사 기록은 보관 폴더에 있습니다.
출력업체에 도면을 전달할 때는 STL 폴더를 사용하세요.
직접 출력할 때는 STL을 슬라이서에서 열어 프린터용 출력 파일로 변환해야 합니다.

[이번에 적용한 가정]
사용자가 정확한 규격 대신 일반적인 규격으로 진행하도록 요청한 시제품입니다.
두 카메라 모두 기판 32×32mm, 나사 중심 간격 27×27mm를 가정했습니다.
네 구멍은 대각선 방향의 짧은 슬롯으로 넓혔습니다.
슬롯의 명목 폭 2.6mm, 정사각형 나사 배치의 중심 간격 약 26~28mm 조절을 목표로 합니다.
그리퍼 슬롯은 원본 구멍의 다각형 해상도를 사용하므로 실제 최소 폭은 명목 폭보다 작습니다.
OPEN용과 PyBrain용 그리퍼 형상은 현재 같습니다. 용도별로 폴더만 구분했습니다.
렌즈 및 USB 커넥터 위치는 실측하지 않았습니다. 실제 카메라 체결·실물 출력은 미검증입니다.

[출력 설정의 시작값]
단위 mm, 배율 100%. 가장 긴 부품은 180mm입니다.
0.4mm 노즐 기준: 레이어 0.16~0.20mm, 벽 5줄, 내부 채움 35%.
책상 클램프는 벽 6줄, 내부 채움 50%로 시작하세요.
PLA 기준 시제품이며, 클램프를 과도하게 조여 휘게 만들지 마세요.
파일에 배치된 방향으로 출력합니다. 그리퍼는 서포트를 활성화하세요.
나사 구멍과 너트 홈 주변의 서포트는 조립 전에 제거합니다.
그리퍼는 모터 몸통과 고정 집게를 포함합니다. 움직이는 집게는 기존 부품을 재사용합니다.

[탑뷰 부품 — 01_탑뷰_OPEN]
기둥 3개, 기둥연결판 4개, 책상클램프 2개, 상단카메라암 1개,
클램프압착패드 2개, 카메라스페이서 4개를 출력합니다.
새로 설계한 분할 기둥 방식이며 공식 탑뷰 원본의 복제본은 아닙니다.
기둥 3개일 때 책상 위 높이 약 552mm, 2개일 때 약 372mm입니다.
카메라 중심은 기둥 뒤쪽 면에서 책상 안쪽으로 약 162mm 떨어집니다.

필요한 금속 부품:
- M4×35mm 볼트 12개: 기둥 연결부 8개 + 상단 암 4개
- M4×40mm 볼트 4개: 기둥과 책상 클램프 연결
- M4 너트 16개, M4 평와셔 32개
- M8×80mm 전체 나사산 볼트 2개, M8 너트 2개
- 카메라용 M2×12~16mm 볼트 4개, M2 너트 4개, 작은 M2 평와셔 8개
M2 길이는 실제 카메라와 스페이서를 쌓아 확인합니다. 나사산이 너트 밖으로 조금 나와야 합니다.

탑뷰 조립 순서:
1. 책상 클램프 두 개를 기둥 맨 아래의 좌우에 놓습니다.
   클램프의 긴 기둥 부분이 뒤쪽, 65mm 길이의 턱이 책상 안쪽을 향합니다.
   아래 기둥의 바닥에서 20mm와 60mm 위치 구멍에 M4×40 볼트 4개로 연결합니다.
2. 클램프 아래턱의 육각 홈에 M8 너트를 넣습니다.
   아래에서 M8×80 볼트를 넣고, 끝에 압착 패드를 대어 책상 밑면에 닿게 합니다.
   패드의 막힌 평평한 면이 책상에 닿고, 오목한 홈이 볼트 끝을 향합니다.
   책상 두께는 약 10~45mm를 가정했습니다. 두 클램프를 번갈아 조입니다.
3. 기둥 끝끼리 맞대고 이음부 앞뒤에 연결판을 하나씩 댑니다.
   각 이음부에 M4×35 볼트 4개로 고정합니다. 이음부는 총 2곳입니다.
4. 상단 카메라 암의 세로판을 맨 위 기둥 앞면에 댑니다.
   기둥 위에서 20mm와 60mm 위치의 구멍을 사용해 M4×35 볼트 4개로 연결합니다.
5. 카메라를 상단 암 끝의 네 슬롯에 연결합니다. 렌즈가 아래를 향합니다.
   카메라와 판 사이에 3mm 스페이서 4개를 넣고 M2 볼트·와셔·너트로 고정합니다.
6. USB 케이블은 기둥에 묶어 카메라 커넥터를 잡아당기지 않게 정리합니다.

[일체형 그리퍼 — 02_그리퍼_OPEN / 03_그리퍼_PyBrain]
각 폴더에서 그리퍼 1개와 스페이서 4개를 출력합니다.
각 카메라에 M2×12~16mm 볼트 4개, M2 너트 4개, 작은 평와셔 8개가 필요합니다.
모터를 기존 고정 그리퍼에서 분리하고 새 몸통에 기존 나사로 옮깁니다.
움직이는 집게는 모터에 붙어 있는 기존 것을 사용합니다.
카메라는 렌즈가 지지판의 중앙 개구부를 향하도록, 스페이서를 사이에 넣어 장착합니다.
USB 커넥터와 모터·집게가 닿지 않는 방향으로 카메라를 돌려 장착합니다.
첫 장착 후 손으로 관절과 집게를 천천히 움직여 간섭을 확인합니다.

[검사 범위]
STL의 닫힌 표면, 모서리 연결, 표면 방향, 한 덩어리 연결, 양의 체적을 검사했습니다.
그리퍼의 모터 결합 형상은 원본 좌표를 유지했습니다. 출력용 전체 회전·이동은 적용했습니다.
실물 조립, 출력 수축, 하중 시험, 모든 표면의 자기 교차 검사는 실시하지 않았습니다.

[원본 및 출처]
그리퍼 원본: TheRobotStudio/SO-ARM100
https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/Wrist_Cam_Mount_32x32_UVC_Module
원본의 중복 표면을 정리하고 카메라 구멍을 넓혀 수정했습니다.
원본 라이선스는 함께 보관된 UPSTREAM_LICENSE.txt를 참고하세요.
탑뷰 기둥·클램프·카메라 암과 스페이서는 이번 작업에서 새로 생성했습니다.
'''
(GUIDE/'출력과조립안내.txt').write_text(guide,encoding='utf-8-sig')
shutil.copy2(ROOT/'sources/topview/UPSTREAM_LICENSE',GUIDE/'UPSTREAM_LICENSE.txt')

# Reuse the checked, installation-free WebGL viewer with the new actual meshes.
tree=ast.parse((ROOT/'build_wrist_viewer.py').read_text(encoding='utf-8'))
template=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='html' for x in node.targets))
assembly=np.load(SOURCE/'assembly_preview_data.npz')
top=np.concatenate([assembly[key] for key in assembly.files])
wrist=np.load(SOURCE/'wrist_display.npy')
def config(t,camera):
    n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
    data=np.c_[t.reshape(-1,3),np.repeat(n,3,axis=0)].astype('<f4')
    bounds=np.array([t.min(axis=(0,1)),t.max(axis=(0,1))])
    return {'data':base64.b64encode(data.tobytes()).decode(),'vertexCount':len(data),'centre':bounds.mean(axis=0).tolist(),'radius':float(np.ptp(bounds,axis=0).max()/2),'cameraCentre':camera}
holes=json.loads((ROOT/'camera_face_measurements.json').read_text())
wc=np.mean([h['centre_xyz_mm'] for h in holes['hole_centres_and_diameters']],axis=0).tolist()
dataset={'top':config(top,[0,162,550]),'wrist':config(wrist,wc)}
template=re.sub(r'<header>.*?</header>','<header><h1>출력할 카메라 마운트 v0.2</h1><p>탑뷰는 조립한 위치로 표시합니다. 그리퍼는 카메라 구멍을 수정한 실제 형상입니다.</p></header>',template,flags=re.S)
aside='''<aside><strong>볼 모델 선택</strong><p><a href="#top">탑뷰 조립 모습</a><br><a href="#wrist">그리퍼 일체형 모습</a></p><strong>보는 방향</strong><p><button data-pose="iso">전체 입체</button><button data-pose="opposite">반대쪽</button><button data-pose="side">옆면</button><button data-pose="camera">카메라 장착면</button></p><p><button id="save">현재 모습 PNG 저장</button></p><hr><p>기판 32×32mm와 나사 간격 27×27mm를 가정했습니다. 짧은 슬롯으로 약 26~28mm 정사각형 나사 배치의 조절을 목표로 했습니다.</p><p>OPEN·PyBrain 그리퍼는 현재 같은 형상입니다.</p><p><a href="출력과조립안내.txt" target="_blank">출력 수량 · 준비할 나사 · 조립 순서</a></p><p class="small">카메라·모터·움직이는 집게·금속 나사는 표시하지 않았습니다. 실물 출력과 조립은 아직 검증하지 않았습니다.</p><p class="small">출력 파일: 바탕화면 → 4-2 → 3D프린팅_STL</p></aside>'''
template=re.sub(r'<aside>.*?</aside>',aside,template,flags=re.S)
template=template.replace('SO-101 일체형 그리퍼 · 실제 STL 보기','카메라 마운트 v0.2 · 탑뷰와 그리퍼')
template=template.replace("const config=JSON.parse(document.getElementById('mesh').textContent),canvas=document.getElementById('view');","const scenes=JSON.parse(document.getElementById('mesh').textContent);const config=scenes[location.hash==='#wrist'?'wrist':'top'],canvas=document.getElementById('view');window.addEventListener('hashchange',()=>location.reload());")
viewer=template.replace('__DATA__',json.dumps(dataset,separators=(',',':')))
(GUIDE/'미리보기.html').write_text(viewer,encoding='utf-8')
# Compile scripts without executing a browser and check all embedded mesh byte counts.
for scene in dataset.values():assert len(base64.b64decode(scene['data']))==scene['vertexCount']*24
(GUIDE/'viewer_script_check.cjs').write_text("const fs=require('fs'),vm=require('vm'),path=require('path');const h=fs.readFileSync(path.join(__dirname,'미리보기.html'),'utf8');for(const m of h.matchAll(/<script>([\\s\\S]*?)<\\/script>/g))new vm.Script(m[1]);console.log('Viewer JavaScript syntax passed');",encoding='utf-8')
print('최신 모델 3D 미리보기와 조립 안내 생성 완료',flush=True)

# A small delivery ZIP has the printing STLs, guide and upstream license, not code.
archive_zip=ARCHIVE/'3D프린팅_STL_전달용.zip'
with zipfile.ZipFile(archive_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(PRINT.rglob('*.stl')):z.write(p,Path('3D프린팅_STL')/p.relative_to(PRINT))
    z.write(GUIDE/'출력과조립안내.txt','설명/출력과조립안내.txt')
    z.write(GUIDE/'UPSTREAM_LICENSE.txt','설명/UPSTREAM_LICENSE.txt')
with zipfile.ZipFile(archive_zip) as z:assert z.testzip() is None
(GUIDE/'출력파일목록.json').write_text(json.dumps({dst:validation[src] for dst,src in mapping.items()},ensure_ascii=False,indent=2),encoding='utf-8')
print('출력용 전달 ZIP 검사 완료',flush=True)

# Archive only known camera-task files. Resolve and constrain both move endpoints.
names=['SO101_PiCameraV2_adapter_v0.1.zip','SO101_PiV2_with_assembly_preview.zip','SO101_PiV2_with_assembly_preview','so101_camera_mounts']
for name in names:
    src=(WORK/name).resolve();dest=(ARCHIVE/name).resolve()
    assert src.parent==WORK and dest.parent==ARCHIVE.resolve()
    assert src.is_relative_to(WORK) and dest.is_relative_to(WORK)
    if src.exists():
        assert not dest.exists(),f'Preserving existing archive: {dest}'
        shutil.move(str(src),str(dest))
print('이전 파일과 설계 자료를 보관 폴더로 이동 완료',flush=True)
