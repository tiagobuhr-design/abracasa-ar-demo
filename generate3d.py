#!/usr/bin/env python3
"""
Generate 3D GLB models from product images using the Tripo3D API.
- Uploads images first for reliability
- Downloads pbr_model GLB directly (no conversion step needed)
"""
import json
import os
import time
import requests
import urllib.request

API_KEY = os.environ.get("TRIPO_API_KEY", "tsk_S_MC-lUH-8gUDdYU99_i6KEVzCdLr6hThLhRMZkFQ2-")
API_BASE = "https://api.tripo3d.ai/v2/openapi"
PRODUCTS_FILE = "products.json"
MODELS_DIR = "models"
POLL_INTERVAL = 5
MAX_POLL = 120

headers_json = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
headers_auth = {"Authorization": f"Bearer {API_KEY}"}


def upload_image(image_url):
    """Download image from URL (or use local path) and upload to Tripo."""
    tmp_path = "/tmp/tripo_upload.jpg"
    
    if image_url.startswith("/tmp/"):
        tmp_path = image_url
        print(f"  Using local image ({os.path.getsize(tmp_path):,} bytes)")
    else:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'}
        response = requests.get(image_url, headers=headers, stream=True)
        response.raise_for_status()
        with open(tmp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        size = os.path.getsize(tmp_path)
        print(f"  Downloaded image ({size:,} bytes)")
    
    with open(tmp_path, "rb") as f:
        resp = requests.post(f"{API_BASE}/upload",
            headers=headers_auth,
            files={"file": ("image.jpg", f, "image/jpeg")}
        )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Upload error: {data}")
    token = data["data"]["image_token"]
    print(f"  Uploaded → token: {token[:20]}...")
    return token


def create_task(image_token):
    """Submit image-to-3D generation task using uploaded image token."""
    resp = requests.post(f"{API_BASE}/task", headers=headers_json, json={
        "type": "image_to_model",
        "file": {"type": "jpg", "file_token": image_token}
    })
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"API error: {data}")
    return data["data"]["task_id"]


def poll_task(task_id):
    """Poll until task completes, return result."""
    for _ in range(MAX_POLL):
        resp = requests.get(f"{API_BASE}/task/{task_id}", headers=headers_json)
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data.get("status")
        progress = data.get("progress", 0)
        print(f"  Status: {status} ({progress}%)", end="\r")
        if status == "success":
            print()
            return data
        elif status in ("failed", "cancelled", "unknown"):
            raise Exception(f"Task failed: {status}")
        time.sleep(POLL_INTERVAL)
    raise Exception("Timeout waiting for task")


def download_glb(result, output_path):
    """Download the GLB model directly from the pbr_model output."""
    model_url = result.get("output", {}).get("pbr_model")
    if not model_url:
        # Fallback to regular model
        model_url = result.get("output", {}).get("model")
    if not model_url:
        raise Exception("No model URL in output")
    
    print(f"  Downloading GLB...")
    resp = requests.get(model_url, stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"  ✅ Saved {os.path.basename(output_path)} ({size_mb:.1f} MB)")


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    products = json.loads(open(PRODUCTS_FILE).read())
    
    # Check balance
    bal = requests.get(f"{API_BASE}/user/balance", headers=headers_json)
    print(f"💰 Balance: {bal.json()['data']['balance']} credits\n")
    
    print(f"🎨 Generating 3D models for {len(products)} products\n")
    
    for i, p in enumerate(products):
        name = p["name"]
        slug = p["slug"]
        glb_path = os.path.join(MODELS_DIR, f"{slug}.glb")
        
        if os.path.exists(glb_path):
            print(f"[{i+1}/{len(products)}] {name} — already exists, skipping")
            p["glb_path"] = glb_path
            continue
        
        print(f"[{i+1}/{len(products)}] {name}")
        
        try:
            # Step 1: Upload image
            token = upload_image(p["image"])
            
            # Step 2: Create generation task
            task_id = create_task(token)
            print(f"  Task: {task_id}")
            
            # Step 3: Poll until done
            result = poll_task(task_id)
            
            # Step 4: Download GLB directly
            download_glb(result, glb_path)
            p["glb_path"] = glb_path
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    # Update products.json with glb_path
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    generated = sum(1 for p in products if p.get("glb_path"))
    print(f"✅ {generated}/{len(products)} models ready")
    
    # Final balance
    bal = requests.get(f"{API_BASE}/user/balance", headers=headers_json)
    print(f"💰 Remaining balance: {bal.json()['data']['balance']} credits")


if __name__ == "__main__":
    main()
