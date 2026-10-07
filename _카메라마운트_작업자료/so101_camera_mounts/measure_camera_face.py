"""Measure the original camera face in its own plane, independent of STL axes."""
import json, os, itertools
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from inspect_wrist_source import ROOT

t=np.load(ROOT/'wrist_inspection_candidate.npy')
vertices,ix=np.unique(t.reshape(-1,3),axis=0,return_inverse=True)
faces=ix.reshape(-1,3)
u=np.array([1.,0.,0.])
v=np.array([0.,np.cos(np.deg2rad(25)),np.sin(np.deg2rad(25))])
n=np.cross(u,v)
reference=np.array([-11.,59.62523333333334,-8.896015222222223])
d=reference@n
normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
selected=(np.max(np.abs(t@n-d),axis=1)<0.00015)&(normals@n>0)
f=faces[selected]
e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
edges,ec=np.unique(np.sort(e,axis=1),axis=0,return_counts=True)
boundary=edges[ec==1]
g=coo_matrix((np.ones(len(boundary)),(boundary[:,0],boundary[:,1])),shape=(len(vertices),len(vertices))).tocsr()
_,labels=connected_components(g,directed=False)
used=np.unique(boundary)
holes=[]
for label in np.unique(labels[used]):
    ids=used[labels[used]==label]
    p=vertices[ids]
    uv=np.column_stack([p@u,p@v])
    # Algebraic circle fit supports nonuniform polygon sampling.
    a=np.column_stack([2*uv,np.ones(len(uv))])
    solution=np.linalg.lstsq(a,np.sum(uv*uv,axis=1),rcond=None)[0]
    centre=solution[:2]
    radii=np.linalg.norm(uv-centre,axis=1)
    if len(p)>=8 and radii.std()<0.03 and 0.5<radii.mean()<3:
        # Exporter also places vertices on polygon chords; fit the original
        # circular polygon corners, excluding those intermediate chord points.
        best=np.zeros(len(uv),dtype=bool)
        for triplet in itertools.combinations(range(len(uv)),3):
            aa=a[list(triplet)]
            if abs(np.linalg.det(aa))<1e-8: continue
            ss=np.linalg.solve(aa,np.sum(uv[list(triplet)]**2,axis=1))
            rr=np.sqrt(max(0,ss[2]+ss[:2]@ss[:2]))
            inliers=np.abs(np.linalg.norm(uv-ss[:2],axis=1)-rr)<0.0001
            if inliers.sum()>best.sum(): best=inliers
        assert best.sum()>=8
        solution=np.linalg.lstsq(a[best],np.sum(uv[best]**2,axis=1),rcond=None)[0]
        centre=solution[:2]
        radii=np.linalg.norm(uv[best]-centre,axis=1)
        holes.append({'centre_uv_mm':centre.tolist(),'centre_xyz_mm':(u*centre[0]+v*centre[1]+n*d).tolist(),'nominal_diameter_mm':float(2*radii.mean()),'circle_fit_error_mm':float(radii.std()),'boundary_vertices':len(p),'circular_polygon_corners':int(best.sum())})
holes.sort(key=lambda h:(round(h['centre_uv_mm'][1],2),h['centre_uv_mm'][0]))
print(json.dumps(holes,indent=2))
assert len(holes)==4, 'Expected exactly four camera screw holes'
centres=np.array([h['centre_uv_mm'] for h in holes])
pitch=np.ptp(centres,axis=0)
assert np.allclose(pitch,[27,27],atol=0.001)
report={'measured_object':'Original supplied SO101 integrated wrist STL; NOT a measurement of either physical camera','plane_u':u.tolist(),'plane_v':v.tolist(),'plane_normal':n.tolist(),'plane_offset_mm':float(d),'hole_centres_and_diameters':holes,'pitch_mm':pitch.tolist(),'physical_camera_compatibility_confirmed':False}
(ROOT/'camera_face_measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
fig,ax=plt.subplots(figsize=(7,7),facecolor='#f3f6fa')
mid=centres.mean(axis=0)
lines=np.stack([vertices[boundary]@u,vertices[boundary]@v],axis=-1)-mid
ax.add_collection(LineCollection(lines,colors='#236488',linewidths=1.4))
for x,y in centres-mid:
    ax.plot(x,y,'+',color='#d46124',markersize=8)
    ax.annotate(f'({x:.1f}, {y:.1f})',(x,y),xytext=(6,7),textcoords='offset points',fontsize=9)
for a,b in [((-13.5,-20),(13.5,-20)),((-21,-13.5),(-21,13.5))]:
    ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'<->','color':'#d46124'})
ax.text(0,-22,'27 mm',ha='center',color='#b64b13',fontsize=13)
ax.text(-23,0,'27 mm',va='center',rotation=90,color='#b64b13',fontsize=13)
ax.set(xlim=(-27,27),ylim=(-27,27),aspect='equal',xlabel='Camera face horizontal (mm)',ylabel='Camera face vertical (mm)')
ax.set_title('Original STL camera mounting holes\n27 x 27 mm centres / approximately 2 mm diameter',pad=15)
ax.grid(alpha=.2); ax.set_facecolor('#f3f6fa')
fig.text(.5,.015,'This measures the mount. Camera hole spacing still needs confirmation.',ha='center',fontsize=9,color='#5e6f7e')
fig.tight_layout(rect=[0,.04,1,1]); fig.savefig(ROOT/'camera_hole_dimensions.png',dpi=150); plt.close(fig)
