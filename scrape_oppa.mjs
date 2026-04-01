import puppeteer from 'puppeteer';
import fs from 'fs/promises';

async function scrapeOppa() {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();

    await page.setViewport({ width: 1280, height: 800 });
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36');

    const urls = [
        "https://www.oppa.com.br/collections/sofa",
        "https://www.oppa.com.br/collections/poltrona"
    ];

    const allProducts = [];

    for (const url of urls) {
        console.log(`Loading category: ${url}`);
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

        // Scroll to load lazy items
        await page.evaluate(() => window.scrollBy(0, 1000));
        await new Promise(r => setTimeout(r, 2000));

        // Get product links (Shopify uses /products/)
        const productLinks = await page.evaluate(() => {
            const links = Array.from(document.querySelectorAll('a'));
            return links
                .map(a => a.href)
                .filter(href => href.includes('/products/') && !href.includes('/collections/'))
                .filter((href, index, self) => self.indexOf(href) === index) // Unique
                .slice(0, 4); // Take 4 per category
        });

        console.log(`Found ${productLinks.length} products on ${url}`);

        for (const link of productLinks) {
            console.log(`Scraping product: ${link}`);
            try {
                await page.goto(link, { waitUntil: 'networkidle2', timeout: 60000 });

                const product = await page.evaluate(() => {
                    const nameEl = document.querySelector('h1.product-single__title') || document.querySelector('h1');
                    const name = nameEl ? nameEl.innerText.trim() : "Unknown";

                    // Try to find price
                    const priceEls = document.querySelectorAll('.product__price, .price-item, [class*="price"]');
                    let price = "Price not found";
                    for (let el of priceEls) {
                        if (el.innerText && el.innerText.includes('R$')) {
                            price = el.innerText.trim();
                            const match = price.match(/R\$\s*[\d\.,]+/);
                            if (match) price = match[0];
                            break;
                        }
                    }

                    // Try to find main image
                    const imgEl = document.querySelector('.product-single__photo img') ||
                        document.querySelector('img.lazyautosizes') ||
                        document.querySelector('.product-image-main img') ||
                        document.querySelector('img[src*="cdn.shopify.com"]');
                    // Get highest res version by replacing size modifiers like _400x400
                    let image = imgEl ? imgEl.src : "";
                    if (image.startsWith('//')) image = 'https:' + image;
                    if (image) image = image.replace(/_\d+x\d+/, '');

                    let width = null, height = null, depth = null;

                    // Look through page text for dimensions
                    // Oppa puts them in a structured table or text list in the description
                    const rawText = document.body.innerText.toLowerCase();
                    const wMatch = rawText.match(/largura[^\d]*([\d.,]+)/);
                    if (wMatch) width = parseFloat(wMatch[1].replace(',', '.'));

                    const hMatch = rawText.match(/altura[^\d]*([\d.,]+)/);
                    if (hMatch) height = parseFloat(hMatch[1].replace(',', '.'));

                    const dMatch = rawText.match(/profundidade[^\d]*([\d.,]+)/);
                    if (dMatch) depth = parseFloat(dMatch[1].replace(',', '.'));

                    return { name, price, image, width, height, depth };
                });

                allProducts.push({
                    name: product.name,
                    price: product.price,
                    url: link,
                    image: product.image,
                    category: url.includes('sofa') ? "sofa" : "poltrona",
                    dimensions: {
                        width_cm: product.width,
                        height_cm: product.height,
                        depth_cm: product.depth
                    }
                });
            } catch (err) {
                console.log(`Failed to scrape ${link}: ${err.message}`);
            }
        }
    }

    await fs.writeFile('oppa_products_with_dims.json', JSON.stringify(allProducts, null, 2));
    console.log(`✅ Saved ${allProducts.length} products.`);
    await browser.close();
}

scrapeOppa().catch(console.error);
