import { NodeIO, getBounds } from '@gltf-transform/core';
import fs from 'fs';
import path from 'path';

const io = new NodeIO();

/**
 * Apply non-uniform 3-axis scaling to match exact product dimensions.
 * Only scales models that are off by more than 5% on any axis.
 */
async function scaleModel(glbPath, targetWidthCm, targetHeightCm, targetDepthCm) {
    console.log(`\nProcessing ${path.basename(glbPath)}...`);
    try {
        const document = await io.read(glbPath);
        const scene = document.getRoot().getDefaultScene() || document.getRoot().listScenes()[0];
        const bbox = getBounds(scene);

        const currentWidth  = bbox.max[0] - bbox.min[0]; // X
        const currentHeight = bbox.max[1] - bbox.min[1]; // Y
        const currentDepth  = bbox.max[2] - bbox.min[2]; // Z

        const targetW = targetWidthCm / 100;
        const targetH = targetHeightCm / 100;
        const targetD = targetDepthCm / 100;

        console.log(`  Current: W=${(currentWidth*100).toFixed(1)}cm, H=${(currentHeight*100).toFixed(1)}cm, D=${(currentDepth*100).toFixed(1)}cm`);
        console.log(`  Target:  W=${targetWidthCm}cm, H=${targetHeightCm}cm, D=${targetDepthCm}cm`);

        const errW = Math.abs(currentWidth - targetW) / targetW * 100;
        const errH = Math.abs(currentHeight - targetH) / targetH * 100;
        const errD = Math.abs(currentDepth - targetD) / targetD * 100;

        if (errW < 5 && errH < 5 && errD < 5) {
            console.log(`  ✅ Already within 5% — skipping (W:${errW.toFixed(1)}%, H:${errH.toFixed(1)}%, D:${errD.toFixed(1)}%)`);
            return true;
        }

        console.log(`  ⚠️  Needs scaling (W:${errW.toFixed(1)}%, H:${errH.toFixed(1)}%, D:${errD.toFixed(1)}%)`);

        const scaleX = targetW / currentWidth;
        const scaleY = targetH / currentHeight;
        const scaleZ = targetD / currentDepth;

        console.log(`  Scale factors: X=${scaleX.toFixed(4)}, Y=${scaleY.toFixed(4)}, Z=${scaleZ.toFixed(4)}`);

        const nodes = scene.listChildren();
        for (const node of nodes) {
            const s = node.getScale();
            node.setScale([s[0] * scaleX, s[1] * scaleY, s[2] * scaleZ]);
        }

        const tempPath = glbPath.replace('.glb', '_temp.glb');
        await io.write(tempPath, document);
        fs.renameSync(tempPath, glbPath);

        // Verify
        const verifyDoc = await io.read(glbPath);
        const verifyScene = verifyDoc.getRoot().getDefaultScene() || verifyDoc.getRoot().listScenes()[0];
        const vb = getBounds(verifyScene);
        const fw = vb.max[0] - vb.min[0];
        const fh = vb.max[1] - vb.min[1];
        const fd = vb.max[2] - vb.min[2];
        console.log(`  Result:  W=${(fw*100).toFixed(1)}cm, H=${(fh*100).toFixed(1)}cm, D=${(fd*100).toFixed(1)}cm`);
        console.log(`  ✅ Scaled successfully`);

        return true;
    } catch (e) {
        console.error(`  ❌ Error: ${e.message}`);
        return false;
    }
}

async function main() {
    const productsData = JSON.parse(fs.readFileSync('products_with_dims.json', 'utf8'));

    for (const p of productsData) {
        if (!p.dimensions || !p.dimensions.width_cm) {
            console.log(`\nSkipping ${p.name}: No dimensions.`);
            continue;
        }

        const filePath = path.join(process.cwd(), p.glb_path);
        if (!fs.existsSync(filePath)) {
            console.log(`\nModel not found: ${filePath}`);
            continue;
        }

        await scaleModel(
            filePath,
            p.dimensions.width_cm,
            p.dimensions.height_cm,
            p.dimensions.depth_cm
        );
    }
}

main();
