/**
 * Convert GLB files to USDZ using Three.js USDZExporter.
 * Usage: node convert_glb_to_usdz.mjs <input.glb> <output.usdz>
 */
import { readFileSync, writeFileSync, readdirSync } from 'fs';
import { join, basename } from 'path';

// Three.js imports
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { USDZExporter } from 'three/examples/jsm/exporters/USDZExporter.js';

// Polyfill for DOM APIs that Three.js needs in Node
globalThis.document = {
    createElementNS: () => ({ setAttribute: () => { }, style: {} }),
    createElement: () => ({ getContext: () => null, style: {} }),
};
globalThis.window = {
    addEventListener: () => { },
    removeEventListener: () => { },
    innerWidth: 1024,
    innerHeight: 768,
};
globalThis.self = globalThis;
globalThis.Image = class { };
globalThis.navigator = { userAgent: '' };
globalThis.HTMLCanvasElement = class { };

const MODELS_DIR = process.argv[2] || 'models';

async function convertGlbToUsdz(glbPath, usdzPath) {
    const data = readFileSync(glbPath);
    const arrayBuffer = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);

    return new Promise((resolve, reject) => {
        const loader = new GLTFLoader();
        loader.parse(arrayBuffer, '', async (gltf) => {
            try {
                const exporter = new USDZExporter();
                const result = await exporter.parse(gltf.scene);
                const buffer = Buffer.from(result);
                writeFileSync(usdzPath, buffer);
                console.log(`  ✅ ${basename(usdzPath)} (${(buffer.length / 1024 / 1024).toFixed(1)} MB)`);
                resolve(true);
            } catch (err) {
                console.log(`  ❌ Export failed: ${err.message}`);
                resolve(false);
            }
        }, (err) => {
            console.log(`  ❌ Parse failed: ${err.message || err}`);
            resolve(false);
        });
    });
}

async function main() {
    const files = readdirSync(MODELS_DIR).filter(f => f.endsWith('.glb')).sort();
    console.log(`📦 Converting ${files.length} GLB files to USDZ\n`);

    let success = 0;
    for (let i = 0; i < files.length; i++) {
        const glbFile = files[i];
        const usdzFile = glbFile.replace('.glb', '.usdz');
        const glbPath = join(MODELS_DIR, glbFile);
        const usdzPath = join(MODELS_DIR, usdzFile);

        const sizeMb = readFileSync(glbPath).length / 1024 / 1024;
        console.log(`[${i + 1}/${files.length}] ${glbFile} (${sizeMb.toFixed(1)} MB)`);

        if (await convertGlbToUsdz(glbPath, usdzPath)) {
            success++;
        }
    }

    console.log(`\n${'═'.repeat(50)}`);
    console.log(`✅ ${success}/${files.length} files converted`);
}

main().catch(console.error);
