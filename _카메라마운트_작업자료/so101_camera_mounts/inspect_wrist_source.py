"""Measure and render the supplied original STL; does not modify its geometry."""
from pathlib import Path
import os, re, json, hashlib
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'sources/Wrist_Cam_Mount_32x32_UVC_Module_SO101.stl'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))

def read_mesh():
    text = SOURCE.read_text('ascii')
    xyz = re.findall(r'vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)', text)
    triangles = np.asarray(xyz, dtype=float).reshape(-1, 3, 3)
    return triangles

def inspect(triangles, report_filename='wrist_source_inspection.json'):
    vertices, index = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = index.reshape(-1, 3)
    directed = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges, inverse, counts = np.unique(np.sort(directed, axis=1), axis=0, return_inverse=True, return_counts=True)
    balance = np.bincount(inverse, weights=np.where(directed[:, 0] < directed[:, 1], 1, -1))
    graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(vertices), len(vertices))).tocsr()
    components, _ = connected_components(graph, directed=False)
    cross = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    area = np.linalg.norm(cross, axis=1)/2
    normals = cross / np.maximum(2*area[:, None], 1e-30)
    offsets = np.einsum('ij,ij->i', normals, triangles[:, 0])
    plane_keys = np.column_stack([np.round(normals, 3), np.round(offsets, 2)])
    keys, plane_index = np.unique(plane_keys, axis=0, return_inverse=True)
    plane_areas = np.bincount(plane_index, weights=area)
    planes = []
    for plane in np.argsort(plane_areas)[::-1][:35]:
        selected = faces[plane_index == plane]
        pe = np.concatenate([selected[:, [0,1]], selected[:, [1,2]], selected[:, [2,0]]])
        ue, ec = np.unique(np.sort(pe, axis=1), axis=0, return_counts=True)
        boundary = ue[ec == 1]
        bg = coo_matrix((np.ones(len(boundary)), (boundary[:,0], boundary[:,1])), shape=(len(vertices),len(vertices))).tocsr()
        _, labels = connected_components(bg, directed=False)
        loops = []
        for label in np.unique(labels[np.unique(boundary)]):
            ids = np.unique(boundary)[labels[np.unique(boundary)] == label]
            points = vertices[ids]
            centre = points.mean(axis=0)
            radii = np.linalg.norm(points-centre,axis=1)
            loops.append({'vertices':len(ids), 'centre':centre.tolist(), 'extent':np.ptp(points,axis=0).tolist(), 'radius_mean':float(radii.mean()), 'radius_std':float(radii.std())})
        planes.append({'normal_and_offset_rounded':keys[plane].tolist(), 'area_mm2':float(plane_areas[plane]), 'boundary_components':loops})
    report = {'source':SOURCE.name, 'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'units_assumed_from_official_design':'mm', 'triangles':len(faces), 'unique_vertices':len(vertices), 'bounds_min':vertices.min(axis=0).tolist(), 'bounds_max':vertices.max(axis=0).tolist(), 'extent_mm':np.ptp(vertices,axis=0).tolist(), 'boundary_edges':int(np.sum(counts==1)), 'nonmanifold_edges':int(np.sum(counts>2)), 'inconsistent_winding_edges':int(np.sum(balance!=0)), 'connected_components':int(components), 'degenerate_triangles':int(np.sum(area<1e-10)), 'signed_volume_mm3':float(np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6), 'largest_planar_groups':planes, 'physical_fit_tested':False}
    (ROOT/report_filename).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='largest_planar_groups'},indent=2))
    for i,p in enumerate(planes):
        circles=[l for l in p['boundary_components'] if l['vertices']>=8 and l['radius_std']<0.03]
        if circles: print('PLANE',i,p['normal_and_offset_rounded'],'AREA',round(p['area_mm2'],2),'CIRCLES',json.dumps(circles))

def render(triangles):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    centre=(triangles.min(axis=(0,1))+triangles.max(axis=(0,1)))/2
    radius=np.ptp(triangles.reshape(-1,3),axis=0).max()/2*1.07
    fig=plt.figure(figsize=(13,7),facecolor='#f3f6fa')
    for i,(el,az) in enumerate([(25,-55),(25,125)],1):
        ax=fig.add_subplot(1,2,i,projection='3d')
        cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        n=cross/np.maximum(np.linalg.norm(cross,axis=1)[:,None],1e-30)
        light=np.array([-.3,-.6,.74]); light/=np.linalg.norm(light)
        shade=.52+.48*np.maximum(n@light,0)
        colors=np.column_stack([shade*.26,shade*.65,shade*.86,np.ones(len(shade))])
        ax.add_collection3d(Poly3DCollection(triangles,facecolors=colors,linewidths=0,rasterized=True))
        ax.set(xlim=(centre[0]-radius,centre[0]+radius),ylim=(centre[1]-radius,centre[1]+radius),zlim=(centre[2]-radius,centre[2]+radius))
        ax.set_box_aspect([1,1,1]); ax.view_init(el,az); ax.set_axis_off(); ax.set_facecolor('#f3f6fa')
        ax.set_title('View '+str(i),color='#31465b')
    fig.suptitle('SO-101 fixed gripper + integrated camera mount\nSupplied official STL / geometry unchanged',fontsize=17,color='#20313e')
    fig.subplots_adjust(left=0,right=1,bottom=0,top=.85,wspace=0)
    fig.savefig(ROOT/'wrist_original_preview.png',dpi=150,facecolor=fig.get_facecolor())
    plt.close(fig)

if __name__=='__main__':
    mesh=read_mesh(); inspect(mesh); render(mesh)
