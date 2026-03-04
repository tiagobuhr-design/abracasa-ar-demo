#!/usr/bin/env python3
"""
Convert GLB files to USDZ using trimesh + usd-core.
Creates USDZ files needed for iOS AR Quick Look.
"""
import os
import sys
import trimesh

MODELS_DIR = "models"

def convert_glb_to_usdz(glb_path, usdz_path):
    """Convert a single GLB to USDZ."""
    try:
        scene = trimesh.load(glb_path)
        scene.export(usdz_path, file_type='usdz')
        size_mb = os.path.getsize(usdz_path) / 1024 / 1024
        print(f"  ✅ Saved ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    glb_files = sorted([f for f in os.listdir(MODELS_DIR) if f.endswith('.glb')])
    print(f"📦 Converting {len(glb_files)} GLB files to USDZ\n")

    success = 0
    for i, glb_file in enumerate(glb_files, 1):
        glb_path = os.path.join(MODELS_DIR, glb_file)
        usdz_file = glb_file.replace('.glb', '.usdz')
        usdz_path = os.path.join(MODELS_DIR, usdz_file)

        if os.path.exists(usdz_path):
            print(f"[{i}/{len(glb_files)}] ⏭️  {usdz_file} exists, skipping")
            success += 1
            continue

        size_mb = os.path.getsize(glb_path) / 1024 / 1024
        print(f"[{i}/{len(glb_files)}] {glb_file} ({size_mb:.1f} MB)")
        if convert_glb_to_usdz(glb_path, usdz_path):
            success += 1

    print(f"\n{'═' * 50}")
    print(f"✅ {success}/{len(glb_files)} files converted")

if __name__ == "__main__":
    main()
