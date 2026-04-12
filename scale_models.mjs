import { NodeIO, getBounds } from '@gltf-transform/core';
import fs from 'fs';
import path from 'path';

const io = new NodeIO();

/**
 * Apply non-uniform 3-axis scaling so each axis (W/H/D) matches
 * the real product dimensions exactly.
 */
async function scaleModel(glbPath, targetWidthCm, targetHeightCm, targetDepthCm) {
    console.log(`\nScaling ${path.basename(glbPath)}...`);
    const document = await io.read(glbPath);
    const scene = document.getRoot().getDefaultScene() || document.getRoot().listScenes()[0];
    const bbox = getBounds(scene);

    const cw = bbox.max[0] - bbox.min[0]; // X = width
    const ch = bbox.max[1] - bbox.min[1]; // Y = height
    const cd = bbox.max[2] - bbox.min[2]; // Z = depth

    const tw = targetWidthCm / 100;
    const th = targetHeightCm / 100;
    const td = targetDepthCm / 100;

    console.log(`  Current: W=${(cw*100).toFixed(1)}cm  H=${(ch*100).toFixed(1)}cm  D=${(cd*100).toFixed(1)}cm`);
    console.log(`  Target:  W=${targetWidthCm}cm  H=${targetHeightCm}cm  D=${targetDepthCm}cm`);

    const sx = tw / cw;
    const sy = th / ch;
    const sz = td / cd;

    for (const node of scene.listChildren()) {
        const s = node.getScale();
        node.setScale([s[0] * sx, s[1] * sy, s[2] * sz]);
    }

    const tmp = glbPath.replace('.glb', '_tmp.glb');
    await io.write(tmp, document);
    fs.renameSync(tmp, glbPath);

    // Verify
    const vDoc = await io.read(glbPath);
    const vScene = vDoc.getRoot().getDefaultScene() || vDoc.getRoot().listScenes()[0];
    const vb = getBounds(vScene);
    const fw = vb.max[0] - vb.min[0];
    const fh = vb.max[1] - vb.min[1];
    const fd = vb.max[2] - vb.min[2];
    console.log(`  Result:  W=${(fw*100).toFixed(1)}cm  H=${(fh*100).toFixed(1)}cm  D=${(fd*100).toFixed(1)}cm  ✅`);
}

async function main() {
    const products = JSON.parse(fs.readFileSync('products.json', 'utf8'));
    for (const p of products) {
        if (!p.glb_path || !p.dimensions) continue;
        const fp = path.resolve(p.glb_path);
        if (!fs.existsSync(fp)) { console.log(`\nSkipping ${p.name}: file not found`); continue; }
        await scaleModel(fp, p.dimensions.width_cm, p.dimensions.height_cm, p.dimensions.depth_cm);
    }
}

main();
