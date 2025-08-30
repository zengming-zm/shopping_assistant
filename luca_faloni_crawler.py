#!/usr/bin/env python3

"""
Simplified crawler for Luca Faloni to build a vector database
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
import os
from typing import List, Dict, Any

class LucaFaloniCrawler:
    def __init__(self):
        self.base_url = "https://lucafaloni.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ShopTalk-Bot/1.0 (Shopping Assistant)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.documents = []
        self.visited_urls = set()
        
    def crawl(self):
        """Main crawling method"""
        print("🕷️ Starting Luca Faloni crawl...")
        
        # Key pages to crawl
        urls_to_crawl = [
            self.base_url,
            f"{self.base_url}/pages/our-story",
            f"{self.base_url}/pages/faq", 
            f"{self.base_url}/pages/returns-exchanges",
            f"{self.base_url}/pages/care-guide",
            f"{self.base_url}/pages/size-guide",
            f"{self.base_url}/pages/craftsmanship",
        ]
        
        # Add product collection pages
        product_categories = [
            "/collections/shirts",
            "/collections/polos-t-shirts", 
            "/collections/knitwear",
            "/collections/trousers-shorts",
            "/collections/jackets-suits",
            "/collections/accessories"
        ]
        
        for category in product_categories:
            urls_to_crawl.append(f"{self.base_url}{category}")
        
        # Crawl each URL
        for url in urls_to_crawl:
            try:
                print(f"📄 Crawling: {url}")
                self.crawl_page(url)
                time.sleep(1)  # Be polite
            except Exception as e:
                print(f"❌ Error crawling {url}: {e}")
                continue
        
        print(f"✅ Crawled {len(self.documents)} documents")
        return self.documents
    
    def crawl_page(self, url: str):
        """Crawl a single page"""
        if url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content
            document = self.extract_content(url, soup)
            if document and document['text'].strip():
                self.documents.append(document)
                print(f"  ✓ Extracted {len(document['text'])} characters")
            
        except Exception as e:
            print(f"  ❌ Failed to crawl {url}: {e}")
    
    def extract_content(self, url: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract content from a page"""
        
        # Get title
        title_elem = soup.find('title')
        title = title_elem.get_text().strip() if title_elem else "Unknown"
        
        # Remove unwanted elements
        for elem in soup(['script', 'style', 'nav', 'footer', 'header']):
            elem.decompose()
        
        # Extract main content
        main_content = ""
        
        # Try to find main content areas
        content_selectors = [
            'main',
            '.main-content',
            '.content',
            '[role="main"]',
            '.page-content',
            '.product-info',
            '.collection-description'
        ]
        
        main_elem = None
        for selector in content_selectors:
            main_elem = soup.select_one(selector)
            if main_elem:
                break
        
        if main_elem:
            main_content = main_elem.get_text(separator=' ', strip=True)
        else:
            # Fallback: get body content
            body = soup.find('body')
            if body:
                main_content = body.get_text(separator=' ', strip=True)
        
        # Clean up text
        main_content = re.sub(r'\s+', ' ', main_content).strip()
        
        # Determine section type
        section = self.classify_page(url, title, main_content)
        
        # Extract metadata
        meta = self.extract_metadata(url, soup, main_content)
        
        return {
            'id': f"luca_faloni_{len(self.documents)}",
            'shop_id': 'luca_faloni',
            'url': url,
            'title': title,
            'section': section,
            'text': main_content,
            'lang': 'en',
            'ts_fetched': datetime.utcnow().isoformat(),
            'meta': meta
        }
    
    def classify_page(self, url: str, title: str, content: str) -> str:
        """Classify page type"""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()
        
        if any(term in url_lower for term in ['/collections/', '/products/', 'shirt', 'polo', 'knitwear', 'trouser', 'jacket']):
            return 'product'
        elif any(term in url_lower for term in ['return', 'exchange', 'shipping', 'faq', 'care', 'size']):
            return 'policy'
        elif any(term in url_lower for term in ['story', 'about', 'craftsmanship']):
            return 'about'
        elif 'review' in content_lower or 'rating' in content_lower:
            return 'review'
        else:
            return 'other'
    
    def extract_metadata(self, url: str, soup: BeautifulSoup, content: str) -> Dict[str, Any]:
        """Extract metadata from page"""
        meta = {}
        
        # Extract prices
        price_patterns = [
            r'[$£€¥][\d,]+\.?\d*',
            r'\d+\s*[$£€¥]',
            r'Price.*?(\d+)',
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, content)
            if matches:
                meta['prices'] = matches[:3]  # Keep first 3 prices
                break
        
        # Extract product details
        if 'collection' in url or 'product' in url:
            # Look for material mentions
            materials = re.findall(r'\b(cotton|wool|silk|linen|cashmere|merino|alpaca)\b', content.lower())
            if materials:
                meta['materials'] = list(set(materials))
            
            # Look for size mentions
            sizes = re.findall(r'\b(XS|S|M|L|XL|XXL|\d{1,2})\b', content)
            if sizes:
                meta['sizes'] = list(set(sizes))
        
        # Extract key phrases
        if 'italian' in content.lower():
            meta['origin'] = 'Italian'
        if 'handmade' in content.lower() or 'artisan' in content.lower():
            meta['craftsmanship'] = 'handmade'
        
        return meta
    
    def save_documents(self, filename: str = 'luca_faloni_documents.json'):
        """Save documents to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved {len(self.documents)} documents to {filename}")

def create_simple_vectors():
    """Create simple text-based vectors for search"""
    print("📖 Creating simple text vectors...")
    
    if not os.path.exists('luca_faloni_documents.json'):
        print("❌ No documents file found. Run crawler first.")
        return
    
    with open('luca_faloni_documents.json', 'r') as f:
        documents = json.load(f)
    
    # Create a simple search index
    search_index = {}
    
    for doc in documents:
        doc_id = doc['id']
        text = doc['text'].lower()
        title = doc['title'].lower()
        
        # Extract keywords
        keywords = set()
        
        # Add words from title and text
        words = re.findall(r'\b[a-z]{3,}\b', f"{title} {text}")
        keywords.update(words)
        
        # Add specific fashion terms
        fashion_terms = [
            'shirt', 'polo', 'knitwear', 'sweater', 'cardigan', 'jacket', 'suit',
            'trousers', 'pants', 'shorts', 'accessories', 'cotton', 'wool', 'silk',
            'linen', 'cashmere', 'italian', 'handmade', 'luxury', 'quality'
        ]
        
        for term in fashion_terms:
            if term in text:
                keywords.add(term)
        
        search_index[doc_id] = {
            'keywords': list(keywords),
            'title': doc['title'],
            'url': doc['url'],
            'section': doc['section'],
            'text': doc['text'][:500]  # First 500 chars for preview
        }
    
    # Save search index
    with open('luca_faloni_search_index.json', 'w') as f:
        json.dump(search_index, f, indent=2)
    
    print(f"🔍 Created search index with {len(search_index)} entries")
    return search_index

def search_documents(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Simple text search through documents"""
    if not os.path.exists('luca_faloni_search_index.json'):
        print("❌ No search index found. Run create_simple_vectors() first.")
        return []
    
    with open('luca_faloni_search_index.json', 'r') as f:
        search_index = json.load(f)
    
    query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
    
    # Score documents
    results = []
    for doc_id, doc_data in search_index.items():
        keywords = set(doc_data['keywords'])
        
        # Calculate simple overlap score
        overlap = len(query_words.intersection(keywords))
        if overlap > 0:
            score = overlap / len(query_words.union(keywords))
            results.append({
                'doc_id': doc_id,
                'title': doc_data['title'],
                'url': doc_data['url'],
                'section': doc_data['section'],
                'snippet': doc_data['text'],
                'score': score
            })
    
    # Sort by score and return top results
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]

def main():
    """Main function"""
    print("🛒 Luca Faloni Vector Database Builder")
    print()
    
    # Step 1: Crawl the website
    crawler = LucaFaloniCrawler()
    documents = crawler.crawl()
    crawler.save_documents()
    
    # Step 2: Create search vectors
    search_index = create_simple_vectors()
    
    # Step 3: Test search
    print("\n🔍 Testing search functionality:")
    test_queries = [
        "cotton shirts",
        "wool knitwear", 
        "return policy",
        "Italian craftsmanship",
        "size guide"
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = search_documents(query, 3)
        for result in results:
            print(f"  📄 {result['title']} (score: {result['score']:.3f})")
            print(f"      {result['url']}")
            print(f"      {result['snippet'][:100]}...")

if __name__ == "__main__":
    main()