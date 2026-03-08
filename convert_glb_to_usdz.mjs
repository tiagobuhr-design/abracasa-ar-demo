import puppeteer from 'puppeteer';
import fs from 'fs/promises';
import path from 'path';

async function convertGlbToUsdz(glbPath, usdzPath) {
    console.log(`Converting ${path.basename(glbPath)}...`);
    const browser = await puppeteer.launch({ headless: 'new' });
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

    const usdzUint8Array = await page.evaluate(async (glbDataArray) => {
        const arrayBuffer = new Uint8Array(glbDataArray).buffer;
        const dynamicLoader = new Function('moduleRoot', 'return import(moduleRoot);');

        const THREE = await dynamicLoader('three');
        const { GLTFLoader } = await dynamicLoader('three/addons/loaders/GLTFLoader.js');
        const { USDZExporter } = await dynamicLoader('three/addons/exporters/USDZExporter.js');

        return new Promise((resolve, reject) => {
            const loader = new GLTFLoader();
            loader.parse(arrayBuffer, '', (gltf) => {
                const newScene = new THREE.Scene();

                try {
                    gltf.scene.updateMatrixWorld(true);
                    const m100 = new THREE.Matrix4().makeScale(100, 100, 100);

                    gltf.scene.traverse((child) => {
                        if (child.isMesh) {
                            const worldMatrix = child.matrixWorld.clone();
                            worldMatrix.premultiply(m100);

                            const newGeometry = child.geometry.clone();
                            newGeometry.applyMatrix4(worldMatrix);

                            const flatMesh = new THREE.Mesh(newGeometry, child.material);
                            flatMesh.position.set(0, 0, 0);
                            flatMesh.quaternion.identity();
                            flatMesh.scale.set(1, 1, 1);
                            flatMesh.updateMatrix();

                            newScene.add(flatMesh);
                        }
                    });
                } catch (e) {
                    reject(e);
                    return;
                }

                const exporter = new USDZExporter();
                exporter.parse(newScene).then((usdzArrayBuffer) => {
                    resolve(Array.from(new Uint8Array(usdzArrayBuffer)));
                }).catch(reject);
            }, reject);
        });
    }, Array.from(glbData));

    await fs.writeFile(usdzPath, Buffer.from(usdzUint8Array));
    console.log(`✅ Saved ${path.basename(usdzPath)}`);

    await browser.close();
}

async function main() {
    try {
        const productsJson = await fs.readFile('products_with_dims.json', 'utf8');
        const products = JSON.parse(productsJson);

        for (const p of products) {
            if (!p.glb_path) continue;
            const glbPath = path.resolve(p.glb_path);
            const usdzPath = glbPath.replace(/\.glb$/i, '.usdz');

            try {
                await fs.access(glbPath);
                await convertGlbToUsdz(glbPath, usdzPath);
            } catch (e) {
                console.log(`Failed or skipped ${p.glb_path}: ${e.message}`);
            }
        }
    } catch (e) {
        console.error("Main error:", e);
    }
}

main();
