#!/usr/bin/env python3
"""
Abra Casa 3D Model Generator — Phase 2
Generates GLB 3D models from product images using the Tripo3D API.
Reads products.json, creates tasks, polls for completion, downloads models.
"""

import json
import os
import sys
import time
import requests

# ─── Config ──────────────────────────────────────────────────────────────────

TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY", "")
TRIPO_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
MODEL_VERSION = "v2.0-20240919"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(SCRIPT_DIR, "products.json")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

POLL_INTERVAL = 15      # seconds between status checks
MAX_POLL_ATTEMPTS = 30  # ~7.5 minutes max per product
PAUSE_BETWEEN = 5       # seconds between products


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_headers():
    return {
        "Authorization": f"Bearer {TRIPO_API_KEY}",
        "Content-Type": "application/json",
    }


def detect_image_type(url):
    """Detect file type from image URL."""
    url_lower = url.lower().split("?")[0]
    if url_lower.endswith(".webp"):
        return "webp"
    elif url_lower.endswith(".png"):
        return "png"
    elif url_lower.endswith(".jpeg"):
        return "jpeg"
    else:
        return "jpg"


def create_task(product):
    """Step A: POST to create an image_to_model task."""
    image_type = detect_image_type(product["image_url"])

    payload = {
        "type": "image_to_model",
        "file": {
            "type": image_type,
            "url": product["image_url"],
        },
        "model_version": MODEL_VERSION,
    }

    resp = requests.post(
        f"{TRIPO_BASE_URL}/task",
        headers=get_headers(),
        json=payload,
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  ❌ API error {resp.status_code}: {resp.text[:200]}")
        return None

    data = resp.json()

    if data.get("code") != 0:
        print(f"  ❌ Task creation failed: {data.get('message', 'unknown error')}")
        return None

    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        print(f"  ❌ No task_id in response: {json.dumps(data)[:200]}")
        return None

    print(f"  📤 Task created: {task_id}")
    return task_id


def poll_task(task_id, product_name):
    """Step B: Poll until status is 'success' or 'failed'."""
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL)

        resp = requests.get(
            f"{TRIPO_BASE_URL}/task/{task_id}",
            headers=get_headers(),
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"  ⚠️  Poll error {resp.status_code} (attempt {attempt})")
            continue

        data = resp.json()
        task_data = data.get("data", {})
        status = task_data.get("status", "unknown")

        if status == "success":
            print(f"  ✅ {product_name} — completed!")
            return task_data
        elif status == "failed":
            print(f"  ❌ {product_name} — task failed")
            return None
        else:
            progress = task_data.get("progress", "?")
            print(f"  ⏳ {product_name} — status: {status} (attempt {attempt}, progress: {progress})")

    print(f"  ❌ {product_name} — timed out after {MAX_POLL_ATTEMPTS} attempts")
    return None


def download_model(task_data, slug):
    """Step C: Download the GLB model file."""
    # Navigate to result.model.url
    model_url = None
    result = task_data.get("result", {}) or task_data.get("output", {})

    # Try different response structures
    if isinstance(result, dict):
        model_info = result.get("model", {})
        if isinstance(model_info, dict):
            model_url = model_info.get("url")
        if not model_url:
            model_url = result.get("model_url") or result.get("url")

    # Also check at top level
    if not model_url:
        model_url = task_data.get("model", {}).get("url") if isinstance(task_data.get("model"), dict) else None

    if not model_url:
        # Try to find any URL that looks like a model download
        data_str = json.dumps(task_data)
        import re
        urls = re.findall(r'"(https?://[^"]+\.glb[^"]*)"', data_str)
        if urls:
            model_url = urls[0]

    if not model_url:
        print(f"  ❌ Could not find model URL in response")
        print(f"     Response keys: {list(task_data.keys())}")
        if "result" in task_data:
            print(f"     Result keys: {list(task_data['result'].keys()) if isinstance(task_data.get('result'), dict) else task_data['result']}")
        if "output" in task_data:
            print(f"     Output keys: {list(task_data['output'].keys()) if isinstance(task_data.get('output'), dict) else task_data['output']}")
        return None

    # Ensure models directory exists
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Download
    filepath = os.path.join(MODELS_DIR, f"{slug}.glb")
    print(f"  📥 Downloading model to {slug}.glb ...")

    resp = requests.get(model_url, timeout=120)
    if resp.status_code != 200:
        print(f"  ❌ Download failed: HTTP {resp.status_code}")
        return None

    with open(filepath, "wb") as f:
        f.write(resp.content)

    size_mb = len(resp.content) / (1024 * 1024)
    print(f"  ✅ Saved {slug}.glb ({size_mb:.1f} MB)")
    return f"models/{slug}.glb"


def update_products_json(products):
    """Step D: Save updated products.json to disk."""
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if not TRIPO_API_KEY:
        print("❌ Error: TRIPO_API_KEY environment variable is not set.")
        print("   Run with: TRIPO_API_KEY='your-key' python3 generate3d.py")
        sys.exit(1)

    # Load products
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"📦 Loaded {len(products)} products from products.json\n")

    results = []  # Track (name, slug, success)

    for i, product in enumerate(products):
        name = product["name"]
        slug = product["slug"]
        print(f"{'─' * 60}")
        print(f"[{i + 1}/{len(products)}] {name}")
        print(f"  Image: {product['image_url'][:70]}...")

        # Skip if already has a glb_path
        if product.get("glb_path"):
            print(f"  ⏭️  Already has glb_path: {product['glb_path']}, skipping")
            results.append((name, slug, True))
            continue

        # Step A: Create task
        task_id = create_task(product)
        if not task_id:
            results.append((name, slug, False))
            if i < len(products) - 1:
                time.sleep(PAUSE_BETWEEN)
            continue

        # Step B: Poll until complete
        task_data = poll_task(task_id, name)
        if not task_data:
            results.append((name, slug, False))
            update_products_json(products)
            if i < len(products) - 1:
                time.sleep(PAUSE_BETWEEN)
            continue

        # Step C: Download model
        glb_path = download_model(task_data, slug)

        # Step D: Update products.json
        if glb_path:
            product["glb_path"] = glb_path
            results.append((name, slug, True))
        else:
            results.append((name, slug, False))

        update_products_json(products)

        # Pause before next product
        if i < len(products) - 1:
            print(f"  ⏸️  Waiting {PAUSE_BETWEEN}s before next product...")
            time.sleep(PAUSE_BETWEEN)

    # Final summary
    print(f"\n{'═' * 60}")
    print(f"🎉 Done! Results:")
    success_count = 0
    for name, slug, ok in results:
        if ok:
            print(f"  ✅ {slug}.glb")
            success_count += 1
        else:
            print(f"  ❌ {slug} (failed)")

    print(f"\n  {success_count}/{len(results)} models generated successfully")
    print(f"  📄 products.json updated")


if __name__ == "__main__":
    main()
