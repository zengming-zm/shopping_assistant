"""
Advanced Product Crawler with Playwright and Structured Data Extraction
Focuses on extracting product information with detailed attributes
"""

import asyncio
import json
import re
import time
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests

class ProductExtractor:
    """Extracts structured product data from HTML"""
    
    def __init__(self):
        self.price_patterns = [
            r'\$[\d,]+\.?\d*',  # $123.45, $1,234
            r'£[\d,]+\.?\d*',   # £123.45
            r'€[\d,]+\.?\d*',   # €123.45
            r'¥[\d,]+\.?\d*',   # ¥123.45
            r'USD\s*[\d,]+\.?\d*',  # USD 123.45
            r'[\d,]+\.?\d*\s*USD',  # 123.45 USD
        ]
        
        self.size_patterns = [
            r'\b(XS|S|M|L|XL|XXL|XXXL)\b',  # Standard sizes
            r'\b(\d{1,2})\b',               # Numeric sizes
            r'\b(\d{1,2}"\s*x\s*\d{1,2}")\b',  # Dimensions
            r'\b(One Size|OS)\b',           # One size
        ]
        
    def extract_product_data(self, url: str, soup: BeautifulSoup, page_text: str = "") -> Optional[Dict[str, Any]]:
        """Extract structured product data from page"""
        
        # Check if this is likely a product page
        if not self.is_product_page(url, soup, page_text):
            return None
            
        product_data = {
            'id': hashlib.md5(url.encode()).hexdigest(),
            'url': url,
            'type': 'product',
            'extracted_at': datetime.utcnow().isoformat()
        }
        
        # Extract product name
        product_data['product_name'] = self.extract_product_name(soup)
        
        # Extract prices
        product_data['prices'] = self.extract_prices(soup, page_text)
        
        # Extract sizes
        product_data['sizes'] = self.extract_sizes(soup, page_text)
        
        # Extract images
        product_data['images'] = self.extract_images(soup, url)
        
        # Extract description and bullet points
        product_data['description'] = self.extract_description(soup)
        product_data['bullet_points'] = self.extract_bullet_points(soup)
        
        # Extract attributes (color, material, etc.)
        product_data['attributes'] = self.extract_attributes(soup, page_text)
        
        # Extract structured data (JSON-LD, microdata)
        structured_data = self.extract_structured_data(soup)
        if structured_data:
            product_data['structured_data'] = structured_data
        
        # Extract availability
        product_data['availability'] = self.extract_availability(soup, page_text)
        
        return product_data
    
    def is_product_page(self, url: str, soup: BeautifulSoup, page_text: str) -> bool:
        """Determine if this is a product page"""
        
        # URL-based detection
        url_indicators = [
            '/product/', '/products/', '/item/', '/items/',
            '/shop/', '/store/', '/buy/', '/p/',
        ]
        
        if any(indicator in url.lower() for indicator in url_indicators):
            return True
        
        # Content-based detection
        content_indicators = [
            'add to cart', 'buy now', 'purchase', 'price',
            'in stock', 'out of stock', 'product description',
            'size', 'color', 'quantity'
        ]
        
        text_lower = page_text.lower()
        indicator_count = sum(1 for indicator in content_indicators if indicator in text_lower)
        
        # Schema.org structured data detection
        schema_scripts = soup.find_all('script', type='application/ld+json')
        for script in schema_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    return True
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            return True
            except:
                continue
        
        # HTML structure detection
        product_selectors = [
            '[itemtype*="Product"]',
            '.product', '#product',
            '.product-info', '.product-details',
            '[data-product-id]', '[data-product]'
        ]
        
        for selector in product_selectors:
            if soup.select(selector):
                return True
        
        return indicator_count >= 3
    
    def extract_product_name(self, soup: BeautifulSoup) -> str:
        """Extract product name"""
        
        # Try different selectors for product name
        name_selectors = [
            'h1[itemprop="name"]',
            '.product-title', '.product-name',
            'h1.product', 'h1.title',
            '.product-info h1', '.product-details h1',
            '[data-product-title]', '[data-product-name]',
            'h1', 'h2'  # Fallback
        ]
        
        for selector in name_selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text(strip=True):
                return elem.get_text(strip=True)
        
        # Try title tag as last resort
        title = soup.find('title')
        if title:
            return title.get_text(strip=True)
        
        return "Unknown Product"
    
    def extract_prices(self, soup: BeautifulSoup, page_text: str) -> List[str]:
        """Extract all prices from the page"""
        prices = []
        
        # Try structured price elements first
        price_selectors = [
            '[itemprop="price"]', '[itemprop="lowPrice"]', '[itemprop="highPrice"]',
            '.price', '.product-price', '.current-price', '.sale-price',
            '.price-current', '.price-now', '.price-final',
            '[data-price]', '[class*="price"]'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                for pattern in self.price_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    prices.extend(matches)
        
        # Fallback to text extraction
        for pattern in self.price_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            prices.extend(matches)
        
        # Clean and deduplicate
        cleaned_prices = []
        seen = set()
        for price in prices:
            clean_price = re.sub(r'[^\d.,£$€¥]', '', price).strip()
            if clean_price and clean_price not in seen:
                cleaned_prices.append(price)
                seen.add(clean_price)
        
        return cleaned_prices[:5]  # Limit to 5 prices
    
    def extract_sizes(self, soup: BeautifulSoup, page_text: str) -> List[str]:
        """Extract available sizes"""
        sizes = []
        
        # Try size-specific selectors
        size_selectors = [
            '.size-option', '.product-size', '[data-size]',
            '.variant-size', '.size-variant',
            'select[name*="size"] option', 'input[name*="size"]',
            '.size-selector option', '.size-selector input'
        ]
        
        for selector in size_selectors:
            elements = soup.select(selector)
            for elem in elements:
                if elem.name == 'option' or elem.name == 'input':
                    size_text = elem.get('value', '') or elem.get_text(strip=True)
                else:
                    size_text = elem.get_text(strip=True)
                
                if size_text and len(size_text) < 10:  # Reasonable size length
                    sizes.append(size_text)
        
        # Pattern-based extraction from text
        for pattern in self.size_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            sizes.extend([match if isinstance(match, str) else match[0] for match in matches])
        
        # Clean and deduplicate
        cleaned_sizes = []
        seen = set()
        for size in sizes:
            clean_size = size.strip().upper()
            if clean_size and len(clean_size) <= 10 and clean_size not in seen:
                cleaned_sizes.append(size.strip())
                seen.add(clean_size)
        
        return cleaned_sizes[:10]  # Limit to 10 sizes
    
    def extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product images"""
        images = []
        
        # Try product-specific image selectors
        image_selectors = [
            '.product-image img', '.product-photo img',
            '.product-gallery img', '.product-slider img',
            '[data-product-image]', '[itemprop="image"]',
            '.main-image img', '.hero-image img'
        ]
        
        for selector in image_selectors:
            elements = soup.select(selector)
            for elem in elements:
                src = elem.get('src') or elem.get('data-src') or elem.get('data-lazy')
                if src:
                    full_url = urljoin(base_url, src)
                    if full_url not in images:
                        images.append(full_url)
        
        return images[:5]  # Limit to 5 images
    
    def extract_description(self, soup: BeautifulSoup) -> str:
        """Extract product description"""
        
        desc_selectors = [
            '[itemprop="description"]',
            '.product-description', '.product-details',
            '.description', '.product-info',
            '#description', '#product-description'
        ]
        
        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator=' ', strip=True)
                if len(text) > 50:  # Reasonable description length
                    return text[:500]  # Limit length
        
        return ""
    
    def extract_bullet_points(self, soup: BeautifulSoup) -> List[str]:
        """Extract bullet points/features"""
        bullet_points = []
        
        # Try to find lists in product areas
        list_selectors = [
            '.product-features ul li', '.product-details ul li',
            '.features ul li', '.specifications ul li',
            '.product-info ul li', '.highlights ul li'
        ]
        
        for selector in list_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) < 200:  # Reasonable bullet point length
                    bullet_points.append(text)
        
        return bullet_points[:10]  # Limit to 10 bullet points
    
    def extract_attributes(self, soup: BeautifulSoup, page_text: str) -> Dict[str, Any]:
        """Extract product attributes like color, material, etc."""
        attributes = {}
        
        # Color extraction
        color_patterns = [
            r'\b(red|blue|green|yellow|black|white|gray|grey|brown|pink|purple|orange|navy|beige|tan|olive|maroon|teal|turquoise)\b',
            r'\b(crimson|scarlet|azure|emerald|golden|silver|bronze|copper|ivory|pearl|charcoal|burgundy|lavender|coral)\b'
        ]
        
        colors = []
        for pattern in color_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            colors.extend([match.lower() for match in matches])
        
        if colors:
            attributes['colors'] = list(set(colors[:5]))
        
        # Material extraction
        material_patterns = [
            r'\b(cotton|wool|silk|linen|polyester|nylon|leather|suede|canvas|denim|cashmere|alpaca|mohair|bamboo|hemp)\b',
            r'\b(organic cotton|merino wool|pure silk|genuine leather|faux leather|recycled polyester)\b'
        ]
        
        materials = []
        for pattern in material_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            materials.extend([match.lower() for match in matches])
        
        if materials:
            attributes['materials'] = list(set(materials[:5]))
        
        # Brand extraction
        brand_selectors = [
            '[itemprop="brand"]', '.brand', '.product-brand',
            '[data-brand]'
        ]
        
        for selector in brand_selectors:
            elem = soup.select_one(selector)
            if elem:
                brand_text = elem.get_text(strip=True)
                if brand_text:
                    attributes['brand'] = brand_text
                    break
        
        return attributes
    
    def extract_structured_data(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract JSON-LD structured data"""
        
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    return data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            return item
            except:
                continue
        
        return None
    
    def extract_availability(self, soup: BeautifulSoup, page_text: str) -> str:
        """Extract availability status"""
        
        availability_patterns = [
            (r'\b(in stock|available|ships\s+today)\b', 'in_stock'),
            (r'\b(out of stock|sold out|unavailable|discontinued)\b', 'out_of_stock'),
            (r'\b(back order|backorder|pre-?order)\b', 'backorder'),
            (r'\b(limited|few left|only \d+ left)\b', 'limited')
        ]
        
        text_lower = page_text.lower()
        for pattern, status in availability_patterns:
            if re.search(pattern, text_lower):
                return status
        
        return 'unknown'

class EnhancedProductCrawler:
    """Enhanced crawler with Playwright for JavaScript-rendered content"""
    
    def __init__(self):
        self.product_extractor = ProductExtractor()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ShopTalk-ProductCrawler/1.0 (E-commerce Assistant)',
        })
    
    async def crawl_with_playwright(self, url: str, progress_callback=None) -> List[Dict[str, Any]]:
        """Crawl using Playwright for JavaScript-rendered content"""
        
        products = []
        
        async with async_playwright() as p:
            if progress_callback:
                progress_callback("Starting browser...")
            
            browser = await p.chromium.launch(headless=True)   
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='ShopTalk-ProductCrawler/1.0 (E-commerce Assistant)'
            )
            page = await context.new_page()
            
            try:
                # Discover URLs to crawl
                if progress_callback:
                    progress_callback("Discovering product URLs...")
                
                urls_to_crawl = await self.discover_product_urls(page, url, progress_callback)
                
                if progress_callback:
                    progress_callback(f"Found {len(urls_to_crawl)} URLs to crawl")
                
                # Crawl each URL
                for i, crawl_url in enumerate(urls_to_crawl):
                    try:
                        if progress_callback:
                            progress_callback(f"Crawling product ({i+1}/{len(urls_to_crawl)}): {crawl_url}")
                        
                        product_data = await self.crawl_product_page(page, crawl_url)
                        if product_data:
                            products.append(product_data)
                        
                        # Be polite
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        print(f"Error crawling {crawl_url}: {e}")
                        continue
            
            finally:
                await browser.close()
        
        return products
    
    async def discover_product_urls(self, page, base_url: str, progress_callback=None, max_urls: int = 20) -> List[str]:
        """Discover product URLs using Playwright"""
        
        urls_to_crawl = []
        discovered = set()
        
        try:
            # Load the main page
            await page.goto(base_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)  # Wait for dynamic content
            
            # Extract links
            links = await page.query_selector_all('a[href]')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    if href:
                        full_url = urljoin(base_url, href)
                        if self.is_product_url(full_url) and full_url not in discovered:
                            urls_to_crawl.append(full_url)
                            discovered.add(full_url)
                            
                            if len(urls_to_crawl) >= max_urls:
                                break
                except:
                    continue
            
            # Try to find collection/category pages
            if len(urls_to_crawl) < 5:
                collection_selectors = [
                    'a[href*="collection"]', 'a[href*="category"]',
                    'a[href*="shop"]', 'a[href*="products"]'
                ]
                
                for selector in collection_selectors:
                    collection_links = await page.query_selector_all(selector)
                    for link in collection_links[:3]:  # Check first 3 collection pages
                        try:
                            href = await link.get_attribute('href')
                            if href:
                                collection_url = urljoin(base_url, href)
                                if progress_callback:
                                    progress_callback(f"Exploring collection: {collection_url}")
                                
                                await page.goto(collection_url, wait_until='networkidle', timeout=30000)
                                await page.wait_for_timeout(2000)
                                
                                # Extract product links from collection page
                                product_links = await page.query_selector_all('a[href]')
                                for prod_link in product_links:
                                    try:
                                        prod_href = await prod_link.get_attribute('href')
                                        if prod_href:
                                            full_prod_url = urljoin(base_url, prod_href)
                                            if self.is_product_url(full_prod_url) and full_prod_url not in discovered:
                                                urls_to_crawl.append(full_prod_url)
                                                discovered.add(full_prod_url)
                                                
                                                if len(urls_to_crawl) >= max_urls:
                                                    break
                                    except:
                                        continue
                                
                                if len(urls_to_crawl) >= max_urls:
                                    break
                        except:
                            continue
        
        except Exception as e:
            print(f"Error discovering URLs: {e}")
        
        return urls_to_crawl[:max_urls]
    
    def is_product_url(self, url: str) -> bool:
        """Check if URL is likely a product URL"""
        url_lower = url.lower()
        
        product_indicators = [
            '/product/', '/products/', '/item/', '/items/',
            '/shop/', '/p/', '/buy/'
        ]
        
        # Skip non-product pages
        skip_patterns = [
            '/cart', '/checkout', '/account', '/login',
            '/about', '/contact', '/blog', '/news',
            '.jpg', '.png', '.gif', '.pdf', '.css', '.js'
        ]
        
        for skip in skip_patterns:
            if skip in url_lower:
                return False
        
        for indicator in product_indicators:
            if indicator in url_lower:
                return True
        
        # Check for product ID patterns
        if re.search(r'/\d+/?$', url) or re.search(r'[?&]id=\d+', url):
            return True
        
        return False
    
    async def crawl_product_page(self, page, url: str) -> Optional[Dict[str, Any]]:
        """Crawl a single product page"""
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for dynamic content
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Get visible text for analysis
            page_text = await page.evaluate('document.body.innerText')
            
            # Extract product data
            product_data = self.product_extractor.extract_product_data(url, soup, page_text)
            
            return product_data
            
        except PlaywrightTimeoutError:
            print(f"Timeout loading {url}")
            return None
        except Exception as e:
            print(f"Error crawling product page {url}: {e}")
            return None

def run_product_crawler(website_url: str, progress_callback=None) -> List[Dict[str, Any]]:
    """Run the enhanced product crawler"""
    
    crawler = EnhancedProductCrawler()
    
    # Run async crawler
    async def main():
        return await crawler.crawl_with_playwright(website_url, progress_callback)
    
    return asyncio.run(main())

# Test function
async def test_crawler():
    """Test the crawler with Luca Faloni"""
    
    def progress(msg):
        print(f"🕷️ {msg}")
    
    print("Testing Enhanced Product Crawler with Luca Faloni...")
    products = run_product_crawler("https://lucafaloni.com", progress)
    
    print(f"\n✅ Extracted {len(products)} products:")
    for product in products:
        print(f"\n📦 {product.get('product_name', 'Unknown')}")
        print(f"   URL: {product['url']}")
        print(f"   Prices: {product.get('prices', [])}")
        print(f"   Sizes: {product.get('sizes', [])}")
        print(f"   Colors: {product.get('attributes', {}).get('colors', [])}")
        print(f"   Materials: {product.get('attributes', {}).get('materials', [])}")
        print(f"   Availability: {product.get('availability', 'unknown')}")

if __name__ == "__main__":
    asyncio.run(test_crawler())