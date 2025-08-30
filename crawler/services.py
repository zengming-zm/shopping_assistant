import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime
from typing import List, Optional, Set, Dict, Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from playwright.async_api import async_playwright, Browser, Page
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from shared.config import config, env_config
from shared.models import CrawlRequest, CrawlStatus, Document, DocumentSection


logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.embeddings_model = None
        self.qdrant_client = None
        self.crawl_statuses: Dict[str, CrawlStatus] = {}
        
    async def initialize(self):
        self.embeddings_model = SentenceTransformer(config.embeddings_model)
        self.qdrant_client = QdrantClient(url=env_config.QDRANT_URL)
        
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        
        try:
            collections = await self.qdrant_client.get_collections()
            if 'documents' not in [c.name for c in collections.collections]:
                await self.qdrant_client.create_collection(
                    collection_name="documents",
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.warning(f"Could not check/create collection: {e}")
    
    async def cleanup(self):
        if self.browser:
            await self.browser.close()
    
    async def crawl_shop(self, request: CrawlRequest):
        shop_id = request.shop_id
        
        status = CrawlStatus(
            shop_id=shop_id,
            status="running",
            pages_discovered=0,
            pages_processed=0,
            pages_indexed=0,
            started_at=datetime.utcnow()
        )
        self.crawl_statuses[shop_id] = status
        
        try:
            urls_to_crawl = await self._discover_urls(request.shop_url, request.include, request.exclude)
            status.pages_discovered = len(urls_to_crawl)
            
            for url in urls_to_crawl:
                try:
                    await self._process_url(shop_id, url)
                    status.pages_processed += 1
                    status.pages_indexed += 1
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    status.last_error = str(e)
                
                await asyncio.sleep(config.crawler.get('rate_limit_delay', 1.0))
            
            status.status = "completed"
            status.completed_at = datetime.utcnow()
            
        except Exception as e:
            status.status = "failed"
            status.last_error = str(e)
            status.completed_at = datetime.utcnow()
    
    async def _discover_urls(self, base_url: str, include_patterns: List[str], exclude_patterns: List[str]) -> List[str]:
        discovered_urls = set()
        
        if not self._can_crawl(base_url):
            logger.warning(f"Crawling not allowed for {base_url} per robots.txt")
            return []
        
        discovered_urls.add(base_url)
        
        try:
            sitemap_urls = await self._get_sitemap_urls(base_url)
            discovered_urls.update(sitemap_urls)
        except Exception as e:
            logger.warning(f"Could not fetch sitemap for {base_url}: {e}")
        
        try:
            crawled_urls = await self._crawl_for_links(base_url, max_pages=50)
            discovered_urls.update(crawled_urls)
        except Exception as e:
            logger.warning(f"Could not crawl for links: {e}")
        
        filtered_urls = []
        for url in discovered_urls:
            if self._should_include_url(url, include_patterns, exclude_patterns):
                filtered_urls.append(url)
        
        return filtered_urls[:config.crawler.get('max_pages_per_site', 1000)]
    
    def _can_crawl(self, url: str) -> bool:
        if not config.crawler.get('respect_robots_txt', True):
            return True
        
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            user_agent = config.crawler.get('user_agent', 'ShopTalk-Bot/1.0')
            return rp.can_fetch(user_agent, url)
        except Exception:
            return True
    
    async def _get_sitemap_urls(self, base_url: str) -> List[str]:
        parsed = urlparse(base_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(sitemap_url)
            response.raise_for_status()
            
            urls = re.findall(r'<loc>(.*?)</loc>', response.text)
            return urls[:100]  # Limit sitemap URLs
    
    async def _crawl_for_links(self, start_url: str, max_pages: int = 50) -> List[str]:
        found_urls = set()
        to_visit = {start_url}
        visited = set()
        
        page = await self.browser.new_page()
        
        try:
            while to_visit and len(visited) < max_pages:
                url = to_visit.pop()
                if url in visited:
                    continue
                
                try:
                    await page.goto(url, timeout=30000)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                    links = await page.evaluate("""
                        () => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)
                    """)
                    
                    base_domain = urlparse(start_url).netloc
                    for link in links:
                        if urlparse(link).netloc == base_domain:
                            found_urls.add(link)
                            if len(visited) < max_pages // 2:
                                to_visit.add(link)
                    
                    visited.add(url)
                    
                except Exception as e:
                    logger.warning(f"Could not crawl {url}: {e}")
                    visited.add(url)
                
                await asyncio.sleep(0.5)
        
        finally:
            await page.close()
        
        return list(found_urls)
    
    def _should_include_url(self, url: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
        if exclude_patterns:
            for pattern in exclude_patterns:
                if re.search(pattern, url):
                    return False
        
        if include_patterns:
            for pattern in include_patterns:
                if re.search(pattern, url):
                    return True
            return False
        
        return True
    
    async def _process_url(self, shop_id: str, url: str):
        page = await self.browser.new_page()
        
        try:
            await page.goto(url, timeout=config.crawler.get('timeout', 30) * 1000)
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            html = await page.content()
            
            text = trafilatura.extract(
                html,
                favor_precision=True,
                include_comments=True,
                include_tables=True
            )
            
            if not text or len(text.strip()) < 100:
                return
            
            title = await page.title()
            
            section = self._detect_section(url, title, text)
            
            meta = await self._extract_metadata(page, text)
            
            document = Document(
                shop_id=shop_id,
                url=url,
                title=title or "Untitled",
                section=section,
                text=text,
                ts_fetched=datetime.utcnow(),
                meta=meta
            )
            
            await self._index_document(document)
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            raise
        finally:
            await page.close()
    
    def _detect_section(self, url: str, title: str, text: str) -> DocumentSection:
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        text_lower = text.lower()
        
        if any(term in url_lower for term in ['product', '/p/', '/item/', 'catalog']):
            return DocumentSection.PRODUCT
        elif any(term in url_lower for term in ['policy', 'terms', 'privacy', 'shipping', 'return']):
            return DocumentSection.POLICY
        elif any(term in url_lower for term in ['faq', 'help', 'support']):
            return DocumentSection.FAQ
        elif any(term in url_lower for term in ['review', 'rating', 'testimonial']):
            return DocumentSection.REVIEW
        elif any(term in text_lower for term in ['$', 'price', 'buy', 'add to cart', 'product']):
            return DocumentSection.PRODUCT
        else:
            return DocumentSection.OTHER
    
    async def _extract_metadata(self, page: Page, text: str) -> Dict[str, Any]:
        meta = {}
        
        try:
            price_element = await page.query_selector('[data-price], .price, .cost, [class*="price"]')
            if price_element:
                price_text = await price_element.inner_text()
                price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                if price_match:
                    meta['price'] = float(price_match.group())
        except Exception:
            pass
        
        try:
            breadcrumbs = await page.query_selector_all('[data-breadcrumb], .breadcrumb, nav[aria-label="breadcrumb"] a')
            if breadcrumbs:
                crumbs = []
                for crumb in breadcrumbs[:5]:
                    text = await crumb.inner_text()
                    if text.strip():
                        crumbs.append(text.strip())
                meta['breadcrumbs'] = crumbs
        except Exception:
            pass
        
        try:
            images = await page.query_selector_all('img[src*="product"], img[alt*="product"], .product-image img')
            if images:
                img_urls = []
                for img in images[:3]:
                    src = await img.get_attribute('src')
                    if src:
                        img_urls.append(src)
                meta['images'] = img_urls
        except Exception:
            pass
        
        return meta
    
    async def _index_document(self, document: Document):
        chunks = self._chunk_text(document.text)
        
        for i, chunk_text in enumerate(chunks):
            vector = self.embeddings_model.encode(chunk_text).tolist()
            
            point = PointStruct(
                id=f"{document.id}_{i}",
                vector=vector,
                payload={
                    "shop_id": document.shop_id,
                    "doc_id": document.id,
                    "url": document.url,
                    "title": document.title,
                    "section": document.section.value,
                    "text": chunk_text,
                    "start_char": i * 800,  # Approximate
                    "end_char": min((i + 1) * 800, len(document.text)),
                    "ts_fetched": document.ts_fetched.isoformat(),
                    "meta": document.meta
                }
            )
            
            self.qdrant_client.upsert(
                collection_name="documents",
                points=[point]
            )
    
    def _chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        chunk_size = chunk_size or config.rag.get('chunk_size', 1000)
        overlap = overlap or config.rag.get('chunk_overlap', 200)
        
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            last_period = text.rfind('.', start, end)
            last_newline = text.rfind('\n', start, end)
            
            cut_point = max(last_period, last_newline)
            if cut_point > start:
                end = cut_point + 1
            
            chunks.append(text[start:end])
            start = end - overlap
        
        return [chunk.strip() for chunk in chunks if len(chunk.strip()) > 50]
    
    async def get_crawl_status(self, shop_id: str) -> CrawlStatus:
        if shop_id not in self.crawl_statuses:
            return CrawlStatus(
                shop_id=shop_id,
                status="not_started",
                pages_discovered=0,
                pages_processed=0,
                pages_indexed=0
            )
        
        return self.crawl_statuses[shop_id]
    
    async def reindex_urls(self, shop_id: str, urls: List[str] = None):
        if urls:
            for url in urls:
                await self._process_url(shop_id, url)
        else:
            status = await self.get_crawl_status(shop_id)
            if status.status == "completed":
                request = CrawlRequest(shop_id=shop_id, shop_url="")
                await self.crawl_shop(request)