#!/usr/bin/env python3
"""
Convert GLB models to USDZ using Tripo3D API's conversion endpoint.
Uses the existing GLB models and the Tripo API to produce USDZ files.
"""

import json
import os
import sys
import time
import requests

TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY", "")
TRIPO_BASE_URL = "https://api.tripo3d.ai/v2/openapi"

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


def upload_glb_to_tripo(glb_path):
    """Upload a GLB file to Tripo and get a file token."""
    filename = os.path.basename(glb_path)
    print(f"  📤 Uploading {filename}...")

    with open(glb_path, 'rb') as f:
        resp = requests.post(
            f"{TRIPO_BASE_URL}/upload",
            headers={"Authorization": f"Bearer {TRIPO_API_KEY}"},
            files={"file": (filename, f, "model/gltf-binary")},
            timeout=120,
        )

    if resp.status_code != 200:
        print(f"  ❌ Upload failed: HTTP {resp.status_code}")
        print(f"     Response: {resp.text[:200]}")
        return None

    data = resp.json()
    if data.get("code") != 0:
        print(f"  ❌ Upload error: {data.get('message', 'unknown')}")
        return None

    token = data.get("data", {}).get("image_token")
    if not token:
        print(f"  ❌ No token in upload response")
        print(f"     Response: {json.dumps(data)[:300]}")
        return None

    print(f"  ✅ Uploaded, token: {token[:20]}...")
    return token


def create_conversion_task(original_task_id=None, file_token=None):
    """Create a conversion task to convert GLB to USDZ."""

    # Try different API endpoint/payload structures
    payload = {
        "type": "convert_model",
        "format": "USDZ",
    }

    if original_task_id:
        payload["original_model_task_id"] = original_task_id
    elif file_token:
        payload["file"] = {"type": "glb", "file_token": file_token}

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
        msg = data.get("message", "unknown")
        print(f"  ❌ Task creation failed: {msg}")
        # If convert_model doesn't work, try other task types
        return None

    task_id = data.get("data", {}).get("task_id")
    if task_id:
        print(f"  📋 Conversion task: {task_id}")
    return task_id


def poll_task(task_id, name):
    """Poll until task completes."""
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL)
        resp = requests.get(
            f"{TRIPO_BASE_URL}/task/{task_id}",
            headers=get_headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            continue

        data = resp.json()
        task_data = data.get("data", {})
        status = task_data.get("status", "unknown")

        if status == "success":
            print(f"  ✅ Conversion completed!")
            return task_data
        elif status == "failed":
            print(f"  ❌ Conversion failed")
            return None
        else:
            progress = task_data.get("progress", "?")
            print(f"  ⏳ Status: {status} (attempt {attempt}, progress: {progress})")

    print(f"  ❌ Timed out")
    return None


def download_usdz(task_data, slug):
    """Download USDZ from completed task."""
    result = task_data.get("result", {}) or task_data.get("output", {})
    model_url = None

    if isinstance(result, dict):
        model_info = result.get("model", {})
        if isinstance(model_info, dict):
            model_url = model_info.get("url")
        if not model_url:
            model_url = result.get("model_url") or result.get("url")

    if not model_url:
        # Search for any USDZ URL in the response
        import re
        data_str = json.dumps(task_data)
        urls = re.findall(r'"(https?://[^"]+\.usdz[^"]*)"', data_str)
        if urls:
            model_url = urls[0]
        else:
            # Try any URL
            urls = re.findall(r'"(https?://[^"]+model[^"]*)"', data_str)
            if urls:
                model_url = urls[0]

    if not model_url:
        print(f"  ❌ Could not find download URL")
        print(f"     Task data keys: {list(task_data.keys())}")
        return None

    filepath = os.path.join(MODELS_DIR, f"{slug}.usdz")
    print(f"  📥 Downloading USDZ...")

    resp = requests.get(model_url, timeout=120)
    if resp.status_code != 200:
        print(f"  ❌ Download failed: HTTP {resp.status_code}")
        return None

    with open(filepath, "wb") as f:
        f.write(resp.content)

    size_mb = len(resp.content) / (1024 * 1024)
    print(f"  ✅ Saved {slug}.usdz ({size_mb:.1f} MB)")
    return f"models/{slug}.usdz"


def main():
    if not TRIPO_API_KEY:
        print("❌ TRIPO_API_KEY not set")
        print("   Run: TRIPO_API_KEY='your-key' python3 convert_to_usdz.py")
        sys.exit(1)

    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"📦 Converting {len(products)} products to USDZ via Tripo3D API\n")

    success = 0
    for i, product in enumerate(products):
        name = product["name"]
        slug = product["slug"]
        glb_path = os.path.join(SCRIPT_DIR, product["glb_path"])

        print(f"{'─' * 60}")
        print(f"[{i + 1}/{len(products)}] {name}")

        # Skip if already converted
        usdz_file = os.path.join(MODELS_DIR, f"{slug}.usdz")
        if os.path.exists(usdz_file) and os.path.getsize(usdz_file) > 1000:
            print(f"  ⏭️  Already has USDZ, skipping")
            product["usdz_path"] = f"models/{slug}.usdz"
            success += 1
            continue

        # Upload GLB
        token = upload_glb_to_tripo(glb_path)
        if not token:
            continue

        # Create conversion task
        task_id = create_conversion_task(file_token=token)
        if not task_id:
            continue

        # Poll
        task_data = poll_task(task_id, name)
        if not task_data:
            continue

        # Download
        usdz_path = download_usdz(task_data, slug)
        if usdz_path:
            product["usdz_path"] = usdz_path
            success += 1

        # Save progress
        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)

        if i < len(products) - 1:
            time.sleep(3)

    # Final save
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    print(f"\n{'═' * 60}")
    print(f"✅ {success}/{len(products)} converted to USDZ")


if __name__ == "__main__":
    main()
