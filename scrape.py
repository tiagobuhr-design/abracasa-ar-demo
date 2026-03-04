#!/usr/bin/env python3
"""
Abra Casa Product Scraper — Phase 1
Scrapes poltronas and sofás from abracasa.com.br using the Firecrawl API.
Outputs products.json with 8 products (4 per category).
"""

import json
import os
import re
import sys
import unicodedata
import requests

# ─── Config ──────────────────────────────────────────────────────────────────

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
BASE_URL = "https://www.abracasa.com.br"

TARGETS = [
    {"url": "https://www.abracasa.com.br/moveis/poltronas", "category": "poltrona"},
    {"url": "https://www.abracasa.com.br/moveis/sofa/sofa-tradicional", "category": "sofa"},
]

PRODUCTS_PER_CATEGORY = 4
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.json")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_slug(name):
    """Convert a product name to a URL-safe slug: lowercase, no accents, hyphens only."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug


def is_valid_image_url(url):
    """Check that the image URL is a real, direct image link."""
    if not url:
        return False
    if len(url) < 30:
        return False
    if "base64" in url.lower():
        return False
    if not re.search(r"\.(jpg|jpeg|png|webp|avif)", url.lower()):
        return False
    return True


def is_lifestyle_image(url):
    """Heuristic: skip images that look like lifestyle/room scenes."""
    lifestyle_keywords = ["banner", "lifestyle", "ambiente", "room", "scene", "hero",
                          "desktop", "mobile", "colecao", "luminaria_foco"]
    url_lower = url.lower()
    return any(kw in url_lower for kw in lifestyle_keywords)


def scrape_page(url, category):
    """Call Firecrawl API to scrape a single page and return raw HTML."""
    if not FIRECRAWL_API_KEY:
        print("❌ Error: FIRECRAWL_API_KEY environment variable is not set.")
        print("   Run with: FIRECRAWL_API_KEY='your-key' python3 scrape.py")
        sys.exit(1)

    print(f"🔍 Scraping {category}s from {url} ...")

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "url": url,
        "formats": ["html"],
        "onlyMainContent": False,
        "waitFor": 5000,
        "timeout": 30000,
        "removeBase64Images": True,
    }

    resp = requests.post(FIRECRAWL_SCRAPE_URL, headers=headers, json=payload, timeout=60)

    if resp.status_code != 200:
        print(f"❌ Firecrawl API error {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)

    data = resp.json()

    if not data.get("success"):
        print(f"❌ Firecrawl returned success=false: {json.dumps(data, indent=2)[:500]}")
        sys.exit(1)

    html = data.get("data", {}).get("html", "")
    if not html:
        print(f"⚠️  No HTML returned for {url}")
        return ""

    print(f"   ✅ Got {len(html):,} chars of HTML")
    return html


def extract_products_from_html(html, category):
    """
    Parse product data from the VTEX-rendered HTML.
    
    Product card structure (from debug):
      <div id="product-card-SKUID" data-deco="view-product" ...>
        <figure>
          <a href="https://www.abracasa.com.br/SLUG/p?skuId=SKUID" aria-label="view product">
            <img src="https://abracasa.vteximg.com.br/arquivos/ids/XXXX/name.jpg?v=..." ...>
          </a>
        </figure>
        <a href="..."><h2>Product Name</h2></a>
        <a href="...">
          <div>R$&nbsp;2.599,88</div>  (original - line-through)
          <div>R$&nbsp;1.499,88</div>  (current price - bold)
          <div>10x de R$ 149,98 s/ juros</div>
        </a>
      </div>
    """
    products = []
    seen_slugs = set()

    # Split HTML into product cards using the product-card-ID pattern
    card_pattern = re.compile(
        r'<div\s+id="product-card-(\d+)"[^>]*data-deco="view-product"[^>]*>(.*?)(?=<div\s+id="product-card-|$)',
        re.DOTALL,
    )

    cards = card_pattern.findall(html)
    print(f"   Found {len(cards)} product cards")

    for sku_id, card_html in cards:
        # ── Extract product URL ──
        url_match = re.search(
            r'href="(https://www\.abracasa\.com\.br/[^"]+/p(?:\?[^"]*)?)"',
            card_html,
        )
        if not url_match:
            continue
        product_url = url_match.group(1)

        # ── Extract product name from h2 ──
        name_match = re.search(r'<h2[^>]*>\s*(.+?)\s*</h2>', card_html, re.DOTALL)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        # Clean any HTML entities
        name = name.replace("&amp;", "&").replace("&nbsp;", " ")
        name = re.sub(r'<[^>]+>', '', name)  # strip any inner tags

        if len(name) < 3:
            continue

        # ── Extract price (current/bold price, not the line-through one) ──
        # The bold/current price has font-bold class
        bold_price_match = re.search(
            r'font-bold[^>]*>R\$[\s\xa0&nbsp;]*([0-9.,]+)',
            card_html,
        )
        if bold_price_match:
            price_val = bold_price_match.group(1).strip()
            price = f"R$ {price_val}"
        else:
            # Fallback: find all R$ X.XXX,XX patterns (with &nbsp;)
            price_matches = re.findall(
                r'R\$(?:&nbsp;|\s|\xa0)*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2}))',
                card_html,
            )
            if price_matches:
                # Take the last full formatted price (likely the selling price)
                price = f"R$ {price_matches[-1]}"
            else:
                continue

        # ── Extract image URL ──
        # First img in the card is the product photo; second is the hover image
        img_matches = re.findall(
            r'<img\s+src="([^"]+)"',
            card_html,
        )

        image_url = None
        for img in img_matches:
            if not is_valid_image_url(img):
                continue
            if is_lifestyle_image(img):
                continue
            image_url = img
            break  # Take the first valid product image

        if not image_url:
            continue

        # ── Generate slug ──
        slug = make_slug(name)

        # ── Deduplicate ──
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        product = {
            "name": name,
            "price": price,
            "image_url": image_url,
            "product_url": product_url,
            "category": category,
            "slug": slug,
            "glb_path": None,
            "usdz_path": None,
        }
        products.append(product)

    return products


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    all_products = []

    for target in TARGETS:
        html = scrape_page(target["url"], target["category"])
        if not html:
            continue

        products = extract_products_from_html(html, target["category"])
        print(f"   ✅ Extracted {len(products)} valid {target['category']}(s)")

        # Limit to PRODUCTS_PER_CATEGORY
        products = products[:PRODUCTS_PER_CATEGORY]
        all_products.extend(products)

    if not all_products:
        print("\n❌ No products found. The page structure may have changed.")
        print("   Try running again or check the Firecrawl API response.")
        sys.exit(1)

    # Save to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n✅ Scraped {len(all_products)} products:")
    for p in all_products:
        print(f"  [{p['category']}] {p['name']} — {p['price']} — {p['image_url'][:80]}...")

    print(f"\n📄 Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
