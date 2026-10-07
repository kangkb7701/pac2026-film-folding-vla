"""Inspect coincident source facets and sheets meeting at nonmanifold edges."""
import json
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from inspect_wrist_source import ROOT, read_mesh

triangles = read_mesh()
vertices, ix = np.unique(triangles.reshape(-1,3),axis=0,return_inverse=True)
faces = ix.reshape(-1,3)
_, keep = np.unique(np.sort(faces,axis=1),axis=0,return_index=True)
faces=faces[np.sort(keep)]
triangles=vertices[faces]
directed=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
owners=np.tile(np.arange(len(faces)),3)
edges,ei,ec=np.unique(np.sort(directed,axis=1),axis=0,return_inverse=True,return_counts=True)
order=np.argsort(ei)
starts=np.r_[0,np.cumsum(ec)[:-1]]
pairs=owners[order[starts[ec==2,None]+np.arange(2)]]
graph=coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(faces),len(faces))).tocsr()
n,labels=connected_components(graph,directed=False)
areas=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)/2
report=[]
for i in range(n):
    t=triangles[labels==i]
    v=np.unique(t.reshape(-1,3),axis=0)
    _,singular,_=np.linalg.svd(v-v.mean(axis=0),full_matrices=False)
    report.append({'component':i,'faces':len(t),'area':float(areas[labels==i].sum()),'bounds_min':v.min(axis=0).tolist(),'bounds_max':v.max(axis=0).tolist(),'singular_values':singular.tolist()})
print(json.dumps({'nonmanifold_edge_count':int(sum(ec>2)),'face_sheets':report},indent=2))
np.savez(ROOT/'wrist_source_sheets.npz',vertices=vertices,faces=faces,labels=labels)
import itertools
for bits in itertools.product([0,1],repeat=3):
    ids=[0,3]+[i for i,b in zip([1,2,4],bits) if b]
    ff=faces[np.isin(labels,ids)]
    e=np.concatenate([ff[:,[0,1]],ff[:,[1,2]],ff[:,[2,0]]])
    _,inv,c=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
    balance=np.bincount(inv,weights=np.where(e[:,0]<e[:,1],1,-1))
    t=vertices[ff]
    volume=np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6
    print(ids,'boundary',sum(c==1),'nonmanifold',sum(c>2),'winding',sum(balance!=0),'volume',round(volume,3))

# Analysis candidate only: the larger-volume of the two closed source-sheet variants.
# The original source is retained unmodified; no camera-specific fit is asserted.
candidate=vertices[faces[np.isin(labels,[0,2,3,4])]]
np.save(ROOT/'wrist_inspection_candidate.npy',candidate)
from inspect_wrist_source import inspect
inspect(candidate,'wrist_candidate_inspection.json')
