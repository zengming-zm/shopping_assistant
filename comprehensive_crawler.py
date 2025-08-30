"""
Comprehensive Product Crawler with Enhanced URL Discovery
Designed to find ALL product categories and collections on e-commerce sites
"""

import asyncio
import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict, Any, Optional, Set
import xml.etree.ElementTree as ET

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests

from product_crawler import ProductExtractor

class ComprehensiveURLDiscovery:
    """Enhanced URL discovery for comprehensive e-commerce crawling"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.discovered_urls = set()
        self.category_urls = set()
        self.product_urls = set()
        
        # Enhanced patterns for e-commerce sites
        self.category_patterns = [
            r'/collection[s]?/',
            r'/categor[y|ies]/',
            r'/shop/',
            r'/products?/',
            r'/browse/',
            r'/store/',
            r'/catalog/',
            r'/department[s]?/',
            r'/section[s]?/',
        ]
        
        self.product_patterns = [
            r'/product[s]?/',
            r'/item[s]?/',
            r'/p/',
            r'/buy/',
            r'/detail[s]?/',
            r'/sku/',
        ]
    
    async def discover_all_urls(self, page, max_categories: int = 20, max_products: int = 100) -> Dict[str, List[str]]:
        """Comprehensive URL discovery using multiple strategies"""
        
        print("🔍 Starting comprehensive URL discovery...")
        
        # Strategy 1: Sitemap parsing
        sitemap_urls = await self.discover_from_sitemap()
        print(f"   📄 Found {len(sitemap_urls)} URLs from sitemap")
        
        # Strategy 2: Robots.txt analysis
        robots_urls = await self.discover_from_robots()
        print(f"   🤖 Found {len(robots_urls)} URLs from robots.txt")
        
        # Strategy 3: Navigation menu analysis
        nav_urls = await self.discover_from_navigation(page)
        print(f"   🧭 Found {len(nav_urls)} URLs from navigation")
        
        # Strategy 4: Footer links analysis
        footer_urls = await self.discover_from_footer(page)
        print(f"   🦶 Found {len(footer_urls)} URLs from footer")
        
        # Strategy 5: In-page link analysis
        page_urls = await self.discover_from_page_content(page)
        print(f"   📃 Found {len(page_urls)} URLs from page content")
        
        # Strategy 6: Deep category exploration
        deep_urls = await self.discover_deep_categories(page)
        print(f"   🔎 Found {len(deep_urls)} URLs from deep exploration")
        
        # Combine and categorize all URLs
        all_urls = sitemap_urls | robots_urls | nav_urls | footer_urls | page_urls | deep_urls
        
        categorized = self.categorize_urls(list(all_urls))
        
        # Limit results
        categorized['categories'] = categorized['categories'][:max_categories]
        categorized['products'] = categorized['products'][:max_products]
        
        print(f"✅ Discovery complete: {len(categorized['categories'])} categories, {len(categorized['products'])} products")
        
        return categorized
    
    async def discover_from_sitemap(self) -> Set[str]:
        """Discover URLs from XML sitemaps"""
        urls = set()
        
        sitemap_locations = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
            f"{self.base_url}/product-sitemap.xml",
            f"{self.base_url}/category-sitemap.xml",
            f"{self.base_url}/sitemaps/sitemap.xml",
        ]
        
        for sitemap_url in sitemap_locations:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(sitemap_url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            urls.update(self.parse_sitemap_xml(content))
            except:
                # Fallback to requests for sitemap
                try:
                    response = requests.get(sitemap_url, timeout=10)
                    if response.status_code == 200:
                        urls.update(self.parse_sitemap_xml(response.text))
                except:
                    continue
        
        return urls
    
    def parse_sitemap_xml(self, xml_content: str) -> Set[str]:
        """Parse XML sitemap content"""
        urls = set()
        
        try:
            # Handle sitemap index
            if 'sitemapindex' in xml_content:
                root = ET.fromstring(xml_content)
                for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                    loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                    if loc is not None:
                        # Recursively fetch individual sitemaps
                        try:
                            response = requests.get(loc.text, timeout=10)
                            if response.status_code == 200:
                                urls.update(self.parse_sitemap_xml(response.text))
                        except:
                            continue
            
            # Handle regular sitemap
            else:
                # Try XML parsing
                root = ET.fromstring(xml_content)
                for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                    loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                    if loc is not None:
                        urls.add(loc.text)
        
        except ET.ParseError:
            # Fallback: regex extraction
            url_pattern = r'<loc>(.*?)</loc>'
            matches = re.findall(url_pattern, xml_content)
            urls.update(matches)
        
        return urls
    
    async def discover_from_robots(self) -> Set[str]:
        """Discover URLs from robots.txt"""
        urls = set()
        
        try:
            robots_url = f"{self.base_url}/robots.txt"
            response = requests.get(robots_url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                
                # Look for sitemap references
                sitemap_pattern = r'Sitemap:\s*(https?://[^\s]+)'
                sitemap_matches = re.findall(sitemap_pattern, content, re.IGNORECASE)
                
                for sitemap_url in sitemap_matches:
                    try:
                        sitemap_response = requests.get(sitemap_url, timeout=10)
                        if sitemap_response.status_code == 200:
                            urls.update(self.parse_sitemap_xml(sitemap_response.text))
                    except:
                        continue
                
                # Look for explicitly allowed paths
                allow_pattern = r'Allow:\s*([^\s]+)'
                allow_matches = re.findall(allow_pattern, content)
                
                for path in allow_matches:
                    if any(pattern in path for pattern in ['/product', '/shop', '/category', '/collection']):
                        full_url = urljoin(self.base_url, path)
                        urls.add(full_url)
        
        except:
            pass
        
        return urls
    
    async def discover_from_navigation(self, page) -> Set[str]:
        """Discover URLs from navigation menus"""
        urls = set()
        
        try:
            # Enhanced navigation selectors
            nav_selectors = [
                'nav a[href]',
                '.navigation a[href]',
                '.nav a[href]',
                '.menu a[href]',
                '.main-menu a[href]',
                '.primary-menu a[href]',
                '.header-menu a[href]',
                '.top-menu a[href]',
                '.category-menu a[href]',
                '.product-menu a[href]',
                '.mega-menu a[href]',
                '[role="navigation"] a[href]',
                '.navbar a[href]',
                '.header nav a[href]',
                '.main-nav a[href]',
            ]
            
            for selector in nav_selectors:
                links = await page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute('href')
                    if href and self.is_same_domain(href):
                        full_url = urljoin(self.base_url, href)
                        urls.add(full_url)
        
        except Exception as e:
            print(f"   ⚠️ Navigation discovery error: {e}")
        
        return urls
    
    async def discover_from_footer(self, page) -> Set[str]:
        """Discover URLs from footer links"""
        urls = set()
        
        try:
            footer_selectors = [
                'footer a[href]',
                '.footer a[href]',
                '.site-footer a[href]',
                '.page-footer a[href]',
                '.main-footer a[href]',
                '#footer a[href]',
            ]
            
            for selector in footer_selectors:
                links = await page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute('href')
                    if href and self.is_same_domain(href):
                        full_url = urljoin(self.base_url, href)
                        # Footer often has category links
                        if self.looks_like_category_url(full_url):
                            urls.add(full_url)
        
        except Exception as e:
            print(f"   ⚠️ Footer discovery error: {e}")
        
        return urls
    
    async def discover_from_page_content(self, page) -> Set[str]:
        """Discover URLs from main page content"""
        urls = set()
        
        try:
            # Look for category and product links in main content
            content_selectors = [
                'main a[href]',
                '.main-content a[href]',
                '.content a[href]',
                '.page-content a[href]',
                '.category-grid a[href]',
                '.product-grid a[href]',
                '.collection-list a[href]',
                '.category-list a[href]',
                '.featured-products a[href]',
                '.product-carousel a[href]',
                '.category-carousel a[href]',
            ]
            
            for selector in content_selectors:
                links = await page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute('href')
                    if href and self.is_same_domain(href):
                        full_url = urljoin(self.base_url, href)
                        urls.add(full_url)
        
        except Exception as e:
            print(f"   ⚠️ Page content discovery error: {e}")
        
        return urls
    
    async def discover_deep_categories(self, page) -> Set[str]:
        """Deep exploration of category pages for sub-categories"""
        urls = set()
        
        try:
            # First, identify potential category pages from current page
            category_candidates = set()
            
            all_links = await page.query_selector_all('a[href]')
            for link in all_links:
                href = await link.get_attribute('href')
                if href and self.looks_like_category_url(href):
                    category_candidates.add(urljoin(self.base_url, href))
            
            # Explore first few category pages for sub-categories
            for category_url in list(category_candidates)[:5]:  # Limit to avoid infinite crawling
                try:
                    await page.goto(category_url, wait_until='networkidle', timeout=15000)
                    await page.wait_for_timeout(2000)
                    
                    # Look for pagination and sub-categories
                    sub_links = await page.query_selector_all('a[href]')
                    for link in sub_links:
                        href = await link.get_attribute('href')
                        if href and self.is_same_domain(href):
                            full_url = urljoin(self.base_url, href)
                            if self.looks_like_category_url(full_url) or self.looks_like_product_url(full_url):
                                urls.add(full_url)
                
                except:
                    continue
        
        except Exception as e:
            print(f"   ⚠️ Deep category discovery error: {e}")
        
        return urls
    
    def categorize_urls(self, urls: List[str]) -> Dict[str, List[str]]:
        """Categorize discovered URLs into categories and products"""
        categories = []
        products = []
        other = []
        
        for url in urls:
            if self.looks_like_product_url(url):
                products.append(url)
            elif self.looks_like_category_url(url):
                categories.append(url)
            else:
                other.append(url)
        
        # Remove duplicates and sort
        return {
            'categories': sorted(list(set(categories))),
            'products': sorted(list(set(products))),
            'other': sorted(list(set(other)))
        }
    
    def looks_like_category_url(self, url: str) -> bool:
        """Enhanced category URL detection"""
        url_lower = url.lower()
        
        # Positive indicators
        category_indicators = [
            '/collection', '/category', '/categories',
            '/shop', '/products', '/browse',
            '/department', '/section', '/catalog',
            '/men', '/women', '/kids', '/accessories',
            '/clothing', '/shoes', '/bags', '/jewelry',
            '/shirts', '/pants', '/dresses', '/jackets',
            '/casual', '/formal', '/business',
        ]
        
        # Skip obvious non-categories
        skip_patterns = [
            '/account', '/login', '/cart', '/checkout',
            '/about', '/contact', '/help', '/faq',
            '/blog', '/news', '/press', '/careers',
            '.jpg', '.png', '.gif', '.pdf', '.css', '.js'
        ]
        
        for skip in skip_patterns:
            if skip in url_lower:
                return False
        
        for indicator in category_indicators:
            if indicator in url_lower:
                return True
        
        return False
    
    def looks_like_product_url(self, url: str) -> bool:
        """Enhanced product URL detection"""
        url_lower = url.lower()
        
        # Positive indicators
        product_indicators = [
            '/product/', '/products/', '/item/', '/items/',
            '/p/', '/buy/', '/detail/', '/sku/'
        ]
        
        # Skip non-products
        skip_patterns = [
            '/cart', '/checkout', '/account', '/login',
            '/about', '/contact', '/help', '/faq',
            '/blog', '/news', '/category', '/collection',
            '.jpg', '.png', '.gif', '.pdf'
        ]
        
        for skip in skip_patterns:
            if skip in url_lower:
                return False
        
        for indicator in product_indicators:
            if indicator in url_lower:
                return True
        
        # Check for product-like patterns
        if re.search(r'/[^/]+-[^/]+/?$', url):  # product-name-style
            return True
        
        if re.search(r'/\d{3,}/?$', url):  # product ID
            return True
        
        return False
    
    def is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to the same domain"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.domain or parsed.netloc == '' or url.startswith('/')
        except:
            return False

class ComprehensiveProductCrawler:
    """Main crawler class with comprehensive URL discovery"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.product_extractor = ProductExtractor()
    
    async def crawl_comprehensively(self, base_url: str, progress_callback=None, max_products: int = 100) -> List[Dict[str, Any]]:
        """Comprehensive crawling with enhanced URL discovery"""
        
        products = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='ShopTalk-Comprehensive/1.0'
            )
            page = await context.new_page()
            
            try:
                if progress_callback:
                    progress_callback("Loading main page...")
                
                await page.goto(base_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Initialize comprehensive URL discovery
                discovery = ComprehensiveURLDiscovery(base_url)
                
                if progress_callback:
                    progress_callback("Discovering all product URLs...")
                
                # Discover all URLs
                discovered = await discovery.discover_all_urls(page, max_products=max_products)
                
                category_urls = discovered['categories']
                product_urls = discovered['products']
                
                if progress_callback:
                    progress_callback(f"Found {len(category_urls)} categories and {len(product_urls)} products")
                
                # Crawl products from discovered URLs
                all_urls_to_crawl = product_urls
                
                # Also crawl category pages to find more products
                for category_url in category_urls[:10]:  # Limit category exploration
                    try:
                        if progress_callback:
                            progress_callback(f"Exploring category: {category_url}")
                        
                        await page.goto(category_url, wait_until='networkidle', timeout=20000)
                        await page.wait_for_timeout(2000)
                        
                        # Find products in this category
                        category_products = await self.find_products_in_category(page, base_url)
                        all_urls_to_crawl.extend(category_products)
                        
                        if len(all_urls_to_crawl) >= max_products:
                            break
                    
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Error exploring {category_url}: {str(e)[:50]}")
                        continue
                
                # Remove duplicates and limit
                all_urls_to_crawl = list(set(all_urls_to_crawl))[:max_products]
                
                if progress_callback:
                    progress_callback(f"Crawling {len(all_urls_to_crawl)} product pages...")
                
                # Crawl products concurrently
                semaphore = asyncio.Semaphore(self.max_workers)
                tasks = []
                
                for url in all_urls_to_crawl:
                    task = asyncio.create_task(
                        self.crawl_product_with_semaphore(browser, url, semaphore)
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, dict) and result:
                        products.append(result)
                
                if progress_callback:
                    progress_callback(f"Crawling complete: {len(products)} products extracted")
            
            finally:
                await browser.close()
        
        return products
    
    async def find_products_in_category(self, page, base_url: str) -> List[str]:
        """Find product URLs within a category page"""
        product_urls = []
        
        try:
            # Look for product links on category page
            product_link_selectors = [
                '.product-item a[href]',
                '.product-card a[href]',
                '.product-tile a[href]',
                '.product a[href]',
                '.item a[href]',
                '[data-product] a[href]',
                '.grid-item a[href]',
                '.collection-item a[href]',
            ]
            
            for selector in product_link_selectors:
                links = await page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute('href')
                    if href:
                        full_url = urljoin(base_url, href)
                        discovery = ComprehensiveURLDiscovery(base_url)
                        if discovery.looks_like_product_url(full_url):
                            product_urls.append(full_url)
        
        except:
            pass
        
        return product_urls
    
    async def crawl_product_with_semaphore(self, browser, url: str, semaphore: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
        """Crawl single product with concurrency control"""
        async with semaphore:
            try:
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    await page.goto(url, wait_until='networkidle', timeout=20000)
                    await page.wait_for_timeout(2000)
                    
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    page_text = await page.evaluate('document.body.innerText || ""')
                    
                    return self.product_extractor.extract_product_data(url, soup, page_text)
                
                finally:
                    await context.close()
            
            except:
                return None

# Import aiohttp for async requests
try:
    import aiohttp
except ImportError:
    aiohttp = None

def run_comprehensive_crawler(website_url: str, progress_callback=None, max_workers: int = 4, max_products: int = 100) -> List[Dict[str, Any]]:
    """Run comprehensive product crawler"""
    
    crawler = ComprehensiveProductCrawler(max_workers)
    
    async def main():
        return await crawler.crawl_comprehensively(website_url, progress_callback, max_products)
    
    return asyncio.run(main())

if __name__ == "__main__":
    # Test with Luca Faloni
    def progress(msg):
        print(f"🔍 {msg}")
    
    print("Testing Comprehensive Crawler with Luca Faloni...")
    products = run_comprehensive_crawler("https://lucafaloni.com", progress, max_products=20)
    
    print(f"\n✅ Found {len(products)} products:")
    for product in products[:5]:
        print(f"- {product.get('product_name', 'Unknown')}")
        print(f"  URL: {product['url']}")
        print(f"  Prices: {product.get('prices', [])}")
        print(f"  Sizes: {product.get('sizes', [])}")