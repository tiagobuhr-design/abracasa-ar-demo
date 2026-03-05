# Project Handoff: AR Furniture Sales Demo & Pipeline

## 🎯 Overall Objective
We are building a complete B2B sales system to pitch 3D/AR visualization services to Brazilian furniture e-commerce companies. 
The system has two main parts:
1. **The Demo:** A fully functional, mobile-first web page showing actual products in 3D and Augmented Reality (AR) directly in the browser, without an app.
2. **The Sales Pipeline:** A structured list of target companies, outreach messages, and a pitch deck (one-pager) to sell this service.

## 🛑 Current Status & Blocker
The demo is built and hosted, and works reliably on Android devices (using Google Scene Viewer intent).
**The Blocker:** The AR button ("Ver na sala") is **failing silently on iPhones (iOS Safari)**. 

We are using Google's `<model-viewer>` component. On iOS, AR relies on Apple's "Quick Look", which strictly requires **USDZ** files. We currently only have **GLB** files. We attempted to rely on `<model-viewer>`'s built-in, on-the-fly GLB-to-USDZ auto-conversion (which sometimes works when the viewer is visible and triggered via native `slot="ar-button"`), but it is failing, likely due to model complexity.

**Next Steps for the new AI:** 
We must generate proper `.usdz` files from our `.glb` files and provide them to `<model-viewer>` via the `ios-src="models/filename.usdz"` attribute. We attempted local conversion (Python `trimesh`, `usd-core`, Node.js `three.js USDZExporter`), but they all failed due to various limitations (lack of DOM in Node, missing USDZ export support in trimesh, etc.). The current plan was to use the **Tripo3D API's "Post Process" converting endpoint** to generate the USDZ files server-side, but we stopped before supplying the API key to run the script.

---

## 📁 File Structure & Overview
**Project Path:** `/Users/tiagobuhr/.gemini/antigravity/playground/retrograde-astro/abracasa-demo/`

### 1. Core Demo
- **`index.html`**: The main demo website. It's a single file containing all HTML, CSS, and JS. It loads a product grid and uses a 3D modal with `<model-viewer>`. *This is where the AR logic needs to be fixed to handle iOS.*
- **`products.json`**: The database of products containing names, prices, image URLs, and URLs pointing to local `glb_path` models. It has placeholder `usdz_path` fields waiting to be filled.
- **`models/`**: Directory containing the 8 generated `.glb` 3D models. (Needs `.usdz` files added here).

### 2. Automation & Conversion Scripts
- **`scrape.py`**: Python script using Firecrawl API to scrape product data from the target website.
- **`generate3d.py`**: Python script using Tripo3D API to turn 2D product images into 3D `.glb` models.
- **`convert_to_usdz.py`**: Draft Python script designed to upload the local `.glb` files to Tripo3D, trigger a format conversion task to `USDZ`, and download the result. *(Recommended script to fix the iOS blocker).*
- **`convert_usdz.py` / `convert_glb_to_usdz.mjs`**: Previous failed attempts at local conversion using Python and Node.js. (Can likely be deleted).

### 3. Sales & Outreach
- **`pitch/index.html`**: A separate, premium single-page HTML proposal. It outlines the problem (cart abandonment), solution (AR), case studies (IKEA, Shopify), and a WhatsApp CTA for the pilot program.
- **`outreach/messages.md`**: 3 crafted message templates (WhatsApp voice script, WhatsApp text, LinkedIn DM) in Brazilian Portuguese specifically tailored for the target executives.
- **`pipeline/target-companies.json` & `.md`**: Research on 10 Brazilian furniture e-commerce stores (e.g., Oppa Design, Lider Interiores) ranked by priority, evaluating their Instagram presence, traffic, and platform to target for future demos.

---

## 🛠️ Instructions for the new AI

**Prompt to give the new AI:**
> "We are building a web-based AR furniture demo using `<model-viewer>`. AR works on Android, but fails on iOS because we only have GLB files, and auto-conversion isn't working. 
> 
> Here is what you need to do:
> 1. Look at `/Users/tiagobuhr/.gemini/antigravity/playground/retrograde-astro/abracasa-demo/convert_to_usdz.py`. We need to run this script using a valid `TRIPO_API_KEY` to convert our 8 GLB models in the `models/` directory into USDZ files.
> 2. Once we successfully generate the `.usdz` files, update `products.json` with the new file paths.
> 3. Modify `index.html` to map the `ios-src` attribute in the `<model-viewer>` component to the new `.usdz` files. Replace the current AR logic to ensure iOS Quick Look launches properly when the AR button is tapped."
