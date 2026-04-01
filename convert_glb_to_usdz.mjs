import puppeteer from 'puppeteer';
import fs from 'fs/promises';
import path from 'path';

async function convertGlbToUsdz(glbPath, usdzPath) {
    console.log(`\nConverting ${path.basename(glbPath)}...`);
    const browser = await puppeteer.launch({ headless: 'new', protocolTimeout: 120000 });
    const page = await browser.newPage();

    const glbBuffer = await fs.readFile(glbPath);
    const glbData = new Uint8Array(glbBuffer.buffer, glbBuffer.byteOffset, glbBuffer.byteLength);

    await page.setContent(`
        <!DOCTYPE html>
        <html>
            <head>
                <script type="importmap">
                    {
                        "imports": {
                            "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
                            "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
                        }
                    }
                </script>
            </head>
            <body></body>
        </html>
    `);

    const result = await page.evaluate(async (glbDataArray) => {
        const arrayBuffer = new Uint8Array(glbDataArray).buffer;
        const dynamicLoader = new Function('moduleRoot', 'return import(moduleRoot);');

        const THREE = await dynamicLoader('three');
        const { GLTFLoader } = await dynamicLoader('three/addons/loaders/GLTFLoader.js');
        const { USDZExporter } = await dynamicLoader('three/addons/exporters/USDZExporter.js');

        return new Promise((resolve, reject) => {
            const loader = new GLTFLoader();
            loader.parse(arrayBuffer, '', (gltf) => {
                const newScene = new THREE.Scene();
                const diagnostics = {};

                try {
                    // Step 1: Compute world matrices for the entire scene hierarchy.
                    // This ensures all transforms (position, rotation, scale) from
                    // parent nodes are propagated down to each mesh's matrixWorld.
                    gltf.scene.updateMatrixWorld(true);

                    // Measure the ORIGINAL scene bounds BEFORE any modification
                    const origBbox = new THREE.Box3().setFromObject(gltf.scene);
                    diagnostics.originalBounds = {
                        min: [origBbox.min.x, origBbox.min.y, origBbox.min.z],
                        max: [origBbox.max.x, origBbox.max.y, origBbox.max.z],
                        width: origBbox.max.x - origBbox.min.x,
                        height: origBbox.max.y - origBbox.min.y,
                        depth: origBbox.max.z - origBbox.min.z,
                    };

                    // Step 2: Flatten the node hierarchy by baking each mesh's
                    // worldMatrix directly into its geometry vertices.
                    //
                    // WHY: The USDZExporter writes both geometry vertices AND per-mesh
                    // transforms. By baking worldMatrix into vertices, we ensure the
                    // scale from scale_models.mjs (which sets node.scale) is included
                    // in the final USDZ coordinates. We then set the mesh transform to
                    // identity so there's no double-counting.
                    //
                    // IMPORTANT: We do NOT multiply by 100. The USDZExporter writes
                    // metersPerUnit = 1, meaning 1 unit = 1 meter. Our GLB models are
                    // already scaled in meters by scale_models.mjs.

                    let meshCount = 0;
                    gltf.scene.traverse((child) => {
                        if (child.isMesh) {
                            meshCount++;
                            const worldMatrix = child.matrixWorld.clone();

                            const newGeometry = child.geometry.clone();
                            newGeometry.applyMatrix4(worldMatrix);

                            const flatMesh = new THREE.Mesh(newGeometry, child.material);
                            // Identity transform — all scale/position is now in the vertices
                            flatMesh.position.set(0, 0, 0);
                            flatMesh.quaternion.identity();
                            flatMesh.scale.set(1, 1, 1);
                            flatMesh.updateMatrix();

                            newScene.add(flatMesh);
                        }
                    });
                    diagnostics.meshCount = meshCount;

                    // Step 3: Floor anchoring
                    // Apple AR Quick Look places the USDZ model's origin (0,0,0) on
                    // the detected floor. If the lowest vertex is at Y = -0.53, the
                    // bottom half of the furniture will be below the floor, and AR Quick
                    // Look will raise the entire model to compensate — making it float.
                    //
                    // Fix: translate ALL geometry so the lowest point is exactly at Y=0.
                    // We modify the geometry buffer directly (not mesh.position), because
                    // the USDZExporter reads vertex positions from the geometry buffer.
                    const bbox = new THREE.Box3().setFromObject(newScene);
                    const lowestY = bbox.min.y;
                    diagnostics.lowestY = lowestY;

                    // Step 4: Floor anchoring — translate so lowest point is at Y=0
                    newScene.traverse((child) => {
                        if (child.isMesh) {
                            child.geometry.translate(0, -lowestY, 0);
                        }
                    });

                    // Final verification: measure the output scene bounds
                    const finalBbox = new THREE.Box3().setFromObject(newScene);
                    diagnostics.finalBounds = {
                        min: [finalBbox.min.x, finalBbox.min.y, finalBbox.min.z],
                        max: [finalBbox.max.x, finalBbox.max.y, finalBbox.max.z],
                        width: finalBbox.max.x - finalBbox.min.x,
                        height: finalBbox.max.y - finalBbox.min.y,
                        depth: finalBbox.max.z - finalBbox.min.z,
                    };

                } catch (e) {
                    reject(e);
                    return;
                }

                const exporter = new USDZExporter();
                exporter.parse(newScene).then((usdzArrayBuffer) => {
                    resolve({
                        data: Array.from(new Uint8Array(usdzArrayBuffer)),
                        diagnostics
                    });
                }).catch(reject);
            }, reject);
        });
    }, Array.from(glbData));

    // Print diagnostics
    const d = result.diagnostics;
    console.log(`  Meshes: ${d.meshCount}`);
    console.log(`  Original bounds (meters):`);
    console.log(`    Width:  ${d.originalBounds.width.toFixed(4)}`);
    console.log(`    Height: ${d.originalBounds.height.toFixed(4)}`);
    console.log(`    Depth:  ${d.originalBounds.depth.toFixed(4)}`);
    console.log(`  Floor offset (lowestY): ${d.lowestY.toFixed(4)}`);
    console.log(`  Final USDZ bounds (meters):`);
    console.log(`    Width:  ${d.finalBounds.width.toFixed(4)}`);
    console.log(`    Height: ${d.finalBounds.height.toFixed(4)}`);
    console.log(`    Depth:  ${d.finalBounds.depth.toFixed(4)}`);
    console.log(`    Y range: ${d.finalBounds.min[1].toFixed(4)} to ${d.finalBounds.max[1].toFixed(4)}`);

    await fs.writeFile(usdzPath, Buffer.from(result.data));
    const fileSizeMb = (result.data.length / 1024 / 1024).toFixed(1);
    console.log(`  ✅ Saved ${path.basename(usdzPath)} (${fileSizeMb} MB)`);

    await browser.close();
    return d;
}

async function main() {
    try {
        const args = process.argv.slice(2);
        let filesToConvert = [];

        if (args.length > 0) {
            // Convert specific files passed as arguments
            for (const argPath of args) {
                const glbPath = path.resolve(argPath);
                const usdzPath = glbPath.replace(/\.glb$/i, '.usdz');
                filesToConvert.push({ glbPath, usdzPath });
            }
        } else {
            // Convert all files from products_with_dims.json
            const productsJson = await fs.readFile('products_with_dims.json', 'utf8');
            const products = JSON.parse(productsJson);

            for (const p of products) {
                if (!p.glb_path) continue;
                const glbPath = path.resolve(p.glb_path);
                const usdzPath = glbPath.replace(/\.glb$/i, '.usdz');
                filesToConvert.push({ glbPath, usdzPath, product: p });
            }
        }

        console.log(`\n📦 Converting ${filesToConvert.length} GLB files to USDZ\n`);
        console.log(`${'═'.repeat(60)}`);

        let success = 0;
        for (const { glbPath, usdzPath, product } of filesToConvert) {
            try {
                await fs.access(glbPath);
                const d = await convertGlbToUsdz(glbPath, usdzPath);

                // Cross-reference with product dimensions if available
                if (product && product.dimensions) {
                    const targetW = product.dimensions.width_cm / 100;
                    const actualMax = Math.max(d.finalBounds.width, d.finalBounds.depth);
                    const pctError = Math.abs(actualMax - targetW) / targetW * 100;
                    console.log(`  📏 Target: ${product.dimensions.width_cm}cm = ${targetW.toFixed(3)}m`);
                    console.log(`  📏 Actual max horizontal: ${actualMax.toFixed(3)}m`);
                    console.log(`  📏 Error: ${pctError.toFixed(1)}%`);
                    if (pctError > 5) {
                        console.log(`  ⚠️  WARNING: Size error exceeds 5%!`);
                    }
                }
                success++;
            } catch (e) {
                console.log(`  ❌ Failed: ${e.message}`);
            }
            console.log(`${'─'.repeat(60)}`);
        }

        console.log(`\n${'═'.repeat(60)}`);
        console.log(`✅ ${success}/${filesToConvert.length} files converted`);
    } catch (e) {
        console.error("Main error:", e);
    }
}

main();
