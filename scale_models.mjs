import { Document, NodeIO, getBounds } from '@gltf-transform/core';
import fs from 'fs';
import path from 'path';

const io = new NodeIO();

async function scaleModel(glbPath, targetWidthCm) {
    console.log(`\nProcessing ${glbPath}...`);
    try {
        const document = await io.read(glbPath);

        // Calculate the bounding box of the whole scene
        const scene = document.getRoot().getDefaultScene() || document.getRoot().listScenes()[0];
        const bbox = getBounds(scene);

        // Dimensions in meters (glTF units)
        const currentWidth = bbox.max[0] - bbox.min[0];
        const currentHeight = bbox.max[1] - bbox.min[1];
        const currentDepth = bbox.max[2] - bbox.min[2];

        console.log(`  Current Size (m): Width=${currentWidth.toFixed(3)}, Height=${currentHeight.toFixed(3)}, Depth=${currentDepth.toFixed(3)}`);

        const targetWidthM = targetWidthCm / 100;
        const maxHorizontal = Math.max(currentWidth, currentDepth);
        const scaleFactor = targetWidthM / maxHorizontal;

        console.log(`  Target Width (m): ${targetWidthM.toFixed(3)}`);
        console.log(`  Scale Factor ( usando eixo horizontal máximo ): ${scaleFactor.toFixed(4)}`);

        // Apply uniform scale to the root node(s)
        const nodes = scene.listChildren();
        for (const node of nodes) {
            const currentScale = node.getScale();
            node.setScale([
                currentScale[0] * scaleFactor,
                currentScale[1] * scaleFactor,
                currentScale[2] * scaleFactor
            ]);
        }

        // Save back to the same file (overwrite)
        const tempPath = glbPath.replace('.glb', '_temp.glb');
        await io.write(tempPath, document);
        fs.renameSync(tempPath, glbPath);

        console.log(`  ✅ Scaled and saved.`);
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
            await scaleModel(filePath, p.dimensions.width_cm);
        } else {
            console.log(`\nModel not found: ${filePath}`);
        }
    }
}

main();
