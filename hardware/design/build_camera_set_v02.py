"""Editable prototype designs. Units mm; camera geometry is an authorized assumption.

Requires numpy, scipy, scikit-image, matplotlib. Robot motor interfaces are retained
from the supplied source; custom stand geometry is generated here.
"""
from pathlib import Path
import os, json, struct, hashlib
from collections import Counter
import numpy as np
from scipy.spatial import Delaunay
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from skimage.measure import marching_cubes

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'camera_set_v0.2'
OUT.mkdir(exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
from matplotlib.path import Path as PolygonPath

# Change these values to regenerate the prototypes after a physical fit check.
PITCH=27.0
SLOT_WIDTH=2.6
PITCH_ADJUST=1.0                 # square hole pitch: nominal 26 to 28 mm
M4_CLEARANCE=4.6
M8_CLEARANCE=8.8
COLUMN_HEIGHT=180.0
VOXEL=0.4
N=48
REPORT={}
ASSEMBLY=[]

def circle(c,r,n=N):
    a=np.arange(n)*2*np.pi/n
    return np.array(c)+r*np.column_stack([np.cos(a),np.sin(a)])

def rectangle(x0,y0,x1,y1):
    return np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]],float)

def rounded_rect(w,h,r):
    points=[]
    for c,start in [((w/2-r,h/2-r),0),((-w/2+r,h/2-r),90),((-w/2+r,-h/2+r),180),((w/2-r,-h/2+r),270)]:
        a=np.deg2rad(np.linspace(start,start+90,9))
        points.extend(np.array(c)+r*np.column_stack([np.cos(a),np.sin(a)]))
    return np.array(points)

def extrude(outer,holes,h):
    def densify(loop):
        return np.concatenate([np.linspace(a,b,max(1,int(np.ceil(np.linalg.norm(b-a)/3))),endpoint=False) for a,b in zip(loop,np.roll(loop,-1,axis=0))])
    loops=[densify(loop) for loop in [outer]+holes]
    points=np.concatenate(loops)
    f=Delaunay(points).simplices
    centres=points[f].mean(axis=1)
    keep=PolygonPath(outer).contains_points(centres)
    for hole in holes: keep &= ~PolygonPath(hole).contains_points(centres)
    f=f[keep]
    aa=points[f[:,1]]-points[f[:,0]];bb=points[f[:,2]]-points[f[:,0]]
    area=aa[:,0]*bb[:,1]-aa[:,1]*bb[:,0]
    f[area<0]=f[area<0][:,[0,2,1]]
    e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    edges,ec=np.unique(np.sort(e,axis=1),axis=0,return_counts=True)
    expected=set();offset=0
    for loop in loops:
        expected.update(tuple(sorted((offset+i,offset+(i+1)%len(loop)))) for i in range(len(loop)))
        offset+=len(loop)
    assert set(map(tuple,edges[ec==1]))==expected,'Unconstrained extrusion boundary'
    length=len(points)
    vv=np.concatenate([np.c_[points,np.zeros(length)],np.c_[points,np.full(length,h)]])
    faces=list(f[:,[0,2,1]])+list(f+length)
    for a,b in e:
        if tuple(sorted((a,b))) in expected:
            faces.extend([[a,b,b+length],[a,b+length,a+length]])
    return vv[np.array(faces)]

def load_stl(path):
    data=Path(path).read_bytes()
    count=struct.unpack_from('<I',data,80)[0]
    dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
    assert len(data)==84+count*50
    return np.frombuffer(data,dtype=dtype,offset=84)['v'].astype(float)

def volume(t):
    return np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6

def validate(t):
    assert np.isfinite(t).all()
    v,ix=np.unique(t.reshape(-1,3),axis=0,return_inverse=True)
    f=ix.reshape(-1,3)
    e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    edges,inv,c=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
    assert np.all(c==2),f'Nonmanifold/open edge counts: {np.unique(c,return_counts=True)}'
    assert np.all(np.bincount(inv,weights=np.where(e[:,0]<e[:,1],1,-1))==0),'Face winding'
    graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(len(v),len(v))).tocsr()
    count,_=connected_components(graph,directed=False)
    assert count==1,('Disconnected components',count)
    assert np.min(np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1))>1e-9
    assert volume(t)>0
    return {'triangles':len(t),'closed_edge_manifold':True,'consistent_winding':True,'connected_components':int(count),'volume_mm3':round(float(volume(t)),3),'bounds_mm':np.round(np.ptp(v,axis=0),4).tolist(),'physical_fit_tested':False}

def save(name,t,quantity=1,notes=''):
    if volume(t)<0:t=t[:,[0,2,1]]
    t=t.astype(np.float32)
    result=validate(t)
    cross=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);cross/=np.linalg.norm(cross,axis=1)[:,None]
    dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
    records=np.zeros(len(t),dtype=dtype);records['n']=cross;records['v']=t
    data=b'SO101 camera set v0.2 PROTOTYPE mm; assumed 32mm camera'.ljust(80,b' ')+struct.pack('<I',len(t))+records.tobytes()
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    assert np.array_equal(load_stl(path).astype(np.float32),t)
    result.update(quantity=quantity,notes=notes,sha256=hashlib.sha256(data).hexdigest())
    REPORT[name]=result
    print(name,len(t),'triangles',flush=True)
    return t.astype(float)

def transform(t,matrix=None,offset=(0,0,0)):
    return t@np.array(matrix).T+offset if matrix is not None else t+offset

def on_bed(t):
    return t-t.min(axis=(0,1))

def remesh_camera_caps(t,n,u,v,d):
    """Re-triangulate the two flat camera faces after changing their hole loops."""
    for plane,sign in [(d,1),(d-4,-1)]:
        mask=np.max(np.abs(t@n-plane),axis=1)<0.00015
        mask &= t[:,:,1].mean(axis=1)>50
        assert mask.sum()>20
        vertices,ix=np.unique(t[mask].reshape(-1,3),axis=0,return_inverse=True)
        f=ix.reshape(-1,3)
        e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
        edges,counts=np.unique(np.sort(e,axis=1),axis=0,return_counts=True)
        boundary=edges[counts==1]
        adjacency={}
        for a,b in boundary:adjacency.setdefault(a,[]).append(b);adjacency.setdefault(b,[]).append(a)
        assert all(len(x)==2 for x in adjacency.values())
        unused=set(adjacency);loops=[]
        while unused:
            first=min(unused);loop=[first];prev=None;current=first
            while True:
                next_id=next(x for x in adjacency[current] if x!=prev)
                if next_id==first:break
                loop.append(next_id);prev,current=current,next_id
            unused-=set(loop);loops.append(loop)
        used=np.unique(boundary);points=np.c_[vertices@u,vertices@v]
        nf=used[Delaunay(points[used]).simplices]
        centroid=points[nf].mean(axis=1)
        inside=np.zeros(len(nf),bool)
        for loop in loops:inside ^= PolygonPath(points[loop]).contains_points(centroid)
        nf=nf[inside]
        ee=np.concatenate([nf[:,[0,1]],nf[:,[1,2]],nf[:,[2,0]]])
        ue,ec=np.unique(np.sort(ee,axis=1),axis=0,return_counts=True)
        assert set(map(tuple,ue[ec==1]))==set(map(tuple,boundary)),'Camera cap edge mismatch'
        nt=vertices[nf];cross=np.cross(nt[:,1]-nt[:,0],nt[:,2]-nt[:,0])
        flip=(cross@n)*sign<0;nt[flip]=nt[flip][:,[0,2,1]]
        t=np.concatenate([t[~mask],nt])
    return t

def wrist():
    source=load_stl(ROOT/'SO101_integrated_wrist_27mm_REFERENCE_mesh_cleaned.stl')
    info=json.loads((ROOT/'camera_face_measurements.json').read_text())
    u,v,n=map(np.array,[info['plane_u'],info['plane_v'],info['plane_normal']])
    flat=source.reshape(-1,3).copy()
    uv=np.c_[flat@u,flat@v]
    mid=np.mean([h['centre_uv_mm'] for h in info['hole_centres_and_diameters']],axis=0)
    moved=np.zeros(len(flat),bool)
    for hole in info['hole_centres_and_diameters']:
        c=np.array(hole['centre_uv_mm'])
        delta=uv-c;r=np.linalg.norm(delta,axis=1)
        mask=(r<1.02)&(np.abs(flat@n-info['plane_offset_mm']+2)<2.1)
        assert mask.sum()>30
        axis=np.sign(c-mid)/np.sqrt(2)
        # Preserve the existing triangulation while opening its polygonal bore
        # into a short diagonal capsule. All surrounding body vertices are fixed.
        shifted=delta[mask]*(SLOT_WIDTH/2)+np.sign(delta[mask]@axis)[:,None]*axis*(PITCH_ADJUST/np.sqrt(2))
        displacement=shifted-delta[mask]
        flat[mask]+=displacement[:,0,None]*u+displacement[:,1,None]*v
        moved|=mask
    t=flat.reshape(-1,3,3)
    assert np.array_equal(t[np.all(source[:,:,1]<24,axis=1)],source[np.all(source[:,:,1]<24,axis=1)])
    oldn=np.cross(source[:,1]-source[:,0],source[:,2]-source[:,0])
    newn=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
    bad=np.flatnonzero(np.sum(oldn*newn,axis=1)<=0)
    assert all(np.ptp(t[i]@n)<0.00015 for i in bad),'Nonplanar face inverted'
    t=remesh_camera_caps(t,n,u,v,info['plane_offset_mm'])
    printable=transform(t,[[0,0,-1],[0,1,0],[1,0,0]])
    printable-=np.array([0,0,printable[:,:,2].min()])
    save('OPEN_TS11_002/SO101_fixed_gripper_camera_slots_v0.2.stl',printable,notes='32 mm board assumed; 27 mm nominal square pitch, diagonal adjustment for 26–28 mm; nominal slot width 2.6 mm. Source body preserved. Print on supplied side orientation with supports.')
    save('PyBrain/SO101_fixed_gripper_camera_slots_v0.2.stl',printable,notes='Same provisional geometry as OPEN version; PyBrain camera dimensions unconfirmed. 32 mm board and 27 mm nominal pitch assumed. Supports required.')
    np.save(OUT/'wrist_display.npy',t)
    return t

class Field:
    def __init__(self,bounds,step=VOXEL):
        self.origin=np.array(bounds[0],float)-step*2.37
        stop=np.array(bounds[1],float)+step*2.37
        axes=[np.arange(a,b+step,step,dtype=np.float32) for a,b in zip(self.origin,stop)]
        self.x,self.y,self.z=axes[0][:,None,None],axes[1][None,:,None],axes[2][None,None,:]
        self.shape=tuple(len(a) for a in axes);self.step=step
    def box(self,lo,hi):
        q=[np.abs(p-(a+b)/2)-(b-a)/2 for p,a,b in zip([self.x,self.y,self.z],lo,hi)]
        return np.maximum(np.maximum(q[0],q[1]),q[2])
    def cylinder(self,axis,c,r,lo,hi):
        coords=[self.x,self.y,self.z];other=[i for i in range(3) if i!=axis]
        radial=np.sqrt((coords[other[0]]-c[0])**2+(coords[other[1]]-c[1])**2)-r
        axial=np.abs(coords[axis]-(lo+hi)/2)-(hi-lo)/2
        return np.maximum(radial,axial)
    def hex_z(self,c,af,lo,hi):
        x,y=self.x-c[0],self.y-c[1]
        sides=[np.abs(x*np.cos(a)+y*np.sin(a))-af/2 for a in np.deg2rad([0,60,120])]
        return np.maximum(np.maximum(np.maximum(sides[0],sides[1]),sides[2]),np.abs(self.z-(lo+hi)/2)-(hi-lo)/2)
    def capsule_z(self,c,axis,half,w,lo,hi):
        x,y=self.x-c[0],self.y-c[1]
        along=np.clip(x*axis[0]+y*axis[1],-half,half)
        radial=np.sqrt((x-along*axis[0])**2+(y-along*axis[1])**2)-w/2
        return np.maximum(radial,np.abs(self.z-(lo+hi)/2)-(hi-lo)/2)
    def mesh(self,value):
        v,f,_,_=marching_cubes(value.astype(np.float32),level=0,spacing=(self.step,)*3,allow_degenerate=False)
        t=(v+self.origin)[f]
        if volume(t)<0:t=t[:,[0,2,1]]
        return simplify_planes(t)

def simplify_planes(t):
    """Remove interior points on large flat patches; keep every patch boundary vertex."""
    import matplotlib.tri as mtri
    vertices,ix=np.unique(t.reshape(-1,3),axis=0,return_inverse=True);faces=ix.reshape(-1,3)
    cross=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);norm=cross/np.linalg.norm(cross,axis=1)[:,None]
    output=[];done=np.zeros(len(t),bool)
    for axis in range(3):
        aligned=(np.max(np.abs(t[:,:,axis]-t[:,0:1,axis]),axis=1)<2e-5)&(np.abs(norm[:,axis])>.99999)
        vals=np.round(t[:,0,axis],4)
        for value in np.unique(vals[aligned]):
            for sign in [-1,1]:
                mask=aligned&(vals==value)&(norm[:,axis]*sign>0)
                ids=np.flatnonzero(mask)
                if len(ids)<200:continue
                f=faces[ids];e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
                edges,c=np.unique(np.sort(e,axis=1),axis=0,return_counts=True)
                boundary=edges[c==1];bv=np.unique(boundary)
                other=[i for i in range(3) if i!=axis]
                projected=vertices[bv][:,other]
                try:
                    nf=Delaunay(projected).simplices
                    allv,inv=np.unique(f,return_inverse=True)
                    finder=mtri.Triangulation(vertices[allv,other[0]],vertices[allv,other[1]],inv.reshape(-1,3)).get_trifinder()
                    p=projected[nf];cent=p.mean(axis=1)
                    inside=finder(cent[:,0],cent[:,1])>=0
                    for a,b in [(0,1),(1,2),(2,0)]:
                        mid=(p[:,a]+p[:,b])*.4999+cent*.0002
                        inside &= finder(mid[:,0],mid[:,1])>=0
                    nf=bv[nf[inside]]
                    ee=np.concatenate([nf[:,[0,1]],nf[:,[1,2]],nf[:,[2,0]]])
                    ue,cc=np.unique(np.sort(ee,axis=1),axis=0,return_counts=True)
                    if set(map(tuple,ue[cc==1]))!=set(map(tuple,boundary)):continue
                    nt=vertices[nf];nn=np.cross(nt[:,1]-nt[:,0],nt[:,2]-nt[:,0])
                    flip=nn[:,axis]*sign<0;nt[flip]=nt[flip][:,[0,2,1]]
                    if len(nt)>=len(ids):continue
                    output.append(nt);done[ids]=True
                except (ValueError,RuntimeError):continue
    result=np.concatenate([t[~done]]+output)
    print('Planar simplification',len(t),'->',len(result),flush=True)
    return result

def stand():
    holes=[circle((x,z),M4_CLEARANCE/2) for x in [-20,20] for z in [20,60,120,160]]
    column=extrude(rectangle(-30,0,30,180),holes+[rounded_rect(24,110,5)+[0,90]],12)
    save('OPEN_TS11_002/topview/column_180mm_x3.stl',on_bed(column),3,'Print flat. 60 x 180 x 12 mm.')
    # Extrusion's XY plane becomes the assembled XZ plane; thickness becomes Y.
    col=transform(column,[[1,0,0],[0,0,-1],[0,1,0]],(0,12,12))
    for i in range(3):ASSEMBLY.append(('기둥',col+[0,0,180*i],[.28,.52,.65]))
    joint=extrude(rounded_rect(60,70,4),[circle((x,z),M4_CLEARANCE/2) for x in [-20,20] for z in [-20,20]],6)
    save('OPEN_TS11_002/topview/joint_strap_x4.stl',on_bed(joint),4,'Two straps per column joint, front and back; M4 x 35 bolts.')
    for z in [192,372]:
        for y in [0,18]:ASSEMBLY.append(('이음판',transform(joint,[[1,0,0],[0,0,-1],[0,1,0]],(0,y,z)),[.83,.56,.24]))

    field=Field(([-11,-18,-70],[11,65,100]))
    sdf=np.minimum(field.box([-11,-18,-70],[11,0,100]),np.minimum(field.box([-11,0,0],[11,65,12]),field.box([-11,0,-70],[11,65,-58])))
    for z in [32,72]:sdf=np.maximum(sdf,-field.cylinder(1,(0,z),M4_CLEARANCE/2,-19,1))
    sdf=np.maximum(sdf,-field.cylinder(2,(0,43),M8_CLEARANCE/2,-71,-57))
    sdf=np.maximum(sdf,-field.hex_z((0,43),13.8,-64.8,-57))
    clamp=field.mesh(sdf)
    # C profile lies on the print bed; its 22 mm width is the print height.
    print_clamp=transform(clamp,[[0,1,0],[0,0,1],[1,0,0]])
    save('OPEN_TS11_002/topview/desk_clamp_10_to_45mm_x2.stl',on_bed(print_clamp),2,'Desk nominal 10–45 mm; M8 full-thread metal bolt and M8 metal nut required.')
    for x in [-20,20]:ASSEMBLY.append(('클램프',clamp+[x,0,0],[.25,.31,.36]))
    del field,sdf

    field=Field(([-30,0,0],[30,172,80]))
    sdf=np.minimum(field.box([-30,0,0],[30,12,80]),np.minimum(field.box([-30,0,68],[30,132,80]),field.box([-22,128,75],[22,172,80])))
    # Two side rails support the camera; a central opening reduces print mass.
    sdf=np.maximum(sdf,-field.box([-12,22,67],[12,112,81]))
    for x in [-20,20]:
        for z in [20,60]:sdf=np.maximum(sdf,-field.cylinder(1,(x,z),M4_CLEARANCE/2,-1,13))
    sdf=np.maximum(sdf,-field.box([-10,140,74],[10,160,81]))
    for x in [-13.5,13.5]:
        for y in [136.5,163.5]:
            axis=np.array([np.sign(x),np.sign(y-150)])/np.sqrt(2)
            sdf=np.maximum(sdf,-field.capsule_z((x,y),axis,PITCH_ADJUST/np.sqrt(2),SLOT_WIDTH,74,81))
    head=field.mesh(sdf)
    # Invert so the camera/arm top faces sit on the bed; upright plate grows upward.
    head_print=transform(head,[[1,0,0],[0,-1,0],[0,0,-1]])
    save('OPEN_TS11_002/topview/top_arm_camera_slots_x1.stl',on_bed(head_print),1,'Camera faces downward. 20 x 20 mm lens opening. Mount with M4 x 35 bolts. Assumed square camera pitch 26–28 mm.')
    ASSEMBLY.append(('카메라 암',head+[0,12,472],[.22,.61,.76]))
    del field,sdf

    # Pads and knobs are simple extrusions / small implicit solids.
    field=Field(([-12,-12,0],[12,12,6]))
    sdf=field.cylinder(2,(0,0),12,0,6)
    sdf=np.maximum(sdf,-field.cylinder(2,(0,0),4.4,-1,3.5))
    pad=field.mesh(sdf)
    save('OPEN_TS11_002/topview/clamp_pressure_pad_x2.stl',on_bed(pad),2,'Blind recess faces the end of the M8 bolt; flat face contacts desk underside.')
    for x in [-20,20]:ASSEMBLY.append(('압착 패드',pad+[x,43,-31],[.69,.73,.76]))

    field=Field(([-18,-18,0],[18,18,10]))
    sdf=field.cylinder(2,(0,0),18,0,10)
    sdf=np.maximum(sdf,-field.cylinder(2,(0,0),4.4,-1,11))
    sdf=np.maximum(sdf,-field.hex_z((0,0),13.8,-1,6.5))
    knob=field.mesh(sdf)
    save('OPEN_TS11_002/topview/M8_bolt_knob_optional_x2.stl',on_bed(knob),2,'Optional grip for 13 mm across-flats M8 hex bolt head; use a wrench if loose.')

    for h in [3,5]:
        spacer=extrude(circle((0,0),3),[circle((0,0),1.3)],h)
        save(f'common/M2_spacer_{h}mm.stl',on_bed(spacer),12 if h==3 else 0,'Default 3 mm stand-off, four per camera. 5 mm alternative for component clearance.')

def main():
    w=wrist();stand()
    (OUT/'mesh_validation.json').write_text(json.dumps(REPORT,indent=2,ensure_ascii=False),encoding='utf-8')
    params={'units':'mm','status':'User-authorized assumed-dimension prototype; physical fit untested','board_assumed_mm':[32,32],'nominal_hole_pitch_mm':[PITCH,PITCH],'square_pitch_adjustment_nominal_mm':[26,28],'slot_nominal_width_mm':SLOT_WIDTH,'wrist_holes_use_source_polygon_resolution':True,'stand_implicit_surface_grid_mm':VOXEL,'stand_height_mm':552,'stand_height_with_two_columns_mm':372,'camera_centre_from_column_rear_mm':162,'desk_thickness_nominal_mm':[10,45],'OPEN_and_PyBrain_wrist_geometry_currently_identical':True,'original_motor_body_coordinates_preserved_except_rigid_print_translation':True}
    (OUT/'design_parameters.json').write_text(json.dumps(params,indent=2),encoding='utf-8')
    np.savez_compressed(OUT/'assembly_preview_data.npz',**{f'mesh_{i}':t for i,(_,t,_) in enumerate(ASSEMBLY)})
    (OUT/'assembly_preview_manifest.json').write_text(json.dumps([{'name':name,'color':color} for name,_,color in ASSEMBLY],ensure_ascii=False,indent=2),encoding='utf-8')
    print('Completed',len(REPORT),'STL files',flush=True)

if __name__=='__main__':main()
