// Check the shipped HTML's STL parser and the adapter-to-STEP hole alignment.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'SO101_PiV2_assembly_viewer.html'), 'utf8');
const embedded = html.match(/<script id="embedded" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const core = script.split('const canvas=')[0];
const context = {
    document: {getElementById: id => ({textContent: embedded})},
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    TextDecoder,
};
vm.createContext(context);
const report = vm.runInContext(core + `
(()=>{
 const dims = data => [0,1,2].map(axis=>{
   let lo=Infinity,hi=-Infinity;
   for(let i=axis;i<data.length;i+=3){lo=Math.min(lo,data[i]);hi=Math.max(hi,data[i])}
   return hi-lo;
 });
 const reference = [
  [-59.8089086486528,-28.6035629842986,4],
  [-59.8089086486528,-28.6035629842986,31],
  [-35.3385983986633,-40.0142560512975,4],
  [-35.3385983986633,-40.0142560512975,31]];
 const calculated=[];for(const x of[-13.5,13.5])for(const y of[-13.5,13.5])calculated.push(cameraPose([x,y,0]));
 const errors=reference.map((p,i)=>Math.hypot(...rigid(p,bracketT,bracketR).map((v,j)=>v-calculated[i][j])));
 return {plateTriangles:meshData.plate.length/9,spacerTriangles:meshData.spacer.length/9,
         plateDimensions:dims(meshData.plate),spacerDimensions:dims(meshData.spacer),
         holeAlignmentMaxErrorMm:Math.max(...errors),
         coordinatesFinite:Object.values(meshData).every(data=>Array.from(data).every(Number.isFinite)),
         browserRenderingVerified:false,officialMeshesDownloaded:false};
})()`, context);
assert.strictEqual(report.plateTriangles, 3504);
assert.strictEqual(report.spacerTriangles, 768);
assert.strictEqual(JSON.stringify(report.plateDimensions), '[35,35,3]');
assert.strictEqual(JSON.stringify(report.spacerDimensions), '[5,5,5]');
assert(report.coordinatesFinite);
assert(report.holeAlignmentMaxErrorMm < 1e-8);
fs.writeFileSync(path.join(__dirname, 'viewer_validation.json'), JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
