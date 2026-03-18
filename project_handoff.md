# Project Handoff: AR Furniture Sales Demo & Pipeline

## 🎯 Overall Objective
We have built a complete B2B sales system to pitch 3D/AR visualization services to Brazilian furniture e-commerce companies. 
The system consists of:
1. **The Demo:** A fully functional, mobile-first web page showing actual products in 3D and Augmented Reality (AR) directly in the browser, without an app.
2. **The Sales Pipeline:** A structured list of target companies, outreach messages, and a pitch deck (one-pager) to sell this service.

## ✅ Current Status: MVP READY
The demo is fully functional and verified on both **iOS** and **Android**.
- **Real-World Scale**: Every model is accurately scaled to match its real-world centimeter dimensions (verified with 0.0% error).
- **Floor Anchoring**: Models snap to the floor and do not float in mid-air.
- **Fixed Scaling**: Users cannot pinch-to-zoom, ensuring they see the product exactly as it is in real life.
- **Full Textures**: High-fidelity textures are preserved during the GLB to USDZ conversion process.

## 📁 File Structure & Overview
**Project Path:** `/Users/tiagobuhr/.gemini/antigravity/playground/retrograde-astro/abracasa-demo/`

### 1. Core Demo
- **`index.html`**: The main demo website. It contains the product grid, 3D modal, and AR launch logic for both iOS Quick Look and Android Scene Viewer.
- **`products_with_dims.json`**: The database of products containing names, prices, image URLs, and URLs pointing to local `glb` and `usdz` models.
- **`models/`**: Directory containing the generated 3D models in both GLB (Android/Web) and USDZ (iOS) formats.

### 2. Automation & Conversion Scripts
- **`scrape.py`**: Python script to scrape product data from the target website.
- **`scale_models.mjs`**: A Node.js script using `@gltf-transform/core` that applies non-uniform 3-axis scaling to ensure every dimension (width, height, depth) matches the real product.
- **`convert_glb_to_usdz.mjs`**: A professional-grade converter using Puppeteer and Three.js. It bakes transforms into vertices, anchors models to the floor, and preserves high-quality textures.

### 3. Sales & Outreach
- **`pitch/index.html`**: A premium single-page HTML proposal tailored for furniture retailers. 
- **`outreach/messages.md`**: Multi-channel outreach scripts (WhatsApp, LinkedIn, Email) in Brazilian Portuguese.
- **`pipeline/target-companies.json`**: Research on 10 high-potential Brazilian furniture stores for business development.

---

## 🚀 How to use this for a new client (e.g., Oppa Design)
1. **Scrape**: Use `scrape_oppa.py` (or similar) to get product data and dimensions into a JSON file.
2. **Generate**: Use `generate_and_convert.py` (requires Tripo3D API key) to get the initial 3D models.
3. **Refine Scale**: Run `node scale_models.mjs` to ensure models match the exact scraped dimensions.
4. **Convert**: Run `node convert_glb_to_usdz.mjs` to generate the floor-anchored USDZ files for iOS.
5. **Deploy**: Push the new models and updated JSON to your GitHub repository.
6. **Pitch**: Send the customized demo link along with the outreach messages.
