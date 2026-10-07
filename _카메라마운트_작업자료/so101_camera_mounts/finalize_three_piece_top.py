"""Replace the rejected multi-part tower with the official three integral bodies."""
from pathlib import Path
import base64,json,shutil,zipfile,re
import numpy as np
import build_camera_set_v02 as cad

WORK=Path.cwd().resolve();ROOT=Path(__file__).resolve().parent
ARCHIVE=WORK/'_카메라마운트_작업자료';GUIDE=ARCHIVE/'미리보기와설명'
PRINT=WORK/'3D프린팅_STL';TOP=PRINT/'01_탑뷰_OPEN';TOP.mkdir(exist_ok=True)
removed=ARCHIVE/'제외한_스페이서';removed.mkdir(exist_ok=True)
for folder in ['02_그리퍼_OPEN','03_그리퍼_PyBrain']:
    src=PRINT/folder/'02_카메라스페이서3mm_4개.stl';dst=removed/(folder+'_스페이서.stl')
    if src.exists():
        assert src.resolve().is_relative_to(WORK) and dst.resolve().is_relative_to(WORK)
        assert not dst.exists();src.rename(dst)

models=[];report={}
names=[('bottom','01_하단_받침일체형_1개.stl'),('middle','02_중단_기둥일체형_1개.stl'),('top','03_상단_카메라거치대일체형_1개.stl')]
for part,name in names:
    src=ROOT/'sources/topview'/f'cam_mount_{part}.stl'
    t=cad.load_stl(src);report[name]=cad.validate(t)
    shutil.copy2(src,TOP/name)
    if part!='bottom':t=t+[18.7,188.1,36.5125]
    t=t[:,:,[2,0,1]]-[36.5125,18.7,0]
    models.append(t)

# Independent C-clamps are moving desk-fixing hardware, as in the supplied photo.
# The upright mounting extensions of the rejected design are removed.
f=cad.Field(([-11,-18,-77],[11,65,12]))
s=np.minimum(f.box([-11,-18,-77],[11,0,12]),np.minimum(f.box([-11,0,0],[11,65,12]),f.box([-11,0,-77],[11,65,-65])))
s=np.maximum(s,-f.cylinder(2,(0,43),4.4,-78,-64))
s=np.maximum(s,-f.hex_z((0,43),13.8,-71.8,-64))
clamp=f.mesh(s)
cad.OUT=TOP
cad.save('04_책상고정클램프_2개.stl',cad.on_bed(cad.transform(clamp,[[0,1,0],[0,0,1],[1,0,0]])),2,'M8 x 80 fully threaded metal bolt and M8 nut; add rubber on desk contact. No tower mounting extensions.')
report['04_책상고정클램프_2개.stl']=cad.REPORT['04_책상고정클램프_2개.stl']
for x in [-35,35]:models.append(clamp+[x,-18.7,7.95])

guide='''최종 출력 구성 — 사진과 같은 3분할 일체형 본체

출력 파일: 바탕화면\\4-2\\3D프린팅_STL

01_탑뷰_OPEN (STL 4종)
- 하단: 받침과 기둥이 붙은 일체형 1개
- 중단: 기둥 일체형 1개
- 상단: 기둥과 카메라 거치대가 붙은 일체형 1개
- 책상 고정 클램프 2개
별도의 기둥 연결판, 별도의 상단 카메라 암, 카메라 스페이서는 없습니다.
본체는 길이 때문에 나눈 상·중·하 접합부 2곳만 조립합니다.
클램프는 사진 구성처럼 책상에 고정하는 별도 부품입니다.

02_그리퍼_OPEN: 카메라마운트 일체형 고정 그리퍼 1개
03_그리퍼_PyBrain: 카메라마운트 일체형 고정 그리퍼 1개
각 폴더에는 출력할 STL만 남겼습니다. 파일 이름에 출력 수량을 표시했습니다.

카메라 장착
기판 32×32mm를 가정했습니다. 스페이서 없이 나사로 직접 연결합니다.
탑뷰 상단은 공식 32×32mm 카메라 마운트 원본의 구멍을 그대로 사용합니다.
그리퍼는 27×27mm를 기준으로 짧은 슬롯을 적용한 이전 수정본입니다.
그리퍼의 슬롯은 M2 볼트·와셔·너트로 체결합니다. 두 카메라용 그리퍼는 같은 가정 치수입니다.
실제 카메라의 렌즈·커넥터 간섭, 나사 간격, 실물 출력·조립은 아직 검증하지 않았습니다.

탑뷰 조립
1. 하단의 돌출 연결부에 중단을 끼우고 키트의 작은 M2 나사 4개로 고정합니다.
2. 중단의 연결부에 상단을 끼우고 M2 나사 4개로 고정합니다.
3. 상단 거치대에 렌즈를 중앙 개구부 쪽으로 향하게 놓고 M2 나사 4개로 직접 고정합니다.
4. 클램프 아래턱의 육각 홈에 M8 너트를 넣고 아래에서 M8×80mm 전체 나사산 볼트를 끼웁니다.
5. 하단 받침 양끝을 클램프로 책상에 고정합니다. 볼트 끝에는 책상 보호용 고무를 댑니다.
   클램프는 책상 두께 약 10~45mm와 하단 받침 두께를 함께 고려했습니다.
기둥 접합부 나사는 원본 설명의 Feetech 서보에 동봉된 작은 M2 나사를 기준으로 합니다.
카메라 고정 나사의 길이는 실제 기판과 거치대 두께를 보고 선택합니다.

준비물
- 기둥 접합부 M2 나사 8개, 카메라 한 개당 M2 나사 4개
- 슬롯이 있는 그리퍼에는 카메라 한 개당 M2 너트 4개와 작은 평와셔
- 클램프용 M8×80mm 전체 나사산 볼트 2개, M8 너트 2개, 책상 보호용 고무 2조각
- 그리퍼의 모터 고정 나사는 기존 것을 재사용합니다.

출력
STL은 슬라이서에서 프린터용 출력 파일로 변환해야 합니다.
단위 mm, 배율 100%. 원본의 위치가 원점에서 떨어져 있으므로 슬라이서의 자동 배치를 사용합니다.
하단의 가장 긴 치수는 약 231mm입니다. 이 크기가 들어가는 출력판이 필요합니다.
중단 약 163mm, 상단 약 182mm입니다. 기존 본체 연결부를 보존했습니다.
0.4mm 노즐, 레이어 0.16~0.20mm, 벽 5줄, 내부 채움 35%를 시작값으로 사용합니다.
클램프는 벽 6줄, 내부 채움 50%. 그리퍼의 돌출부는 서포트를 활성화합니다.
큰 힘으로 클램프를 조여 휘게 만들지 않습니다.

출처와 변경
탑뷰 본체 3개: TheRobotStudio/SO-ARM100 공식 STL을 그대로 사용했습니다.
https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/Overhead_Cam_Mount_32x32_UVC_Module
그리퍼: 같은 저장소 원본의 겹친 면 정리 및 카메라 구멍을 슬롯으로 수정했습니다.
클램프: 이번 작업에서 새로 만든 별도 책상 고정 부품입니다.
원본 라이선스는 UPSTREAM_LICENSE.txt에 있습니다.
각 STL의 닫힌 표면, 표면 방향, 한 덩어리 연결을 검사했습니다. 실물 하중 시험은 하지 않았습니다.
'''
(GUIDE/'출력과조립안내.txt').write_text(guide,encoding='utf-8-sig')
shutil.copy2(ROOT/'original_top_parts.png',GUIDE/'탑뷰_상중하_일체형.png')
(GUIDE/'최종_탑뷰_검사.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

viewer_path=GUIDE/'미리보기.html';html=viewer_path.read_text(encoding='utf-8')
match=re.search(r'<script id="mesh" type="application/json">(.*?)</script>',html,re.S)
data=json.loads(match.group(1));t=np.concatenate(models)
n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
buffer=np.c_[t.reshape(-1,3),np.repeat(n,3,axis=0)].astype('<f4')
bounds=np.array([t.min(axis=(0,1)),t.max(axis=(0,1))])
data['top']={'data':base64.b64encode(buffer.tobytes()).decode(),'vertexCount':len(buffer),'centre':bounds.mean(axis=0).tolist(),'radius':float(np.ptp(bounds,axis=0).max()/2),'cameraCentre':[0,30,551]}
html=html[:match.start(1)]+json.dumps(data,separators=(',',':'))+html[match.end(1):]
html=re.sub(r'<header>.*?</header>','<header><h1>사진과 같은 상·중·하 일체형 탑뷰</h1><p>본체는 3개입니다. 길이 분할 접합부만 조립하며, 책상 고정용 클램프는 별도입니다.</p></header>',html,flags=re.S)
html=html.replace('기판 32×32mm와 나사 간격 27×27mm를 가정했습니다. 짧은 슬롯으로 약 26~28mm 정사각형 나사 배치의 조절을 목표로 했습니다.','기판 32×32mm를 가정했습니다. 탑뷰는 공식 원본의 카메라 고정 구멍을 사용하고, 그리퍼는 27mm 간격의 짧은 슬롯을 적용했습니다. 카메라 스페이서는 없습니다.')
html=html.replace('<strong>보는 방향</strong>','<p><a href="탑뷰_상중하_일체형.png" target="_blank">상·중·하 부품 모양 보기</a></p><strong>보는 방향</strong>')
viewer_path.write_text(html,encoding='utf-8')

with zipfile.ZipFile(ARCHIVE/'3D프린팅_STL_전달용.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(PRINT.rglob('*.stl')):z.write(p,Path('3D프린팅_STL')/p.relative_to(PRINT))
    for name in ['출력과조립안내.txt','UPSTREAM_LICENSE.txt']:z.write(GUIDE/name,Path('설명')/name)
with zipfile.ZipFile(ARCHIVE/'3D프린팅_STL_전달용.zip') as z:assert z.testzip() is None
print('Final: three integral tower bodies, desk clamps, two wrist variants. Spacers and straps removed from printing folders.',flush=True)
