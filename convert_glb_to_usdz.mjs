import puppeteer from 'puppeteer';
import fs from 'fs/promises';
import path from 'path';

/**
 * Convert a GLB to USDZ using Three.js USDZExporter in a headless browser.
 * - Bakes world matrices into vertex positions (no transform tricks)
 * - Anchors lowest Y to exactly 0 (furniture sits on floor)
 * - Preserves textures via Puppeteer WebGL context
 */
async function convertGlbToUsdz(glbPath, usdzPath) {
    console.log(`\nConverting ${path.basename(glbPath)}...`);
    const browser = await puppeteer.launch({ headless: 'new', protocolTimeout: 120000 });
    const page = await browser.newPage();

    const glbBuffer = await fs.readFile(glbPath);
    const glbData = new Uint8Array(glbBuffer.buffer, glbBuffer.byteOffset, glbBuffer.byteLength);

    await page.setContent(`<!DOCTYPE html><html><head>
        <script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
    </head><body></body></html>`);

    const result = await page.evaluate(async (glbDataArray) => {
        const arrayBuffer = new Uint8Array(glbDataArray).buffer;
        const load = (m) => new Function('m', 'return import(m)')(m);
        const THREE = await load('three');
        const { GLTFLoader } = await load('three/addons/loaders/GLTFLoader.js');
        const { USDZExporter } = await load('three/addons/exporters/USDZExporter.js');

        return new Promise((resolve, reject) => {
            new GLTFLoader().parse(arrayBuffer, '', (gltf) => {
                try {
                    const newScene = new THREE.Scene();
                    const diag = {};

                    // Bake world matrices into vertices
                    gltf.scene.updateMatrixWorld(true);
                    const ob = new THREE.Box3().setFromObject(gltf.scene);
                    diag.orig = { w: ob.max.x-ob.min.x, h: ob.max.y-ob.min.y, d: ob.max.z-ob.min.z };

                    let mc = 0;
                    gltf.scene.traverse((c) => {
                        if (c.isMesh) {
                            mc++;
                            const g = c.geometry.clone();
                            g.applyMatrix4(c.matrixWorld.clone());
                            const m = new THREE.Mesh(g, c.material);
                            m.position.set(0,0,0);
                            m.quaternion.identity();
                            m.scale.set(1,1,1);
                            m.updateMatrix();
                            newScene.add(m);
                        }
                    });
                    diag.meshes = mc;

                    // Floor anchor: translate so lowest Y = 0
                    const bb = new THREE.Box3().setFromObject(newScene);
                    const ly = bb.min.y;
                    diag.lowestY = ly;
                    newScene.traverse((c) => {
                        if (c.isMesh) c.geometry.translate(0, -ly, 0);
                    });

                    // Final bounds
                    const fb = new THREE.Box3().setFromObject(newScene);
                    diag.final = {
                        w: fb.max.x-fb.min.x, h: fb.max.y-fb.min.y, d: fb.max.z-fb.min.z,
                        minY: fb.min.y, maxY: fb.max.y
                    };

                    new USDZExporter().parse(newScene).then((usdz) => {
                        resolve({ data: Array.from(new Uint8Array(usdz)), diag });
                    }).catch(reject);
                } catch(e) { reject(e); }
            }, reject);
        });
    }, Array.from(glbData));

    const d = result.diag;
    console.log(`  Meshes: ${d.meshes}`);
    console.log(`  Original: W=${d.orig.w.toFixed(4)}m  H=${d.orig.h.toFixed(4)}m  D=${d.orig.d.toFixed(4)}m`);
    console.log(`  Floor offset: ${d.lowestY.toFixed(4)}m`);
    console.log(`  Final USDZ: W=${d.final.w.toFixed(4)}m  H=${d.final.h.toFixed(4)}m  D=${d.final.d.toFixed(4)}m`);
    console.log(`  Y range: ${d.final.minY.toFixed(4)} to ${d.final.maxY.toFixed(4)}`);

    await fs.writeFile(usdzPath, Buffer.from(result.data));
    const mb = (result.data.length / 1024 / 1024).toFixed(1);
    console.log(`  ✅ Saved ${path.basename(usdzPath)} (${mb} MB)`);

    await browser.close();
}

async function main() {
    const args = process.argv.slice(2);
    let files = [];

    if (args.length > 0) {
        for (const a of args) {
            files.push({ glb: path.resolve(a), usdz: path.resolve(a).replace(/\.glb$/i, '.usdz') });
        }
    } else {
        const products = JSON.parse(await fs.readFile('products.json', 'utf8'));
        for (const p of products) {
            if (!p.glb_path) continue;
            files.push({ glb: path.resolve(p.glb_path), usdz: path.resolve(p.glb_path).replace(/\.glb$/i, '.usdz') });
        }
    }

    console.log(`\n📦 Converting ${files.length} GLB → USDZ\n${'═'.repeat(50)}`);
    let ok = 0;
    for (const f of files) {
        try {
            await fs.access(f.glb);
            await convertGlbToUsdz(f.glb, f.usdz);
            ok++;
        } catch(e) { console.log(`  ❌ ${e.message}`); }
        console.log('─'.repeat(50));
    }
    console.log(`\n${'═'.repeat(50)}\n✅ ${ok}/${files.length} converted`);
}

main();
