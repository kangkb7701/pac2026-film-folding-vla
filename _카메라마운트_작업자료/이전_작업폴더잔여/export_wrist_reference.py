"""Export the inspected source-sheet candidate as a clearly labelled reference."""
import hashlib, json, struct
import numpy as np
from inspect_wrist_source import ROOT, SOURCE, read_mesh

assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='b4345ccf23f1f2ed3f4885c205cac5afbed6ddd1b183617c4801751e3bafb7b4'
t=np.load(ROOT/'wrist_inspection_candidate.npy')
inspection=json.loads((ROOT/'wrist_candidate_inspection.json').read_text())
for key in ['boundary_edges','nonmanifold_edges','inconsistent_winding_edges','degenerate_triangles']:
    assert inspection[key]==0,key
assert inspection['connected_components']==1
assert inspection['signed_volume_mm3']>0
source=read_mesh()
assert np.array_equal(source.min(axis=(0,1)),t.min(axis=(0,1)))
assert np.array_equal(source.max(axis=(0,1)),t.max(axis=(0,1)))
sheets=np.load(ROOT/'wrist_source_sheets.npz')
body=sheets['vertices'][sheets['faces'][sheets['labels']==0]]
face_keys={tuple(face.ravel()) for face in t}
assert all(tuple(face.ravel()) in face_keys for face in body)
n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
out=bytearray(b'SO101 source mesh cleanup REFERENCE - camera fit unconfirmed'.ljust(80,b' '))
out.extend(struct.pack('<I',len(t)))
for normal,tri in zip(n,t): out.extend(struct.pack('<12fH',*normal,*tri.ravel(),0))
name='SO101_integrated_wrist_27mm_REFERENCE_mesh_cleaned.stl'
(ROOT/name).write_bytes(out)
# Validate the serialized result, including any float32 vertex merges.
dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
roundtrip=np.frombuffer(out,dtype=dtype,offset=84)['vertices'].astype(float)
assert len(out)==84+50*len(t)
v,ix=np.unique(roundtrip.reshape(-1,3),axis=0,return_inverse=True)
f=ix.reshape(-1,3);e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
_,inv,c=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
assert np.all(c==2)
assert np.all(np.bincount(inv,weights=np.where(e[:,0]<e[:,1],1,-1))==0)
metadata={'file':name,'sha256':hashlib.sha256(out).hexdigest(),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'status':'Reference mesh only; neither OPEN-TS11-002 nor PyBrain fit is confirmed','changes':['Removed 1915 exact duplicate triangle copies','Selected source support sheet 4 (143 facets) instead of coincident alternative sheet 1 (103 facets); retained sheets 0, 2, 3, 4','No source vertex coordinates moved; original body sheet and camera face coordinates retained'],'triangles':len(t),'binary_stl_edge_manifold_and_winding_check':'passed','body_sheet_16776_facets_unchanged':True,'bounding_box_unchanged':True,'camera_hole_pitch_mm':[27,27],'camera_hole_nominal_diameter_mm':2,'physical_fit_tested':False,'self_intersection_check_completed':False}
(ROOT/'wrist_reference_validation.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
(ROOT/'wrist_reference_ko.txt').write_text('SO-101 일체형 고정 그리퍼 — 27mm 규격 참고용\n\n공식 원본의 중복 표면을 정리한 참고 STL입니다. 카메라별 최종 수정본은 아직 아닙니다.\n모터 몸통의 원본 표면과 카메라 구멍 좌표를 유지했습니다. 겹쳐 있던 지지대 표면 중 하나를 선택했습니다.\n구멍 중심 간격: 27 x 27mm. 구멍 지름: 약 2mm.\n출력하거나 카메라를 실제 조립한 검증은 하지 않았습니다.\n\n원본 및 조립 설명:\nhttps://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/Wrist_Cam_Mount_32x32_UVC_Module\n원본 라이선스:\nhttps://github.com/TheRobotStudio/SO-ARM100/blob/main/LICENSE\n\n3D 보기: SO101_integrated_gripper_viewer.html (수정 전 원본 표시)\n치수 그림: camera_hole_dimensions.png\n검사 기록: wrist_reference_validation.json\n',encoding='utf-8')

request=json.loads((ROOT/'current_design_request.json').read_text(encoding='utf-8'))
for item in request['requested_outputs']:
    if 'integrated_gripper' in item['id']:
        item['needs']=[need for need in item['needs'] if 'Original STL asset' not in need]
        item['status']='Original STL received and inspected; cleaned 27 mm reference exported; camera-specific compatibility pending'
request['provided_camera_specification']={'board_mm':[32,32],'source':'User supplied product description','matching_manufacturer_model':'PCBA_1080P_PS5268_AF','matching_page':'https://www.usbzwak.com/ko/2mp-auto-focus-usb-camera-module-0003lux-low-light-1080p-dynamic-range-86db-hd-web-camera-free-driver','identity_with_OPEN_TS11_002_confirmed':False,'mounting_holes':None}
request['original_wrist_measurements']={'pitch_mm':[27,27],'nominal_hole_diameter_mm':2,'camera_compatibility_confirmed':False}
(ROOT/'current_design_request.json').write_text(json.dumps(request,indent=2,ensure_ascii=False),encoding='utf-8')
print('Exported reference STL; binary manifold/winding, original body facets, and bounds verified.')
