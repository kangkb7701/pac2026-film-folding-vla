"""Generate a dimension-based SO101/Pi Camera V2 adapter prototype in millimetres.

Requires numpy, scipy and matplotlib. Does not depend on a CAD installation.
The SO101 wrist bracket itself must be obtained from TheRobotStudio.
"""
from pathlib import Path
import json
import os
import struct
from collections import Counter, defaultdict

import numpy as np
from scipy.spatial import Delaunay
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent / '.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

OUT = Path(__file__).resolve().parent
N = 96
OUTER_PITCH = 27.0
PI_PITCH = (21.0, 12.5)
HOLE_D = 2.2
PLATE_SIZE = 35.0
PLATE_H = 3.0
RELIEF_D = 18.0
SPACER_OD = 5.0
SPACER_H = 5.0


def circle(center, radius):
    angles = np.arange(N) * 2 * np.pi / N
    return np.asarray(center) + radius * np.column_stack((np.cos(angles), np.sin(angles)))


def hole_centres(px, py):
    return [(x, y) for x in (-px / 2, px / 2) for y in (-py / 2, py / 2)]


def extrude(outer, holes, height):
    loops = [outer] + [circle(c, r) for c, r in holes]
    points = np.concatenate(loops)
    triangulation = Delaunay(points)
    kept = []
    for triangle in triangulation.simplices:
        midpoint = points[triangle].mean(axis=0)
        if any(np.linalg.norm(midpoint - c) < r * np.cos(np.pi / N) for c, r in holes):
            continue
        a, b, c = points[triangle]
        if np.linalg.det(np.array([b-a, c-a])) < 0:
            triangle = triangle[[0, 2, 1]]
        kept.append(tuple(int(v) for v in triangle))
    boundary = Counter(tuple(sorted((a, b))) for t in kept for a, b in zip(t, t[1:] + t[:1]))
    actual_boundary = {edge for edge, count in boundary.items() if count == 1}
    expected_boundary = set()
    offset = 0
    for loop in loops:
        for i in range(len(loop)):
            expected_boundary.add(tuple(sorted((offset+i, offset+(i+1) % len(loop)))))
        offset += len(loop)
    assert actual_boundary == expected_boundary, 'Triangulation did not preserve the hole loops'
    n = len(points)
    vertices = np.concatenate((np.column_stack((points, np.zeros(n))),
                               np.column_stack((points, np.full(n, height)))))
    faces = []
    for a, b, c in kept:
        faces += [(a, c, b), (a+n, b+n, c+n)]
        for u, v in ((a, b), (b, c), (c, a)):
            if boundary[tuple(sorted((u, v)))] == 1:
                faces += [(u, v, v+n), (u, v+n, u+n)]
    return vertices, np.asarray(faces)


def write_stl(path, vertices, faces):
    triangles = vertices[faces].astype(np.float32)
    normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    with path.open('wb') as f:
        f.write(b'SO101 Pi Camera V2 adapter prototype; units mm'.ljust(80, b' '))
        f.write(struct.pack('<I', len(triangles)))
        for normal, triangle in zip(normals, triangles):
            f.write(struct.pack('<12fH', *normal, *triangle.ravel(), 0))


def validate_stl(path, expected_volume, expected_bounds):
    """Validate exported float32 STL, including watertightness and connectedness."""
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + count * 50
    triangles = np.array([struct.unpack_from('<12fH', data, 84+i*50)[3:12]
                          for i in range(count)]).reshape(-1, 3, 3)
    assert np.isfinite(triangles).all()
    vertices, indices = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = indices.reshape(-1, 3)
    edge_counts = Counter()
    edge_winding = Counter()
    adjacency = defaultdict(set)
    for t in faces:
        for a, b in zip(t, np.roll(t, -1)):
            key = tuple(sorted((int(a), int(b))))
            edge_counts[key] += 1
            edge_winding[key] += 1 if a < b else -1
            adjacency[int(a)].add(int(b))
            adjacency[int(b)].add(int(a))
    assert set(edge_counts.values()) == {2}, 'STL is not watertight'
    assert set(edge_winding.values()) == {0}, 'STL has inconsistent face winding'
    unseen = set(range(len(vertices)))
    components = 0
    while unseen:
        components += 1
        todo = [unseen.pop()]
        while todo:
            node = todo.pop()
            for neighbor in adjacency[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    todo.append(neighbor)
    assert components == 1
    crosses = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    assert (np.linalg.norm(crosses, axis=1) > 1e-8).all()
    volume = float(np.einsum('ij,ij->i', triangles[:, 0],
                            np.cross(triangles[:, 1], triangles[:, 2])).sum()/6)
    assert volume > 0
    assert abs(volume-expected_volume) / expected_volume < 1e-6
    bounds = vertices.max(axis=0)-vertices.min(axis=0)
    assert np.allclose(bounds, expected_bounds, atol=1e-5)
    return {'triangles': count, 'vertices': len(vertices), 'watertight': True,
            'consistent_winding': True, 'connected_components': components,
            'volume_mm3': round(volume, 4), 'bounding_box_mm': bounds.tolist(),
            'physical_fit_tested': False}


def polygon_area(loop):
    return abs(np.sum(loop[:, 0]*np.roll(loop[:, 1], -1)
                      - loop[:, 1]*np.roll(loop[:, 0], -1)))/2


def main():
    mounting = hole_centres(OUTER_PITCH, OUTER_PITCH)
    pi = hole_centres(*PI_PITCH)
    half = PLATE_SIZE/2
    outer = np.array([[-half, -half], [half, -half], [half, half], [-half, half]])
    holes = [(np.array(c), HOLE_D/2) for c in mounting+pi]
    holes += [(np.zeros(2), RELIEF_D/2)]
    vertices, faces = extrude(outer, holes, PLATE_H)
    plate = OUT/'SO101_PiCameraV2_adapter_27mm_v0.1.stl'
    write_stl(plate, vertices, faces)
    plate_volume = (polygon_area(outer)-sum(polygon_area(circle(c, r)) for c, r in holes))*PLATE_H
    report = {plate.name: validate_stl(plate, plate_volume, [PLATE_SIZE, PLATE_SIZE, PLATE_H])}
    spacer_outer = circle((0, 0), SPACER_OD/2)
    spacer_holes = [(np.zeros(2), HOLE_D/2)]
    vertices, faces = extrude(spacer_outer, spacer_holes, SPACER_H)
    spacer = OUT/'M2_spacer_5mm_v0.1.stl'
    write_stl(spacer, vertices, faces)
    spacer_volume = (polygon_area(spacer_outer)-polygon_area(circle((0, 0), HOLE_D/2)))*SPACER_H
    report[spacer.name] = validate_stl(spacer, spacer_volume, [SPACER_OD, SPACER_OD, SPACER_H])
    parameters = {'units': 'mm', 'status': 'dimensional prototype; physical fit not tested',
                  'plate_size': [PLATE_SIZE, PLATE_SIZE, PLATE_H],
                  'bracket_hole_pitch': [OUTER_PITCH, OUTER_PITCH],
                  'camera_hole_pitch': list(PI_PITCH), 'through_hole_diameter': HOLE_D,
                  'relief_diameter': RELIEF_D,
                  'spacer_size': {'height': SPACER_H, 'outer_diameter': SPACER_OD, 'inner_diameter': HOLE_D},
                  'bracket_hole_centres': mounting, 'camera_hole_centres': pi,
                  'sources': [
                      'https://datasheets.raspberrypi.com/camera/camera-module-2-mechanical-drawing.pdf',
                      'https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/Optional/SO101_Wrist_Cam_Hex-Nut_Mount_32x32_UVC_Module/stl/SO-ARM101_camera_wrist_mount.step']}
    (OUT/'dimensions.json').write_text(json.dumps(parameters, indent=2), encoding='utf-8')
    (OUT/'mesh_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    preview(mounting, pi)
    print(json.dumps(report, indent=2))


def preview(mounting, pi):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw={'width_ratios': [1.4, 1]})
    ax = axes[0]
    ax.add_patch(Rectangle((-17.5, -17.5), 35, 35, facecolor='#d8e3eb', edgecolor='#233d4d', lw=2))
    ax.add_patch(Circle((0, 0), RELIEF_D/2, facecolor='white', edgecolor='#233d4d'))
    for points, color in ((mounting, '#247ba0'), (pi, '#e76f51')):
        for x, y in points:
            ax.add_patch(Circle((x, y), HOLE_D/2, facecolor='white', edgecolor=color, lw=2))
            ax.plot(x, y, '+', color=color, markersize=5)
    for y, xleft, xright, label, color in ((20, -13.5, 13.5, '27 mm: SO101 bracket', '#247ba0'),
                                           (-20, -10.5, 10.5, '21 mm: Pi Camera V2', '#e76f51')):
        ax.annotate('', (xright, y), (xleft, y), arrowprops={'arrowstyle': '<->', 'color': color})
        ax.text(0, y+(1.5 if y > 0 else -2.5), label, ha='center', color=color)
    ax.annotate('', (-22, 6.25), (-22, -6.25), arrowprops={'arrowstyle': '<->', 'color': '#e76f51'})
    ax.text(-24, 0, '12.5 mm', va='center', rotation=90, color='#e76f51')
    ax.text(0, 0, '18 mm relief', ha='center', va='center', fontsize=10)
    ax.set(xlim=(-28, 27), ylim=(-25, 26), aspect='equal', title='Adapter plate: 35 x 35 x 3 mm')
    ax.axis('off')
    ax = axes[1]
    ax.axis('off')
    ax.set_title('Side view / assembly order')
    # Schematic side view, not a rendering of the original wrist bracket.
    for x, width, y, height, color, text, label_y in (
        (0.06, .13, .17, .60, '#247ba0', 'Official SO101\nhex-nut bracket', .07),
        (.29, .10, .17, .60, '#a6bdcc', '3 mm adapter\n(print 1)', .88),
        (.47, .16, .39, .15, '#666666', '5 mm spacers\n(print 4)', .29),
        (.73, .04, .24, .47, '#468b58', 'Pi Camera V2\nPCB', .88),
        (.77, .17, .42, .12, '#333333', 'Lens faces\noutward', .64)):
        ax.add_patch(Rectangle((x, y), width, height, facecolor=color, transform=ax.transAxes))
        ax.text(x+width/2, label_y, text, transform=ax.transAxes,
                ha='center', va='center', fontsize=8.5)
    ax.text(.5, -.02, 'M2 through holes: nominal 2.2 mm\nDimensional prototype: physical fit not tested',
            transform=ax.transAxes, ha='center', fontsize=10)
    fig.suptitle('SO101 wrist + Raspberry Pi Camera Module V2', fontsize=15)
    fig.tight_layout()
    fig.savefig(OUT/'adapter_preview.png', dpi=170, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
