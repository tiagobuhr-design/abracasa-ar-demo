import requests
from bs4 import BeautifulSoup
import json
import re

# Oppa Design category URLs
urls = [
    "https://www.oppa.com.br/moveis/sofas/?PS=12",
    "https://www.oppa.com.br/moveis/poltronas/?PS=12"
]

products = []

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

for url in urls:
    print(f"Scraping category: {url}")
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # This will depend on VTEX or Magento structure, let's try generic links first or find VTEX pattern
        # Many Brazilian e-commerces use VTEX.
        items = soup.find_all('a', class_=re.compile(r'product-image|shelf-item__image|product__image', re.I))
        if not items:
            items = soup.select('.prateleira a') # VTEX
            
        for item in items[:4]: # Take top 4 from each category to get 8 total
            href = item.get('href')
            if not href.startswith('http'):
                href = 'https://www.oppa.com.br' + href
                
            print(f"Found product: {href}")
            
            # Now scrape the product page
            p_res = requests.get(href, headers=headers)
            p_soup = BeautifulSoup(p_res.text, 'html.parser')
            
            name = p_soup.find('h1')
            name = name.text.strip() if name else "Unknown"
            
            price_elem = p_soup.find(class_=re.compile(r'bestPrice|skuBestPrice|preco-por|price__best', re.I))
            price = price_elem.text.strip() if price_elem else "R$ 0,00"
            
            img_elem = p_soup.find('img', id='image-main')
            if not img_elem:
                img_elem = p_soup.find('img', class_=re.compile(r'sku-rich-image-main|product-image__main', re.I))
            img_url = img_elem.get('src') if img_elem else ""
            
            # Extract dimensions from description or specs table
            # VTEX specs table
            specs = p_soup.find_all('td', class_='value-field')
            spec_labels = p_soup.find_all('th', class_='name-field')
            
            width, height, depth = None, None, None
            
            for th, td in zip(spec_labels, specs):
                label = th.text.strip().lower()
                val = td.text.strip().lower()
                if 'largura' in label:
                    m = re.search(r'([\d.,]+)', val)
                    if m: width = float(m.group(1).replace(',', '.'))
                elif 'altura' in label:
                    m = re.search(r'([\d.,]+)', val)
                    if m: height = float(m.group(1).replace(',', '.'))
                elif 'profundidade' in label:
                    m = re.search(r'([\d.,]+)', val)
                    if m: depth = float(m.group(1).replace(',', '.'))

            products.append({
                "name": name,
                "price": price,
                "url": href,
                "image": img_url,
                "category": "sofa" if "sofa" in url else "poltrona",
                "dimensions": {
                    "width_cm": width,
                    "height_cm": height,
                    "depth_cm": depth
                }
            })
            
    except Exception as e:
        print(f"Error scraping {url}: {e}")

with open('oppa_products.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, indent=2, ensure_ascii=False)
    
print(f"Saved {len(products)} products to oppa_products.json")
