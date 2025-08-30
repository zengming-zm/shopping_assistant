"""
Multi-threaded Enhanced Product Crawler with Playwright and Structured Data Extraction
Optimized for high-performance concurrent crawling with rate limiting
"""

import asyncio
import json
import re
import time
import hashlib
import threading
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import logging

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests

# Import the original ProductExtractor
from product_crawler import ProductExtractor

class RateLimiter:
    """Thread-safe rate limiter for polite crawling"""
    
    def __init__(self, max_requests_per_second: float = 2.0):
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()

class ProgressTracker:
    """Thread-safe progress tracking"""
    
    def __init__(self, total_items: int, callback: Optional[Callable[[str], None]] = None):
        self.total_items = total_items
        self.completed_items = 0
        self.callback = callback
        self.lock = threading.Lock()
        self.start_time = time.time()
    
    def update(self, message: str = ""):
        """Update progress with thread safety"""
        with self.lock:
            self.completed_items += 1
            elapsed = time.time() - self.start_time
            
            if self.total_items > 0:
                progress_pct = (self.completed_items / self.total_items) * 100
                rate = self.completed_items / elapsed if elapsed > 0 else 0
                eta = (self.total_items - self.completed_items) / rate if rate > 0 else 0
                
                status = f"Progress: {self.completed_items}/{self.total_items} ({progress_pct:.1f}%) - Rate: {rate:.1f}/s - ETA: {eta:.0f}s"
                if message:
                    status = f"{status} | {message}"
            else:
                status = f"Processed: {self.completed_items} | {message}"
            
            if self.callback:
                self.callback(status)

class MultiThreadedProductCrawler:
    """Multi-threaded crawler with Playwright for JavaScript-rendered content"""
    
    def __init__(self, max_workers: int = 4, rate_limit: float = 2.0):
        self.max_workers = max_workers
        self.rate_limiter = RateLimiter(rate_limit)
        self.product_extractor = ProductExtractor()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ShopTalk-ProductCrawler/2.0 (Multi-threaded E-commerce Assistant)',
        })
        
        # Thread-safe collections
        self.discovered_urls = set()
        self.products = []
        self.errors = []
        self.lock = threading.Lock()
    
    async def crawl_with_concurrent_playwright(self, url: str, progress_callback=None, max_urls: int = 50) -> List[Dict[str, Any]]:
        """Crawl using concurrent Playwright contexts"""
        
        products = []
        
        async with async_playwright() as p:
            if progress_callback:
                progress_callback("Starting browsers...")
            
            # Launch browser with multiple contexts
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-web-security'
                ]
            )
            
            try:
                # Discover URLs to crawl
                if progress_callback:
                    progress_callback("Discovering product URLs...")
                
                # Create initial context for URL discovery
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='ShopTalk-ProductCrawler/2.0'
                )
                page = await context.new_page()
                
                urls_to_crawl = await self.discover_product_urls(page, url, max_urls)
                await context.close()
                
                if not urls_to_crawl:
                    if progress_callback:
                        progress_callback("No product URLs discovered")
                    return products
                
                if progress_callback:
                    progress_callback(f"Found {len(urls_to_crawl)} URLs to crawl")
                
                # Create progress tracker
                progress_tracker = ProgressTracker(len(urls_to_crawl), progress_callback)
                
                # Crawl URLs concurrently with multiple contexts
                semaphore = asyncio.Semaphore(self.max_workers)
                tasks = []
                
                for crawl_url in urls_to_crawl:
                    task = asyncio.create_task(
                        self.crawl_single_url_with_semaphore(
                            browser, crawl_url, semaphore, progress_tracker
                        )
                    )
                    tasks.append(task)
                
                # Wait for all tasks to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect successful results
                for result in results:
                    if isinstance(result, dict) and result:
                        products.append(result)
                    elif isinstance(result, Exception):
                        print(f"Task failed: {result}")
            
            finally:
                await browser.close()
        
        return products
    
    async def crawl_single_url_with_semaphore(
        self, 
        browser, 
        url: str, 
        semaphore: asyncio.Semaphore, 
        progress_tracker: ProgressTracker
    ) -> Optional[Dict[str, Any]]:
        """Crawl a single URL with concurrency control"""
        
        async with semaphore:
            try:
                # Create new context for this URL
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='ShopTalk-ProductCrawler/2.0'
                )
                page = await context.new_page()
                
                try:
                    # Add rate limiting
                    await asyncio.sleep(0.5)  # Basic rate limiting
                    
                    await page.goto(url, wait_until='networkidle', timeout=20000)
                    await page.wait_for_timeout(2000)  # Wait for dynamic content
                    
                    # Get page content
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Get visible text for analysis
                    page_text = await page.evaluate('document.body.innerText || document.body.textContent || ""')
                    
                    # Extract product data
                    product_data = self.product_extractor.extract_product_data(url, soup, page_text)
                    
                    progress_tracker.update(f"Crawled {url}")
                    
                    return product_data
                    
                finally:
                    await context.close()
                    
            except PlaywrightTimeoutError:
                progress_tracker.update(f"Timeout: {url}")
                return None
            except Exception as e:
                progress_tracker.update(f"Error: {url} - {str(e)[:50]}")
                return None
    
    async def discover_product_urls(self, page, base_url: str, max_urls: int = 50) -> List[str]:
        """Enhanced URL discovery with concurrent processing"""
        
        urls_to_crawl = []
        discovered = set()
        
        try:
            # Load the main page
            await page.goto(base_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for dynamic content
            
            # Extract all links concurrently
            links_data = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(link => ({
                        href: link.href,
                        text: link.textContent?.trim() || '',
                        className: link.className || ''
                    }));
                }
            """)
            
            # Process links and filter for product URLs
            for link_data in links_data:
                href = link_data['href']
                if href and self.is_product_url(href) and href not in discovered:
                    full_url = urljoin(base_url, href)
                    urls_to_crawl.append(full_url)
                    discovered.add(href)
                    
                    if len(urls_to_crawl) >= max_urls:
                        break
            
            # If we don't have enough URLs, try category pages
            if len(urls_to_crawl) < 10:
                category_urls = await self.discover_category_urls(page, base_url)
                
                for category_url in category_urls[:3]:  # Check first 3 categories
                    try:
                        await page.goto(category_url, wait_until='networkidle', timeout=20000)
                        await page.wait_for_timeout(2000)
                        
                        # Extract product links from category page
                        category_links = await page.evaluate("""
                            () => {
                                const links = Array.from(document.querySelectorAll('a[href]'));
                                return links.map(link => link.href).filter(href => href);
                            }
                        """)
                        
                        for href in category_links:
                            if self.is_product_url(href) and href not in discovered:
                                urls_to_crawl.append(href)
                                discovered.add(href)
                                
                                if len(urls_to_crawl) >= max_urls:
                                    break
                        
                        if len(urls_to_crawl) >= max_urls:
                            break
                            
                    except Exception as e:
                        print(f"Error processing category {category_url}: {e}")
                        continue
        
        except Exception as e:
            print(f"Error discovering URLs: {e}")
        
        return urls_to_crawl[:max_urls]
    
    async def discover_category_urls(self, page, base_url: str) -> List[str]:
        """Discover category/collection URLs"""
        
        category_urls = []
        
        try:
            # Look for category/collection links
            category_links = await page.evaluate("""
                () => {
                    const selectors = [
                        'a[href*="collection"]',
                        'a[href*="category"]',
                        'a[href*="shop"]',
                        'a[href*="products"]',
                        '.nav a',
                        '.menu a',
                        '.category a'
                    ];
                    
                    const links = [];
                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(link => {
                            if (link.href) links.push(link.href);
                        });
                    });
                    
                    return [...new Set(links)];
                }
            """)
            
            for link in category_links:
                if self.is_category_url(link):
                    category_urls.append(link)
            
        except Exception as e:
            print(f"Error discovering category URLs: {e}")
        
        return category_urls[:5]  # Limit to 5 categories
    
    def is_product_url(self, url: str) -> bool:
        """Enhanced product URL detection"""
        url_lower = url.lower()
        
        # Positive indicators
        product_indicators = [
            '/product/', '/products/', '/item/', '/items/',
            '/shop/', '/p/', '/buy/', '/detail/'
        ]
        
        # Skip patterns
        skip_patterns = [
            '/cart', '/checkout', '/account', '/login', '/register',
            '/about', '/contact', '/blog', '/news', '/help',
            '.jpg', '.png', '.gif', '.pdf', '.css', '.js',
            '/search', '/compare', '/wishlist'
        ]
        
        # Check skip patterns first
        for skip in skip_patterns:
            if skip in url_lower:
                return False
        
        # Check product indicators
        for indicator in product_indicators:
            if indicator in url_lower:
                return True
        
        # Check for product ID patterns
        if re.search(r'/\d{3,}/?$', url) or re.search(r'[?&](id|product)=\d+', url):
            return True
        
        # Check for product-like paths
        if re.search(r'/[^/]+-[^/]+/?$', url):  # product-name-style URLs
            return True
        
        return False
    
    def is_category_url(self, url: str) -> bool:
        """Check if URL is a category/collection page"""
        url_lower = url.lower()
        
        category_indicators = [
            '/collection', '/category', '/categories',
            '/shop', '/products', '/catalog'
        ]
        
        return any(indicator in url_lower for indicator in category_indicators)

class ThreadedRequestsCrawler:
    """Multi-threaded crawler using requests (fallback for non-JS sites)"""
    
    def __init__(self, max_workers: int = 8, rate_limit: float = 3.0):
        self.max_workers = max_workers
        self.rate_limiter = RateLimiter(rate_limit)
        self.product_extractor = ProductExtractor()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ShopTalk-ProductCrawler/2.0 (Multi-threaded)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def crawl_urls_threaded(self, urls: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """Crawl multiple URLs using thread pool"""
        
        products = []
        progress_tracker = ProgressTracker(len(urls), progress_callback)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all URLs to thread pool
            future_to_url = {
                executor.submit(self.crawl_single_url, url, progress_tracker): url 
                for url in urls
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        products.append(result)
                except Exception as e:
                    progress_tracker.update(f"Error crawling {url}: {str(e)[:50]}")
        
        return products
    
    def crawl_single_url(self, url: str, progress_tracker: ProgressTracker) -> Optional[Dict[str, Any]]:
        """Crawl a single URL with requests"""
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product data
            product_data = self.product_extractor.extract_product_data(url, soup, response.text)
            
            progress_tracker.update(f"Crawled {url}")
            
            return product_data
            
        except Exception as e:
            progress_tracker.update(f"Error: {url} - {str(e)[:50]}")
            return None

def run_multithreaded_product_crawler(
    website_url: str, 
    progress_callback=None, 
    max_workers: int = 4,
    use_playwright: bool = True,
    max_urls: int = 50
) -> List[Dict[str, Any]]:
    """Run the multi-threaded product crawler"""
    
    if use_playwright:
        # Use Playwright for JavaScript-heavy sites
        crawler = MultiThreadedProductCrawler(max_workers, rate_limit=2.0)
        
        async def main():
            return await crawler.crawl_with_concurrent_playwright(
                website_url, progress_callback, max_urls
            )
        
        return asyncio.run(main())
    
    else:
        # Use requests for simple sites (faster)
        from urllib.parse import urlparse
        
        # First discover URLs using simple crawler
        crawler = MultiThreadedProductCrawler(max_workers, rate_limit=3.0)
        domain = urlparse(website_url).netloc
        
        # Discover URLs using a simple method
        urls = [website_url]  # Start with base URL
        
        # Use threaded requests crawler
        requests_crawler = ThreadedRequestsCrawler(max_workers, rate_limit=3.0)
        return requests_crawler.crawl_urls_threaded(urls, progress_callback)

# Performance comparison test
async def performance_test():
    """Test performance comparison between single-threaded and multi-threaded"""
    
    test_url = "https://lucafaloni.com"
    
    print("🧪 Performance Test: Single vs Multi-threaded Crawling")
    print("=" * 60)
    
    # Test 1: Single-threaded (original)
    print("\n1️⃣ Testing Single-threaded Crawler...")
    start_time = time.time()
    
    def progress_callback(msg):
        print(f"   {msg}")
    
    try:
        from product_crawler import run_product_crawler
        single_results = run_product_crawler(test_url, progress_callback)
        single_time = time.time() - start_time
        print(f"   ✅ Single-threaded: {len(single_results)} products in {single_time:.2f}s")
    except Exception as e:
        print(f"   ❌ Single-threaded failed: {e}")
        single_time = 0
        single_results = []
    
    # Test 2: Multi-threaded
    print("\n2️⃣ Testing Multi-threaded Crawler...")
    start_time = time.time()
    
    try:
        multi_results = run_multithreaded_product_crawler(
            test_url, progress_callback, max_workers=4, max_urls=20
        )
        multi_time = time.time() - start_time
        print(f"   ✅ Multi-threaded: {len(multi_results)} products in {multi_time:.2f}s")
    except Exception as e:
        print(f"   ❌ Multi-threaded failed: {e}")
        multi_time = 0
        multi_results = []
    
    # Performance summary
    print("\n📊 Performance Summary:")
    print("-" * 40)
    if single_time > 0 and multi_time > 0:
        speedup = single_time / multi_time
        print(f"Single-threaded: {single_time:.2f}s ({len(single_results)} products)")
        print(f"Multi-threaded:  {multi_time:.2f}s ({len(multi_results)} products)")
        print(f"Speedup: {speedup:.2f}x {'🚀' if speedup > 1.2 else '📈'}")
    else:
        print("Unable to complete performance comparison")

if __name__ == "__main__":
    asyncio.run(performance_test())