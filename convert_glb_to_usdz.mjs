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

        // Hide dynamic imports from Node.js explicit parser
        const dynamicLoader = new Function('moduleRoot', 'return import(moduleRoot);');

        const THREE = await dynamicLoader('three');
        const { GLTFLoader } = await dynamicLoader('three/addons/loaders/GLTFLoader.js');
        const { USDZExporter } = await dynamicLoader('three/addons/exporters/USDZExporter.js');

        return new Promise((resolve, reject) => {
            const loader = new GLTFLoader();
            loader.parse(arrayBuffer, '', (gltf) => {
                // Apple AR Quick Look assumes USDZ units are Centimeters
                // Our glTF models are correctly scaled in Meters.
                // We must scale the root scene by 100x so 2.2m becomes 220cm.
                gltf.scene.scale.set(100, 100, 100);

                const exporter = new USDZExporter();
                exporter.parse(gltf.scene).then((usdzArrayBuffer) => {
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
