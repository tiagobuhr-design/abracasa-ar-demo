import { NodeIO, getBounds } from '@gltf-transform/core';
import fs from 'fs';
import path from 'path';

const io = new NodeIO();

/**
 * Scale a GLB model to match EXACT real-world product dimensions.
 *
 * Uses NON-UNIFORM scaling: each axis (width, height, depth) is scaled
 * independently so the final model matches the product's centimeter
 * dimensions precisely. This compensates for the AI-generated model
 * having different proportions than the real product.
 *
 * Axis mapping (glTF standard):
 *   X = width (largura)
 *   Y = height (altura)
 *   Z = depth (profundidade)
 */
async function scaleModel(glbPath, targetWidthCm, targetHeightCm, targetDepthCm) {
    console.log(`\nProcessing ${glbPath}...`);
    try {
        const document = await io.read(glbPath);
        const scene = document.getRoot().getDefaultScene() || document.getRoot().listScenes()[0];
        const bbox = getBounds(scene);

        // Current dimensions in glTF units (may be arbitrary AI scale)
        const currentWidth  = bbox.max[0] - bbox.min[0]; // X
        const currentHeight = bbox.max[1] - bbox.min[1]; // Y
        const currentDepth  = bbox.max[2] - bbox.min[2]; // Z

        console.log(`  Current (glTF units): W=${currentWidth.toFixed(4)}, H=${currentHeight.toFixed(4)}, D=${currentDepth.toFixed(4)}`);

        // Target in meters
        const targetW = targetWidthCm / 100;
        const targetH = targetHeightCm / 100;
        const targetD = targetDepthCm / 100;

        console.log(`  Target (meters):      W=${targetW.toFixed(4)}, H=${targetH.toFixed(4)}, D=${targetD.toFixed(4)}`);

        // Compute per-axis scale factors
        const scaleX = targetW / currentWidth;
        const scaleY = targetH / currentHeight;
        const scaleZ = targetD / currentDepth;

        console.log(`  Scale factors:        X=${scaleX.toFixed(4)}, Y=${scaleY.toFixed(4)}, Z=${scaleZ.toFixed(4)}`);

        // Apply non-uniform scale to root node(s)
        const nodes = scene.listChildren();
        for (const node of nodes) {
            const currentScale = node.getScale();
            node.setScale([
                currentScale[0] * scaleX,
                currentScale[1] * scaleY,
                currentScale[2] * scaleZ
            ]);
        }

        // Save back
        const tempPath = glbPath.replace('.glb', '_temp.glb');
        await io.write(tempPath, document);
        fs.renameSync(tempPath, glbPath);

        // Verify the result
        const verifyDoc = await io.read(glbPath);
        const verifyScene = verifyDoc.getRoot().getDefaultScene() || verifyDoc.getRoot().listScenes()[0];
        const verifyBbox = getBounds(verifyScene);
        const finalW = verifyBbox.max[0] - verifyBbox.min[0];
        const finalH = verifyBbox.max[1] - verifyBbox.min[1];
        const finalD = verifyBbox.max[2] - verifyBbox.min[2];

        console.log(`  Final (meters):       W=${finalW.toFixed(4)}, H=${finalH.toFixed(4)}, D=${finalD.toFixed(4)}`);

        const errW = Math.abs(finalW - targetW) / targetW * 100;
        const errH = Math.abs(finalH - targetH) / targetH * 100;
        const errD = Math.abs(finalD - targetD) / targetD * 100;

        if (errW > 1 || errH > 1 || errD > 1) {
            console.log(`  ⚠️  Dimension error > 1%: W=${errW.toFixed(1)}%, H=${errH.toFixed(1)}%, D=${errD.toFixed(1)}%`);
        } else {
            console.log(`  ✅ All dimensions within 1% of target`);
        }

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
            console.log(`\nSkipping ${p.name}: No dimensions found.`);
            continue;
        }

        const filePath = path.join(process.cwd(), p.glb_path);
        if (fs.existsSync(filePath)) {
            await scaleModel(
                filePath,
                p.dimensions.width_cm,
                p.dimensions.height_cm,
                p.dimensions.depth_cm
            );
        } else {
            console.log(`\nModel not found: ${filePath}`);
        }
    }
}

main();
