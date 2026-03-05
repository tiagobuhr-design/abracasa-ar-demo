#!/usr/bin/env python3
"""
Converts GLB to USDZ using Tripo3D API by passing public GitHub Pages URLs.
Bypasses local upload size limits and avoids 1-hour regeneration times.
"""

import json
import os
import sys
import time
import requests

TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY", "")
TRIPO_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
GITHUB_PAGES_BASE = "https://tiagobuhr-design.github.io/abracasa-ar-demo"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(SCRIPT_DIR, "products.json")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

POLL_INTERVAL = 10
MAX_POLL_ATTEMPTS = 30

def get_headers():
    return {
        "Authorization": f"Bearer {TRIPO_API_KEY}",
        "Content-Type": "application/json",
    }

def create_usdz_conversion_task(glb_url):
    payload = {
        "type": "convert_model",
        "format": "USDZ",
        "file": {
            "type": "glb",
            "url": glb_url
        }
    }
    resp = requests.post(f"{TRIPO_BASE_URL}/task", headers=get_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"  ❌ API Error: {resp.text[:200]}")
        return None
    
    data = resp.json()
    if data.get("code") != 0:
        print(f"  ❌ Convert error: {data.get('message')}")
        return None
        
    return data.get("data", {}).get("task_id")

def poll_task(task_id, description):
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL)
        resp = requests.get(f"{TRIPO_BASE_URL}/task/{task_id}", headers=get_headers(), timeout=30)
        if resp.status_code != 200: continue
        
        data = resp.json().get("data", {})
        status = data.get("status", "unknown")
        
        if status == "success":
            print(f"    ✅ {description} completed!")
            return data
        elif status == "failed":
            print(f"    ❌ {description} failed")
            return None
        else:
            prog = data.get("progress", "?")
            print(f"    ⏳ {description} status: {status} ({prog}%)")
    return None

def download_file(task_data, filepath):
    result = task_data.get("result", {}) or task_data.get("output", {})
    model_url = None
    if isinstance(result, dict) and isinstance(result.get("model"), dict):
        model_url = result["model"].get("url")
    if not model_url:
        model_url = result.get("model_url") or result.get("url")
    
    if not model_url:
        import re
        urls = re.findall(r'"(https?://[^"]+\.(?:glb|usdz)[^"]*)"', json.dumps(task_data))
        if urls: model_url = urls[0]

    if not model_url: return False
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    resp = requests.get(model_url, timeout=120)
    if resp.status_code == 200:
        with open(filepath, "wb") as f:
            f.write(resp.content)
        size_mb = len(resp.content) / (1024 * 1024)
        print(f"    📥 Saved {os.path.basename(filepath)} ({size_mb:.1f} MB)")
        return True
    return False

def main():
    if not TRIPO_API_KEY:
        print("❌ TRIPO_API_KEY not set")
        sys.exit(1)

    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"📦 Converting {len(products)} public GLB URLs to USDZ\n")
    success = 0

    for i, product in enumerate(products):
        print(f"{'─' * 60}")
        print(f"[{i + 1}/{len(products)}] {product['name']}")

        slug = product.get("slug")
        if not slug: continue
        
        glb_path = product.get("glb_path")
        if not glb_path: continue

        usdz_file = os.path.join(MODELS_DIR, f"{slug}.usdz")
        if os.path.exists(usdz_file) and os.path.getsize(usdz_file) > 1000:
            print(f"  ⏭️  Already has USDZ ({slug}.usdz), skipping")
            product["usdz_path"] = f"models/{slug}.usdz"
            success += 1
            json.dump(products, open(PRODUCTS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            continue

        # Form public URL
        glb_url = f"{GITHUB_PAGES_BASE}/{glb_path}"
        print(f"  🔗 Source: {glb_url}")

        task_id = create_usdz_conversion_task(glb_url)
        if not task_id: continue

        task_data = poll_task(task_id, "USDZ Conversion")
        if not task_data: continue

        if download_file(task_data, usdz_file):
            product["usdz_path"] = f"models/{slug}.usdz"
            success += 1
            with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump(products, f, indent=2, ensure_ascii=False)

        time.sleep(2)

    print(f"\n{'═' * 60}")
    print(f"✅ {success}/{len(products)} USDZ files generated")

if __name__ == "__main__":
    main()
