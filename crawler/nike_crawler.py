#!/usr/bin/env python3
"""
Nike Product Catalog Crawler using Firecrawl
Crawls all products from Nike.com and stores them in structured format for sparse retrieval
"""

import json
import os
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import sqlite3
import hashlib


@dataclass
class Product:
    """Product data structure"""
    id: str
    name: str
    price: str
    category: str
    subcategory: str
    description: str
    colors: List[str]
    sizes: List[str]
    images: List[str]
    url: str
    availability: str
    sku: Optional[str]
    rating: Optional[float]
    reviews_count: Optional[int]
    tags: List[str]
    crawled_at: str


class NikeCrawler:
    """Comprehensive Nike product catalog crawler"""
    
    def __init__(self, api_key: str, output_dir: str = "data/nike"):
        self.api_key = api_key
        self.output_dir = output_dir
        self.base_url = "https://www.nike.com/us/"
        self.products: List[Product] = []
        self.crawled_urls: Set[str] = set()
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize SQLite database
        self.db_path = os.path.join(output_dir, "nike_products.db")
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for structured storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price TEXT,
                category TEXT,
                subcategory TEXT,
                description TEXT,
                colors TEXT,  -- JSON array
                sizes TEXT,   -- JSON array
                images TEXT,  -- JSON array
                url TEXT UNIQUE,
                availability TEXT,
                sku TEXT,
                rating REAL,
                reviews_count INTEGER,
                tags TEXT,    -- JSON array
                crawled_at TEXT,
                content_hash TEXT  -- For deduplication
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category ON products(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_name ON products(name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price ON products(price)
        """)
        
        conn.commit()
        conn.close()
    
    def _generate_content_hash(self, product_data: Dict) -> str:
        """Generate hash for deduplication"""
        # Use key fields to generate hash
        key_fields = f"{product_data.get('name', '')}{product_data.get('price', '')}{product_data.get('sku', '')}"
        return hashlib.md5(key_fields.encode()).hexdigest()
    
    async def discover_product_urls(self) -> List[str]:
        """Discover Nike product URLs using crawl endpoint with include/exclude patterns"""
        print("🔍 Discovering Nike product URLs using crawl endpoint...")
        
        try:
            # Prepare crawl command with Nike-specific include/exclude patterns
            crawl_data = {
                "url": "https://www.nike.com",
                "includePaths": ["^/t/.*$"],
                "excludePaths": [
                    "^/w/.*$",           # listings & filters
                    "^/help.*$",         # help center
                    "^/launch.*$",       # SNKRS/launch hub
                    "^/stories.*$",      # editorial
                    "^/sitemap.*$",      # sitemaps
                    "^/cart.*$",         # cart/checkout
                    "^[^#?]*[?].*$"      # any URL with query params
                ],
                "maxDiscoveryDepth": 1,
                "sitemap": "include",
                "ignoreQueryParameters": True,
                "limit": 20,
                "allowExternalLinks": False,
                "allowSubdomains": False,
                "scrapeOptions": { "onlyMainContent": True}
            }
            
            # Execute crawl command
            crawl_command = [
                "curl", "-X", "POST",
                "https://api.firecrawl.dev/v2/crawl",
                "-H", f"Authorization: Bearer {self.api_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(crawl_data),
            ]
            
            print("🚀 Starting crawl job...")
            result = subprocess.run(crawl_command, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                response_data = json.loads(result.stdout)
                print(f"📊 Crawl response: {response_data}")
                
                # Check if we got a job ID for async crawling
                if 'id' in response_data:
                    job_id = response_data['id']
                    print(f"🆔 Crawl job ID: {job_id}")
                    
                    # Poll for crawl completion
                    nike_urls = await self._poll_crawl_job(job_id)
                    return nike_urls
                    
                # If synchronous response with URLs
                elif 'data' in response_data:
                    urls = []
                    for item in response_data['data']:
                        if 'url' in item:
                            urls.append(item['url'])
                    print(f"✅ Found {len(urls)} Nike product URLs")
                    return urls
            else:
                print(f"❌ Crawl error: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error during URL discovery: {e}")
        
        # Fallback to a few sample URLs if crawl fails
        print("🔄 Using fallback Nike product URLs...")
        fallback_urls = [
            "https://www.nike.com/t/air-max-270-mens-shoes-KkLcGR",
        ]
        
        print(f"✅ Using {len(fallback_urls)} fallback URLs")
        return fallback_urls

    async def _poll_crawl_job(self, job_id: str) -> List[str]:
        """Poll crawl job until completion and extract URLs"""
        print(f"⏳ Polling crawl job {job_id}...")
        
        max_attempts = 2  # Max 5 minutes (30 * 10 seconds)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Check job status
                status_command = [
                    "curl", "-X", "GET",
                    f"https://api.firecrawl.dev/v2/crawl/{job_id}",
                    "-H", f"Authorization: Bearer {self.api_key}",
                    "-H", "Content-Type: application/json"
                ]
                
                result = subprocess.run(status_command, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    response_data = json.loads(result.stdout)
                    status = response_data.get('status', 'unknown')
                    
                    print(f"📊 Job status: {status} (attempt {attempt + 1}/{max_attempts})")
                    
                    if status == 'completed':
                        # Extract URLs from completed job
                        urls = []
                        data = response_data.get('data', [])
                        
                        for item in data:
                            if isinstance(item, dict) and 'url' in item:
                                url = item['url']
                                # Only include Nike product URLs (should match our include pattern)
                                if '/t/' in url and 'nike.com' in url:
                                    urls.append(url)
                        
                        print(f"✅ Crawl completed! Found {len(urls)} Nike product URLs")
                        return urls
                    
                    elif status == 'failed':
                        print(f"❌ Crawl job failed: {response_data}")
                        break
                    
                    # Job still running, wait and retry
                    await asyncio.sleep(10)
                    attempt += 1
                    
                else:
                    print(f"❌ Error checking job status: {result.stderr}")
                    break
                    
            except Exception as e:
                print(f"❌ Error polling job {job_id}: {e}")
                break
        
        print("⚠️ Crawl job polling timed out or failed")
        return []
    
    def _extract_product_data(self, scraped_data: Dict, url: str) -> Optional[Product]:
        """Extract structured product data from scraped content"""
        try:
            # Get the main content
            content = scraped_data.get('markdown', '') or scraped_data.get('content', '') or scraped_data('json', '')
            metadata = scraped_data.get('metadata', {})
            
            # Handle metadata properly - it might be an object with attributes
            if hasattr(metadata, '__dict__'):
                metadata_dict = metadata.__dict__
            elif hasattr(metadata, 'title'):
                metadata_dict = {'title': metadata.title, 'description': getattr(metadata, 'description', '')}
            else:
                metadata_dict = metadata if isinstance(metadata, dict) else {}
            
            # Extract structured JSON data from Firecrawl
            json_data = scraped_data.get('json', {})
            
            # Use structured JSON data if available, otherwise fallback to parsing
            if json_data and isinstance(json_data, dict):
                name = json_data.get('product_name', '') or metadata_dict.get('title', '').replace(' - Nike', '').replace('. Nike.com', '').strip()
                description = json_data.get('description', '') or metadata_dict.get('description', '')
                price = json_data.get('price', '')
                colors = json_data.get('colors', [])
                sizes = json_data.get('sizes', [])
                category_from_json = json_data.get('category', '')
                availability = json_data.get('availability', 'Unknown')
                rating = json_data.get('rating')
                reviews_count = json_data.get('reviews_count')
                images = json_data.get('images', [])
                sku = json_data.get('sku', '')
            else:
                # Fallback to original parsing logic
                name = metadata_dict.get('title', '').replace(' - Nike', '').replace('. Nike.com', '').strip()
                description = metadata_dict.get('description', '')
                price = ''
                colors = []
                sizes = []
                category_from_json = ''
                availability = 'Unknown'
                rating = None
                reviews_count = None
                images = []
                sku = ''
            
            # If we don't have structured JSON data, try content parsing as fallback
            if not json_data or not isinstance(json_data, dict):
                import re
                if content:
                    # Look for price patterns like $129.99, $129, etc.
                    price_matches = re.findall(r'\$\d+(?:\.\d{2})?', content)
                    if price_matches and not price:
                        price = price_matches[0]
                    
                    # Look for ratings (e.g., "4.5 stars", "4.5 out of 5")
                    rating_matches = re.findall(r'(\d+\.?\d*)\s*(?:stars?|out of 5)', content.lower())
                    if rating_matches and rating is None:
                        try:
                            rating = float(rating_matches[0])
                        except ValueError:
                            pass
                    
                    # Extract colors from content if not already found
                    if not colors:
                        color_keywords = ['black', 'white', 'red', 'blue', 'green', 'yellow', 'grey', 'gray', 
                                        'brown', 'pink', 'purple', 'orange', 'navy', 'multi-color', 'multicolor']
                        content_lower = content.lower()
                        for color in color_keywords:
                            if color in content_lower:
                                colors.append(color.title())
                        colors = list(set(colors))  # Remove duplicates
            
            # Extract category from URL or use JSON data
            category = category_from_json if category_from_json else 'Unknown'
            subcategory = ''
            
            # If no category from JSON, extract from URL
            if category == 'Unknown':
                url_parts = url.split('/')
                if '/w/' in url:
                    w_index = url_parts.index('w')
                    if w_index + 1 < len(url_parts):
                        category_part = url_parts[w_index + 1]
                        if 'mens' in category_part:
                            category = 'Men'
                        elif 'womens' in category_part:
                            category = 'Women'
                        elif 'kids' in category_part:
                            category = 'Kids'
                        elif 'sale' in category_part:
                            category = 'Sale'
                        
                        if 'shoes' in category_part:
                            subcategory = 'Shoes'
                        elif 'clothing' in category_part:
                            subcategory = 'Clothing'
            
            # Generate unique ID
            product_id = hashlib.md5(f"{name}{url}".encode()).hexdigest()[:16]
            
            # Create product object
            product = Product(
                id=product_id,
                name=name,
                price=price,
                category=category,
                subcategory=subcategory,
                description=description,
                colors=colors,
                sizes=sizes,
                images=images,
                url=url,
                availability=availability,
                sku=sku,
                rating=float(rating) if rating else None,
                reviews_count=int(reviews_count) if reviews_count else None,
                tags=[category, subcategory] if subcategory else [category],
                crawled_at=datetime.now().isoformat()
            )
            
            return product
            
        except Exception as e:
            print(f"❌ Error extracting product data from {url}: {e}")
            return None
    
    def _save_product_to_db(self, product: Product):
        """Save product to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Generate content hash for deduplication
            content_hash = self._generate_content_hash(asdict(product))
            
            cursor.execute("""
                INSERT OR REPLACE INTO products 
                (id, name, price, category, subcategory, description, colors, sizes, 
                 images, url, availability, sku, rating, reviews_count, tags, crawled_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product.id,
                product.name,
                product.price,
                product.category,
                product.subcategory,
                product.description,
                json.dumps(product.colors),
                json.dumps(product.sizes),
                json.dumps(product.images),
                product.url,
                product.availability,
                product.sku,
                product.rating,
                product.reviews_count,
                json.dumps(product.tags),
                product.crawled_at,
                content_hash
            ))
            
            conn.commit()
            
        except Exception as e:
            print(f"❌ Error saving product to database: {e}")
        finally:
            conn.close()
    
    async def crawl_product(self, url: str) -> Optional[Product]:
        """Crawl a single product page using curl"""
        try:
            print(f"🔍 Crawling: {url}")
            
            # Prepare curl command with Nike-specific schema
            curl_data = {
                "url": url,
                "onlyMainContent": True,
                "maxAge": 172800000,
                "formats": [
                    {
                        "type": "json",
                        "schema": {
                            "type": "object",
                            "required": [],
                            "properties": {
                                "product_name": {"type": "string"},
                                "price": {"type": "string"},
                                "description": {"type": "string"},
                                "colors": {"type": "array", "items": {"type": "string"}},
                                "sizes": {"type": "array", "items": {"type": "string"}},
                                "category": {"type": "string"},
                                "availability": {"type": "string"},
                                "rating": {"type": "number"},
                                "reviews_count": {"type": "number"},
                                "images": {"type": "array", "items": {"type": "string"}},
                                "sku": {"type": "string"},
                                "brand": {"type": "string"}
                            }
                        }
                    }
                ]
            }
            
            # Execute curl command
            curl_command = [
                "curl", "--request", "POST",
                "--url", "https://api.firecrawl.dev/v2/scrape",
                "--header", f"Authorization: Bearer {self.api_key}",
                "--header", "Content-Type: application/json",
                "--data", json.dumps(curl_data)
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                response_data = json.loads(result.stdout)
                print(f"🔍 Curl response: {response_data}")
                
                # Extract product data from curl response
                product = self._extract_product_from_curl_response(response_data, url)
                if product:
                    self.products.append(product)
                    self._save_product_to_db(product)
                    return product
            else:
                print(f"❌ Curl error: {result.stderr}")
            
        except Exception as e:
            print(f"❌ Error crawling {url}: {e}")
        
        return None

    def _extract_product_from_curl_response(self, response_data: Dict, url: str) -> Optional[Product]:
        """Extract product data from curl response"""
        try:
            # Extract data from the API response
            data = response_data.get('data', {})
            
            # Check if we have JSON format data
            json_data = None
            if isinstance(data, dict):
                # Look for JSON format in the data
                if 'json' in data:
                    json_data = data['json']
                elif 'formats' in data and isinstance(data['formats'], dict):
                    json_data = data['formats'].get('json', {})
            
            if not json_data:
                print(f"⚠️ No JSON data found in response for {url}")
                return None
            
            # Extract product information
            name = json_data.get('product_name', '') or json_data.get('brand', '') + ' Product'
            description = json_data.get('description', '')
            price = json_data.get('price', '')
            colors = json_data.get('colors', [])
            sizes = json_data.get('sizes', [])
            category = json_data.get('category', 'Unknown')
            availability = json_data.get('availability', 'Unknown')
            rating = json_data.get('rating')
            reviews_count = json_data.get('reviews_count')
            images = json_data.get('images', [])
            sku = json_data.get('sku', '')
            
            # Extract category from URL if not provided
            if category == 'Unknown':
                if 'mens' in url.lower():
                    category = 'Men'
                elif 'womens' in url.lower() or 'women' in url.lower():
                    category = 'Women'
                elif 'kids' in url.lower():
                    category = 'Kids'
            
            # Determine subcategory
            subcategory = ''
            if 'shoes' in url.lower() or 'sneakers' in url.lower():
                subcategory = 'Shoes'
            elif 'clothing' in url.lower() or 'apparel' in url.lower():
                subcategory = 'Clothing'
            
            # Generate unique ID
            product_id = hashlib.md5(f"{name}{url}".encode()).hexdigest()[:16]
            
            # Create product object
            product = Product(
                id=product_id,
                name=name,
                price=price,
                category=category,
                subcategory=subcategory,
                description=description,
                colors=colors,
                sizes=sizes,
                images=images,
                url=url,
                availability=availability,
                sku=sku,
                rating=float(rating) if rating else None,
                reviews_count=int(reviews_count) if reviews_count else None,
                tags=[category, subcategory] if subcategory else [category],
                crawled_at=datetime.now().isoformat()
            )
            
            return product
            
        except Exception as e:
            print(f"❌ Error extracting product from curl response for {url}: {e}")
            return None
    
    async def crawl_all_products(self, max_products: int = 500):
        """Crawl all Nike products"""
        print("🚀 Starting Nike product catalog crawl...")
        
        # Discover product URLs
        product_urls = await self.discover_product_urls()
        
        if not product_urls:
            print("❌ No product URLs discovered!")
            return
        
        # Limit the number of products to crawl
        product_urls = product_urls[:min(max_products, len(product_urls))]
        
        print(f"📦 Crawling {len(product_urls)} products...")
        
        # Crawl products with rate limiting
        successful_crawls = 0
        
        for i, url in enumerate(product_urls):
            product = await self.crawl_product(url)
            
            if product:
                successful_crawls += 1
                print(f"✅ ({i+1}/{len(product_urls)}) Crawled: {product.name}")
            else:
                print(f"❌ ({i+1}/{len(product_urls)}) Failed to crawl: {url}")
            
            # Rate limiting - be respectful to Nike's servers
            await asyncio.sleep(3)
            
            # Progress update every 10 products
            if (i + 1) % 10 == 0:
                print(f"📊 Progress: {i+1}/{len(product_urls)} URLs processed, {successful_crawls} products extracted")
        
        print(f"🎉 Crawl completed! Successfully extracted {successful_crawls} products")
        
        # Export to JSON for easy access
        await self._export_to_json()
    
    async def _export_to_json(self):
        """Export all products to JSON files for easy retrieval"""
        print("📄 Exporting products to JSON...")
        
        # Export all products
        all_products_file = os.path.join(self.output_dir, "nike_products.json")
        with open(all_products_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(product) for product in self.products], f, indent=2, ensure_ascii=False)
        
        # Export by category
        categories = {}
        for product in self.products:
            if product.category not in categories:
                categories[product.category] = []
            categories[product.category].append(asdict(product))
        
        for category, products in categories.items():
            category_file = os.path.join(self.output_dir, f"nike_products_{category.lower()}.json")
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)
        
        # Create search index
        search_index = []
        for product in self.products:
            search_index.append({
                'id': product.id,
                'name': product.name,
                'category': product.category,
                'subcategory': product.subcategory,
                'price': product.price,
                'description': product.description,
                'tags': product.tags,
                'url': product.url
            })
        
        index_file = os.path.join(self.output_dir, "nike_search_index.json")
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(search_index, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(self.products)} products to JSON files")
    
    def get_stats(self) -> Dict:
        """Get crawling statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
        
        # Get category breakdown
        cursor.execute("SELECT category, COUNT(*) FROM products GROUP BY category")
        categories = dict(cursor.fetchall())
        
        # Get price distribution
        cursor.execute("SELECT AVG(CAST(REPLACE(REPLACE(price, '$', ''), ',', '') AS REAL)) FROM products WHERE price != ''")
        avg_price = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_products': total_products,
            'categories': categories,
            'average_price': round(avg_price, 2) if avg_price else 0,
            'database_path': self.db_path,
            'export_directory': self.output_dir
        }


async def main():
    """Main crawler execution"""
    # Initialize crawler with API key
    api_key = "fc-f31bab16fdf84e42b315b49f61f15305"  # Using the key from the existing file
    crawler = NikeCrawler(api_key=api_key, output_dir="data/nike")
    
    try:
        # Crawl products (limit to 10 for initial test)
        await crawler.crawl_all_products(max_products=10)
        
        # Print statistics
        stats = crawler.get_stats()
        print("\n📊 CRAWLING STATISTICS:")
        print(f"Total products: {stats['total_products']}")
        print(f"Categories: {stats['categories']}")
        print(f"Average price: ${stats['average_price']}")
        print(f"Database: {stats['database_path']}")
        print(f"JSON exports: {stats['export_directory']}")
        
    except Exception as e:
        print(f"❌ Crawler failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())