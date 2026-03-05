#!/usr/bin/env python3
"""
Regenerates GLB models via Tripo3D and immediately asks Tripo3D
to convert them to USDZ using the original_model_task_id.
This bypasses upload limits because the models never leave Tripo's servers during conversion.
"""

import json
import os
import sys
import time
import requests

TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY", "")
TRIPO_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
MODEL_VERSION = "v2.0-20240919"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(SCRIPT_DIR, "products.json")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

POLL_INTERVAL = 15
MAX_POLL_ATTEMPTS = 40

def get_headers():
    return {
        "Authorization": f"Bearer {TRIPO_API_KEY}",
        "Content-Type": "application/json",
    }

def detect_image_type(url):
    url_lower = url.lower().split("?")[0]
    if url_lower.endswith(".webp"): return "webp"
    elif url_lower.endswith(".png"): return "png"
    elif url_lower.endswith(".jpeg"): return "jpeg"
    else: return "jpg"

def create_model_task(product):
    image_type = detect_image_type(product["image_url"])
    payload = {
        "type": "image_to_model",
        "file": {"type": image_type, "url": product["image_url"]},
        "model_version": MODEL_VERSION,
    }
    resp = requests.post(f"{TRIPO_BASE_URL}/task", headers=get_headers(), json=payload, timeout=30)
    if resp.status_code != 200: return None
    return resp.json().get("data", {}).get("task_id")

def create_usdz_task(original_task_id):
    payload = {
        "type": "convert_model",
        "format": "USDZ",
        "original_model_task_id": original_task_id
    }
    resp = requests.post(f"{TRIPO_BASE_URL}/task", headers=get_headers(), json=payload, timeout=30)
    if resp.status_code != 200: return None
    return resp.json().get("data", {}).get("task_id")

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

    for i, product in enumerate(products):
        print(f"{'─' * 60}")
        print(f"[{i + 1}/{len(products)}] {product['name']}")

        # Skip if already has USDZ
        usdz_file = os.path.join(MODELS_DIR, f"{product['slug']}.usdz")
        if os.path.exists(usdz_file) and os.path.getsize(usdz_file) > 1000:
            print(f"  ⏭️  Already has USDZ, skipping")
            continue

        print(f"  1. Starting GLB generation...")
        model_task_id = create_model_task(product)
        if not model_task_id: continue

        model_data = poll_task(model_task_id, "GLB generation")
        if not model_data: continue

        print(f"  2. Starting USDZ conversion...")
        usdz_task_id = create_usdz_task(model_task_id)
        if not usdz_task_id: continue

        usdz_data = poll_task(usdz_task_id, "USDZ conversion")
        if not usdz_data: continue

        print(f"  3. Downloading files...")
        slug = product["slug"]
        
        glb_path = os.path.join(MODELS_DIR, f"{slug}.glb")
        if download_file(model_data, glb_path):
            product["glb_path"] = f"models/{slug}.glb"

        usdz_path = os.path.join(MODELS_DIR, f"{slug}.usdz")
        if download_file(usdz_data, usdz_path):
            product["usdz_path"] = f"models/{slug}.usdz"

        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)

        time.sleep(2)

if __name__ == "__main__":
    main()
