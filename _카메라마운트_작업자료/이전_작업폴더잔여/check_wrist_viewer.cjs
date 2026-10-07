const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const root = __dirname;
const html = fs.readFileSync(path.join(root, 'SO101_integrated_gripper_viewer.html'), 'utf8');
for (const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(m[1]);
const data = JSON.parse(html.match(/<script id="mesh" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const bytes = Buffer.from(data.data, 'base64');
assert.equal(bytes.length, data.vertexCount * 24);
const source = fs.readFileSync(path.join(root, 'sources/Wrist_Cam_Mount_32x32_UVC_Module_SO101.stl'), 'ascii');
const points = [...source.matchAll(/vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)/g)];
assert.equal(points.length, data.vertexCount);
for (let i = 0; i < points.length; i++) {
  for (let axis = 0; axis < 3; axis++) assert.equal(bytes.readFloatLE(i * 24 + axis * 4), Math.fround(Number(points[i][axis + 1])));
  const n = [0, 1, 2].map(axis => bytes.readFloatLE(i * 24 + 12 + axis * 4));
  assert.ok(Math.abs(Math.hypot(...n) - 1) < 1e-6);
}
fs.writeFileSync(path.join(root, 'wrist_viewer_validation.json'), JSON.stringify({javascript_syntax:'passed',embedded_vertices_match_original_stl:'passed',normal_lengths:'passed',vertex_count:points.length,browser_render_tested:false},null,2));
console.log('JavaScript syntax, all embedded STL vertices, and normals passed. Browser rendering not tested.');
