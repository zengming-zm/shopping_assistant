"""
Universal ShopTalk - Dynamic Website Crawler and RAG System
Enhanced with Product-Focused Crawling and Structured Data Extraction
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
import asyncio
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote
from typing import List, Dict, Any, Optional
import hashlib
import google.generativeai as genai
from dotenv import load_dotenv

# Import the enhanced product crawler
from product_crawler import EnhancedProductCrawler, run_product_crawler
from multithreaded_product_crawler import run_multithreaded_product_crawler
from comprehensive_crawler import run_comprehensive_crawler
# from google_search_rag import GoogleSearchRAG  # DEPRECATED: Using SearchTool instead
from chat import UniversalChatRAG, SearchTool

load_dotenv()

st.set_page_config(
    page_title="Universal ShopTalk", 
    page_icon="🌐",
    layout="wide"
)

class UniversalCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ShopTalk-Universal/1.0 (Shopping Assistant)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def format_product_text_simple(self, product: Dict[str, Any]) -> str:
        """Format product data into simple text"""
        text_parts = []
        
        if product.get('product_name'):
            text_parts.append(f"Product: {product['product_name']}")
        if product.get('description'):
            text_parts.append(f"Description: {product['description']}")
        if product.get('prices'):
            text_parts.append(f"Prices: {', '.join(product['prices'])}")
        
        return " | ".join(text_parts)
        
    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for use as shop_id"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    def get_safe_filename(self, domain: str) -> str:
        """Create safe filename from domain"""
        safe = re.sub(r'[^a-zA-Z0-9._-]', '_', domain)
        return safe
    
    def discover_urls(self, base_url: str, max_pages: int = 15) -> List[str]:
        """Discover URLs to crawl from the website"""
        urls_to_crawl = [base_url]
        discovered = set([base_url])
        
        try:
            # Try to get sitemap first
            sitemap_urls = [
                urljoin(base_url, '/sitemap.xml'),
                urljoin(base_url, '/sitemap_index.xml'),
                urljoin(base_url, '/robots.txt')
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    response = self.session.get(sitemap_url, timeout=10)
                    if response.status_code == 200:
                        # Simple sitemap parsing
                        urls_found = re.findall(r'<loc>(.*?)</loc>', response.text)
                        for url in urls_found[:max_pages-1]:
                            if url not in discovered and self.is_valid_url(url, base_url):
                                urls_to_crawl.append(url)
                                discovered.add(url)
                                if len(urls_to_crawl) >= max_pages:
                                    break
                        if len(urls_to_crawl) >= max_pages:
                            break
                except:
                    continue
            
            # If we don't have enough URLs, crawl main page for links
            if len(urls_to_crawl) < max_pages:
                try:
                    response = self.session.get(base_url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        links = soup.find_all('a', href=True)
                        
                        for link in links:
                            href = link['href']
                            full_url = urljoin(base_url, href)
                            
                            if full_url not in discovered and self.is_valid_url(full_url, base_url):
                                urls_to_crawl.append(full_url)
                                discovered.add(full_url)
                                if len(urls_to_crawl) >= max_pages:
                                    break
                except:
                    pass
        
        except Exception as e:
            st.warning(f"URL discovery warning: {e}")
        
        return urls_to_crawl[:max_pages]
    
    def is_valid_url(self, url: str, base_url: str) -> bool:
        """Check if URL is valid for crawling"""
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)
        
        # Same domain only
        if parsed_url.netloc.lower() != parsed_base.netloc.lower():
            return False
        
        # Skip certain file types and patterns
        skip_patterns = [
            r'\.(jpg|jpeg|png|gif|svg|ico|css|js|pdf|zip|exe)$',
            r'#',
            r'\?.*',
            r'/admin',
            r'/login',
            r'/cart',
            r'/checkout',
            r'/search'
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, url.lower()):
                return False
        
        return True
    
    def crawl_website(self, base_url: str, progress_callback=None) -> List[Dict[str, Any]]:
        """Crawl a website and return documents"""
        domain = self.get_domain_from_url(base_url)
        documents = []
        
        if progress_callback:
            progress_callback("Discovering URLs...")
        
        urls_to_crawl = self.discover_urls(base_url)
        
        if progress_callback:
            progress_callback(f"Found {len(urls_to_crawl)} URLs to crawl")
        
        for i, url in enumerate(urls_to_crawl):
            try:
                if progress_callback:
                    progress_callback(f"Crawling ({i+1}/{len(urls_to_crawl)}): {url}")
                
                doc = self.crawl_page(url, domain)
                if doc and doc['text'].strip():
                    documents.append(doc)
                
                time.sleep(0.5)  # Be polite
                
            except Exception as e:
                st.warning(f"Error crawling {url}: {e}")
                continue
        
        return documents
    
    def crawl_page(self, url: str, domain: str) -> Dict[str, Any]:
        """Crawl a single page"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content
            return self.extract_content(url, soup, domain)
            
        except Exception as e:
            raise Exception(f"Failed to crawl {url}: {e}")
    
    def extract_content(self, url: str, soup: BeautifulSoup, domain: str) -> Dict[str, Any]:
        """Extract content from a page"""
        # Get title
        title_elem = soup.find('title')
        title = title_elem.get_text().strip() if title_elem else "Unknown"
        
        # Remove unwanted elements
        for elem in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            elem.decompose()
        
        # Extract main content
        main_content = ""
        
        # Try to find main content areas
        content_selectors = [
            'main', 'article', '.main-content', '.content', '[role="main"]',
            '.page-content', '.product-info', '.collection-description',
            '.entry-content', '.post-content'
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
        
        # Create unique document ID
        doc_id = hashlib.md5(url.encode()).hexdigest()
        
        return {
            'id': doc_id,
            'shop_id': domain,
            'url': url,
            'title': title,
            'section': self.classify_page(url, title, main_content),
            'text': main_content,
            'lang': 'en',
            'ts_fetched': datetime.utcnow().isoformat(),
            'meta': self.extract_metadata(url, soup, main_content)
        }
    
    def classify_page(self, url: str, title: str, content: str) -> str:
        """Classify page type"""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()
        
        if any(term in url_lower for term in ['/product', '/item', '/shop', '/store']):
            return 'product'
        elif any(term in url_lower for term in ['about', 'story', 'company', 'history']):
            return 'about'
        elif any(term in url_lower for term in ['contact', 'support', 'help', 'faq']):
            return 'support'
        elif any(term in url_lower for term in ['policy', 'terms', 'privacy', 'return', 'shipping']):
            return 'policy'
        elif any(term in url_lower for term in ['blog', 'news', 'article']):
            return 'content'
        else:
            return 'other'
    
    def extract_metadata(self, url: str, soup: BeautifulSoup, content: str) -> Dict[str, Any]:
        """Extract metadata from page"""
        meta = {}
        
        # Extract prices
        price_patterns = [r'[$£€¥][\d,]+\.?\d*', r'\d+\s*[$£€¥]']
        for pattern in price_patterns:
            matches = re.findall(pattern, content)
            if matches:
                meta['prices'] = matches[:3]
                break
        
        # Extract meta description
        desc_elem = soup.find('meta', attrs={'name': 'description'})
        if desc_elem:
            meta['description'] = desc_elem.get('content', '')
        
        return meta

class UniversalRAG:
    def __init__(self):
        self.model = self.setup_gemini()
        
    def setup_gemini(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-1.5-flash')
        return None
    
    def get_website_data(self, domain: str) -> tuple:
        """Load documents and search index for a domain"""
        safe_domain = re.sub(r'[^a-zA-Z0-9._-]', '_', domain)
        
        documents_file = f'data_{safe_domain}_documents.json'
        index_file = f'data_{safe_domain}_index.json'
        
        documents = {}
        search_index = {}
        
        if os.path.exists(documents_file):
            with open(documents_file, 'r', encoding='utf-8') as f:
                docs_list = json.load(f)
                documents = {doc['id']: doc for doc in docs_list}
        
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                search_index = json.load(f)
        
        return documents, search_index
    
    def save_website_data(self, domain: str, documents: List[Dict[str, Any]]):
        """Save documents and create search index"""
        safe_domain = re.sub(r'[^a-zA-Z0-9._-]', '_', domain)
        
        documents_file = f'data_{safe_domain}_documents.json'
        index_file = f'data_{safe_domain}_index.json'
        
        # Save documents
        with open(documents_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        
        # Create search index
        search_index = {}
        for doc in documents:
            doc_id = doc['id']
            text = doc['text'].lower()
            title = doc['title'].lower()
            
            # Extract keywords
            keywords = set()
            words = re.findall(r'\b[a-z]{3,}\b', f"{title} {text}")
            keywords.update(words)
            
            search_index[doc_id] = {
                'keywords': list(keywords),
                'title': doc['title'],
                'url': doc['url'],
                'section': doc['section'],
                'text': doc['text'][:500]
            }
        
        # Save search index
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(search_index, f, indent=2)
        
        return len(documents)
    
    def search_website(self, domain: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search website documents"""
        documents, search_index = self.get_website_data(domain)
        
        if not search_index:
            return []
        
        query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
        
        results = []
        for doc_id, doc_data in search_index.items():
            keywords = set(doc_data['keywords'])
            
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
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    def format_product_text(self, product: Dict[str, Any]) -> str:
        """Format product data into searchable text"""
        text_parts = []
        
        # Product name
        if product.get('product_name'):
            text_parts.append(f"Product: {product['product_name']}")
        
        # Description
        if product.get('description'):
            text_parts.append(f"Description: {product['description']}")
        
        # Prices
        if product.get('prices'):
            text_parts.append(f"Prices: {', '.join(product['prices'])}")
        
        # Sizes
        if product.get('sizes'):
            text_parts.append(f"Available sizes: {', '.join(product['sizes'])}")
        
        # Attributes
        attributes = product.get('attributes', {})
        if attributes.get('colors'):
            text_parts.append(f"Colors: {', '.join(attributes['colors'])}")
        if attributes.get('materials'):
            text_parts.append(f"Materials: {', '.join(attributes['materials'])}")
        if attributes.get('brand'):
            text_parts.append(f"Brand: {attributes['brand']}")
        
        # Bullet points
        if product.get('bullet_points'):
            text_parts.append("Features:")
            text_parts.extend([f"• {point}" for point in product['bullet_points']])
        
        # Availability
        if product.get('availability'):
            text_parts.append(f"Availability: {product['availability'].replace('_', ' ').title()}")
        
        return " | ".join(text_parts)
    
    def generate_response(self, domain: str, user_message: str) -> str:
        """Generate response using RAG with enhanced product support"""
        if not self.model:
            return "Please configure GOOGLE_API_KEY in your .env file to use the AI assistant."
        
        # Search domain-specific content
        search_results = self.search_website(domain, user_message)
        
        context = ""
        product_context = ""
        
        if search_results:
            context = f"\n{domain.upper()} Website Information:\n"
            for result in search_results:
                context += f"- {result['title']}: {result['snippet'][:200]}...\n"
                context += f"  Source: {result['url']}\n\n"
                
                # Check if this is product data
                if result['section'] == 'product':
                    try:
                        # Load full document to get product metadata
                        documents, _ = self.get_website_data(domain)
                        if result['doc_id'] in documents:
                            doc = documents[result['doc_id']]
                            if 'product_data' in doc.get('meta', {}):
                                product_data = doc['meta']['product_data']
                                product_context += f"\n🛍️ Product: {product_data.get('product_name', 'Unknown')}\n"
                                product_context += f"   Prices: {product_data.get('prices', [])}\n"
                                product_context += f"   Sizes: {product_data.get('sizes', [])}\n"
                                product_context += f"   Availability: {product_data.get('availability', 'unknown')}\n"
                                if product_data.get('attributes', {}).get('colors'):
                                    product_context += f"   Colors: {product_data['attributes']['colors']}\n"
                                if product_data.get('attributes', {}).get('materials'):
                                    product_context += f"   Materials: {product_data['attributes']['materials']}\n"
                    except:
                        pass
        else:
            context = f"\nNo specific information found for {domain}. Please provide general assistance.\n"
        
        prompt = f"""You are ShopTalk, a universal shopping assistant that helps customers with questions about any website.

Current website: {domain}
Customer question: {user_message}

{context}
{product_context}

Instructions:
- Use the provided website information to answer questions about products, services, and policies
- For product questions, include specific details like prices, sizes, colors, materials, and availability when available
- If you have specific information from the website, reference it with source URLs
- If you don't have specific information, acknowledge this and provide helpful general guidance
- Maintain a helpful, professional tone appropriate for customer service
- Focus on being accurate and citing sources when available
- For product recommendations, consider the customer's needs and highlight relevant features

Respond as a knowledgeable shopping assistant for {domain}.
"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"I apologize, but I encountered an error generating a response: {str(e)}"

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "current_website" not in st.session_state:
        st.session_state.current_website = ""
    if "indexed_websites" not in st.session_state:
        st.session_state.indexed_websites = get_indexed_websites()
    if "chat_provider" not in st.session_state:
        st.session_state.chat_provider = "gemini"
    if "chat_rag" not in st.session_state:
        st.session_state.chat_rag = UniversalChatRAG()
    
    # Ensure persistent chat sessions are maintained across Streamlit reruns
    # This is especially important for Gemini's chat sessions
    if hasattr(st.session_state, 'chat_rag') and st.session_state.chat_rag:
        # The chat_rag object persists in session state, maintaining Gemini chat sessions
        pass

def get_indexed_websites() -> List[str]:
    """Get list of domains that have been used (for Google Search RAG)"""
    # Since we're using Google Search, we don't need local files
    # Return empty list initially, will populate as users chat with domains
    return []

def create_google_search_function():
    """
    Create a Google Search function compatible with SearchTool
    Returns a function that can be used by SearchTool for actual Google searches
    """
    # Check if Google Search API is configured
    api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
    cse_id = os.getenv('GOOGLE_CSE_ID')
    
    if api_key and cse_id:
        try:
            from googleapiclient.discovery import build
            service = build("customsearch", "v1", developerKey=api_key)
            
            def google_search_function(domain: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
                """Google Search function compatible with SearchTool"""
                try:
                    # Execute Google Custom Search
                    result = service.cse().list(
                        q=f"{query} site:{domain}",  # Restrict search to domain
                        cx=cse_id,
                        num=min(limit, 10)  # Google CSE allows max 10 results per request
                    ).execute()
                    
                    search_results = []
                    if 'items' in result:
                        for i, item in enumerate(result['items']):
                            search_results.append({
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet', ''),
                                'url': item.get('link', ''),
                                'source': 'google_search',
                                'score': 1.0 - (i * 0.1)  # Decreasing score by relevance
                            })
                    
                    print(f"ming-debug: Google Search API returned {len(search_results)} results for '{query}' on {domain}")
                    return search_results
                    
                except Exception as e:
                    print(f"Google Search API error: {e}")
                    return [{
                        'title': 'Google Search Error',
                        'snippet': f'Unable to search Google for {query}',
                        'url': '',
                        'source': 'error',
                        'score': 0.0
                    }]
            
            return google_search_function
            
        except ImportError:
            print("Google API client not installed. Install with: pip install google-api-python-client")
        except Exception as e:
            print(f"Failed to initialize Google Search: {e}")
    
    # Return mock search function if Google Search API is not configured
    def mock_search_function(domain: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Mock search function for testing/demo purposes"""
        mock_results = []
        search_queries = [f"{query} {domain}", f"{domain} {query}", query]
        
        for i, search_query in enumerate(search_queries[:limit]):
            mock_results.append({
                'title': f'Search Results for {search_query}',
                'snippet': f'Comprehensive information about {search_query} from {domain}. Product details, pricing, and availability.',
                'url': f'https://{domain}/search?q={search_query.replace(" ", "+")}',
                'source': 'mock_search',
                'score': 0.9 - (i * 0.1)
            })
        
        return mock_results
    
    return mock_search_function

def main():
    st.title("🌐 Universal ShopTalk")
    st.subheader("Dynamic Website Crawler and Shopping Assistant")
    
    initialize_session_state()
    crawler = UniversalCrawler()
    # search_rag = GoogleSearchRAG()  # DEPRECATED: Using SearchTool instead
    chat_rag = st.session_state.chat_rag
    
    # Sidebar
    st.sidebar.title("Website Management")
    
    # AI Provider Selection
    available_providers = chat_rag.get_available_providers()
    if available_providers:
        st.sidebar.subheader("🤖 AI Configuration")
        
        # Provider selection
        current_provider = st.sidebar.selectbox(
            "Choose AI Model:",
            available_providers,
            index=available_providers.index(chat_rag.default_provider) if chat_rag.default_provider in available_providers else 0,
            format_func=lambda x: x.title()
        )
        chat_rag.set_provider(current_provider)
        
        # Response mode selection
        response_mode = st.sidebar.selectbox(
            "Response Mode:",
            ["normal", "thinking_react"],
            index=0 if chat_rag.get_response_mode() == "normal" else 1,
            format_func=lambda x: {
                "normal": "🎯 Normal",
                "thinking_react": "🧠 Thinking + ReAct (Intelligent)"
            }[x],
            help="Choose how the AI processes and responds to queries"
        )
        chat_rag.set_response_mode(response_mode)
        
        st.sidebar.info(f"Using: {current_provider.title()} | Mode: {response_mode.title()}")
        
        # Add mode descriptions
        mode_descriptions = {
            "normal": "🎯 Standard AI responses with optional search",
            "thinking_react": "🧠 Intelligent thinking + tool usage when needed"
        }
        st.sidebar.caption(f"ℹ️ {mode_descriptions[response_mode]}")
        
    else:
        st.sidebar.error("⚠ No AI providers available! Please configure API keys.")
    
    # URL input
    website_url = st.sidebar.text_input(
        "Enter website URL:",
        placeholder="https://example.com",
        help="Enter any website URL to crawl and chat with"
    )
    
    if website_url:
        domain = crawler.get_domain_from_url(website_url)
        
        # Check if domain has been used before
        is_used = domain in st.session_state.indexed_websites
        
        if is_used:
            st.sidebar.success(f"✅ Ready to chat with {domain}!")
        else:
            st.sidebar.info(f"🔍 Ready to search {domain} with Google!")
            
            # Crawl mode selection
            st.sidebar.subheader("🕷️ Crawling Mode")
            crawl_mode = st.sidebar.selectbox(
                "Choose crawling approach:",
                [
                    "🔍 Google Search Only",
                    "🔍 Comprehensive (All Products)", 
                    "🚀 Multi-threaded (Fast)", 
                    "🏪 Standard Product Focus",
                    "🕷️ General Content"
                ],
                index=0,
                help="Google Search Only: No local crawling, uses Google Search for real-time info"
            )
            
            # Handle Google Search Only mode
            if crawl_mode == "🔍 Google Search Only":
                if st.sidebar.button("🚀 Start Chatting", type="primary"):
                    # Add domain to used list
                    if domain not in st.session_state.indexed_websites:
                        st.session_state.indexed_websites.append(domain)
                    st.session_state.current_website = domain
                    st.rerun()
            
            # Performance settings for product crawling modes
            if crawl_mode in ["🔍 Comprehensive (All Products)", "🚀 Multi-threaded (Fast)", "🏪 Standard Product Focus"]:
                st.sidebar.subheader("⚡ Performance Settings")
                
                if crawl_mode == "🔍 Comprehensive (All Products)":
                    st.sidebar.info("🔍 Comprehensive mode uses advanced URL discovery to find ALL product categories")
                    max_workers = st.sidebar.slider("Concurrent workers:", min_value=2, max_value=6, value=4)
                    max_products = st.sidebar.slider("Max products to extract:", min_value=20, max_value=200, value=50)
                    use_comprehensive = True
                    use_multithreading = True
                
                elif crawl_mode == "🚀 Multi-threaded (Fast)":
                    st.sidebar.info("🚀 Fast multi-threaded crawling with basic URL discovery")
                    max_workers = st.sidebar.slider("Concurrent workers:", min_value=2, max_value=8, value=4)
                    max_products = st.sidebar.slider("Max products to extract:", min_value=10, max_value=100, value=30)
                    use_comprehensive = False
                    use_multithreading = True
                
                # else:  # Standard Product Focus
                #     st.sidebar.info("🏪 Standard single-threaded product crawling")
                #     max_workers = 1
                #     max_products = st.sidebar.slider("Max products to extract:", min_value=10, max_value=50, value=20)
                #     use_comprehensive = False
                #     use_multithreading = False
            
            # Product crawling modes
            if crawl_mode in ["🔍 Comprehensive (All Products)", "🚀 Multi-threaded (Fast)", "🏪 Standard Product Focus"]:
                
                # Set button text based on mode
                if crawl_mode == "🔍 Comprehensive (All Products)":
                    crawl_button_text = "🔍 Comprehensive Crawl"
                    crawl_description = f"Comprehensive discovery with {max_workers} workers..."
                elif crawl_mode == "🚀 Multi-threaded (Fast)":
                    crawl_button_text = "🚀 Multi-threaded Crawl"
                    crawl_description = f"Multi-threaded crawling with {max_workers} workers..."
                else:
                    crawl_button_text = "🏪 Standard Crawl"
                    crawl_description = "Single-threaded product crawling..."
                
                if st.sidebar.button(crawl_button_text, type="primary"):
                    with st.spinner(crawl_description):
                        progress_placeholder = st.empty()
                        start_time = time.time()
                        
                        def progress_callback(message):
                            elapsed = time.time() - start_time
                            progress_placeholder.text(f"🛍️ [{elapsed:.1f}s] {message}")
                        
                        try:
                            if use_comprehensive:
                                # Use comprehensive crawler
                                products = run_comprehensive_crawler(
                                    website_url,
                                    progress_callback,
                                    max_workers=max_workers,
                                    max_products=max_products
                                )
                            elif use_multithreading:
                                # Use multi-threaded crawler
                                products = run_multithreaded_product_crawler(
                                    website_url, 
                                    progress_callback, 
                                    max_workers=max_workers,
                                    max_urls=max_products
                                )
                            else:
                                # Use single-threaded crawler
                                products = run_product_crawler(website_url, progress_callback)
                            
                            if products:
                                progress_placeholder.text("💾 Saving product data...")
                                
                                # Convert products to document format for storage
                                documents = []
                                for product in products:
                                    doc = {
                                        'id': product['id'],
                                        'shop_id': domain,
                                        'url': product['url'],
                                        'title': product.get('product_name', 'Unknown Product'),
                                        'section': 'product',
                                        # Format product text for display
                                        'text': crawler.format_product_text_simple(product),
                                        'lang': 'en',
                                        'ts_fetched': product['extracted_at'],
                                        'meta': {
                                            'product_data': product,
                                            'prices': product.get('prices', []),
                                            'sizes': product.get('sizes', []),
                                            'attributes': product.get('attributes', {}),
                                            'availability': product.get('availability', 'unknown')
                                        }
                                    }
                                    documents.append(doc)
                                
                                # Note: Google Search RAG doesn't require local data storage
                                doc_count = len(documents)
                                
                                st.session_state.indexed_websites.append(domain)
                                progress_placeholder.empty()
                                
                                # Show product summary with performance stats
                                elapsed_total = time.time() - start_time
                                rate = len(products) / elapsed_total if elapsed_total > 0 else 0
                                
                                success_msg = f"🛍️ Successfully extracted {len(products)} products from {domain}"
                                if use_comprehensive:
                                    success_msg += f" in {elapsed_total:.1f}s ({rate:.1f} products/sec) using comprehensive discovery 🔍"
                                elif use_multithreading:
                                    success_msg += f" in {elapsed_total:.1f}s ({rate:.1f} products/sec) using {max_workers} workers 🚀"
                                else:
                                    success_msg += f" in {elapsed_total:.1f}s ({rate:.1f} products/sec)"
                                
                                st.success(success_msg)
                                
                                with st.expander("📊 Product Summary"):
                                    # Show performance metrics
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("Products", len(products))
                                    with col2:
                                        st.metric("Time", f"{elapsed_total:.1f}s")
                                    with col3:
                                        st.metric("Rate", f"{rate:.1f}/s")
                                    with col4:
                                        if use_comprehensive:
                                            st.metric("Mode", "🔍 Comprehensive")
                                        elif use_multithreading:
                                            st.metric("Workers", f"{max_workers} 🚀")
                                        else:
                                            st.metric("Mode", "🏪 Standard")
                                    
                                    st.subheader("🛍️ Extracted Products")
                                    for i, product in enumerate(products[:10]):  # Show first 10
                                        with st.container():
                                            st.write(f"**{i+1}. {product.get('product_name', 'Unknown')}**")
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.caption(f"💰 Prices: {product.get('prices', [])}")
                                            with col2:
                                                st.caption(f"📏 Sizes: {product.get('sizes', [])}")
                                            with col3:
                                                st.caption(f"📦 Status: {product.get('availability', 'unknown')}")
                                            
                                            # Show additional attributes if available
                                            attrs = product.get('attributes', {})
                                            extra_info = []
                                            if attrs.get('colors'):
                                                extra_info.append(f"🎨 {', '.join(attrs['colors'][:3])}")
                                            if attrs.get('materials'):
                                                extra_info.append(f"🧵 {', '.join(attrs['materials'][:2])}")
                                            if extra_info:
                                                st.caption(" | ".join(extra_info))
                                            
                                            st.caption(f"🔗 [View Product]({product['url']})")
                                        st.divider()
                                
                                st.rerun()
                            else:
                                progress_placeholder.empty()
                                st.error("No products could be extracted from this website")
                                
                        except Exception as e:
                            progress_placeholder.empty()
                            st.error(f"Product crawling failed: {str(e)}")
            
            else:  # General content mode
                if st.sidebar.button("🕷️ Crawl General Content", type="secondary"):
                    with st.spinner("Crawling website content..."):
                        progress_placeholder = st.empty()
                        
                        def progress_callback(message):
                            progress_placeholder.text(f"🕷️ {message}")
                        
                        try:
                            documents = crawler.crawl_website(website_url, progress_callback)
                            
                            if documents:
                                progress_placeholder.text("💾 Saving and indexing documents...")
                                # Note: Google Search RAG doesn't require local data storage
                                doc_count = len(documents)
                                
                                st.session_state.indexed_websites.append(domain)
                                progress_placeholder.empty()
                                st.success(f"✅ Successfully crawled and indexed {doc_count} documents from {domain}")
                                st.rerun()
                            else:
                                progress_placeholder.empty()
                                st.error("No content could be extracted from this website")
                                
                        except Exception as e:
                            progress_placeholder.empty()
                            st.error(f"Crawling failed: {str(e)}")
    
    # Indexed websites list
    if st.session_state.indexed_websites:
        st.sidebar.subheader("💬 Recent Domains")
        for site in st.session_state.indexed_websites:
            if st.sidebar.button(f"💬 Chat with {site}", key=f"chat_{site}"):
                st.session_state.current_website = site
                st.rerun()
    
    # Conversation management
    if st.session_state.current_website:
        st.sidebar.subheader("💭 Conversation")
        
        # Show conversation summary
        conv_summary = chat_rag.get_conversation_summary(st.session_state.current_website)
        if conv_summary['total_turns'] > 0:
            st.sidebar.info(f"🔄 {conv_summary['total_turns']} turns in conversation")
            
            if st.sidebar.button("🧹 Clear Conversation History"):
                st.session_state.chat_rag.clear_conversation(st.session_state.current_website)
                # Also clear Streamlit session messages
                if st.session_state.current_website in st.session_state.messages:
                    st.session_state.messages[st.session_state.current_website] = []
                st.success("Conversation history cleared!")
                st.rerun()
        else:
            st.sidebar.info("💬 Start a new conversation")
    
    # Main chat interface
    if st.session_state.current_website:
        st.header(f"💬 Chatting with: {st.session_state.current_website}")
        
        # Initialize messages for current website
        if st.session_state.current_website not in st.session_state.messages:
            st.session_state.messages[st.session_state.current_website] = []
        
        current_messages = st.session_state.messages[st.session_state.current_website]
        
        # Display chat messages
        for message in current_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input(f"Ask about {st.session_state.current_website}..."):
            # Add user message
            current_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display assistant response
            with st.chat_message("assistant"):
                with st.spinner("Analyzing context and searching..."):
                    # Use the Google Search function (auto-detects if API is configured)
                    search_function = create_google_search_function()
                    
                    # Use Universal Chat RAG for multi-turn support
                    conv_result = chat_rag.generate_conversational_response(
                        st.session_state.current_website, 
                        prompt,
                        search_function=search_function
                    )
                    
                    response = conv_result['response']
                    st.markdown(response)
                    
                    # Show conversation insights in an expander
                    with st.expander("🧠 AI Processing Analysis", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Query Processing:**")
                            st.write(f"🤖 **AI Provider:** {conv_result['provider_used'].title()}")
                            st.write(f"🎯 **Response Mode:** {conv_result.get('response_mode', 'normal').title()}")
                            if conv_result['rewritten_keyphrases'] != [prompt]:
                                st.write(f"🔄 **Original:** {prompt}")
                                st.write(f"🎯 **Key Phrases:** {', '.join(conv_result['rewritten_keyphrases'])}")
                                st.write(f"💭 **Reasoning:** {conv_result['rewrite_reasoning']}")
                            else:
                                st.write("✅ Used original query (no rewriting needed)")
                        
                        with col2:
                            st.write("**Sources Found:**")
                            if conv_result['sources']:
                                for i, source in enumerate(conv_result['sources'][:3], 1):
                                    title = source.get('title', 'Unknown')
                                    url = source.get('url', '#')
                                    score = source.get('score', 0)
                                    st.write(f"{i}. [{title}]({url}) (Score: {score:.3f})")
                            else:
                                st.write("No specific sources found")
                        
                        # Show thinking process if available
                        if conv_result.get('thinking_process'):
                            st.write("**🤔 Thinking Process:**")
                            st.text_area("AI's step-by-step reasoning:", conv_result['thinking_process'], height=150, disabled=True)
                        
                        # Show ReAct process if available
                        if conv_result.get('react_turns'):
                            st.write("**🔄 ReAct Process:**")
                            st.write(f"Success: {'✅' if conv_result.get('react_success') else '❌'} | Turns: {conv_result.get('total_react_turns', 0)}")
                            
                            # Show ReAct turns in a collapsible section
                            with st.expander("View ReAct Turns", expanded=False):
                                for turn in conv_result['react_turns']:
                                    st.write(f"**Turn {turn['turn']}:**")
                                    st.text_area(f"Model Output {turn['turn']}:", turn['model_output'], height=100, disabled=True, key=f"react_turn_{turn['turn']}")
                                    if 'observation' in turn:
                                        st.write(f"🔍 **Observation:** {turn['observation']}")
                                    if 'error' in turn:
                                        st.write(f"❌ **Error:** {turn['error']}")
                                    st.divider()
                        
                        if conv_result['conversation_context_used']:
                            st.write("**Conversation Context:**")
                            st.text_area("Previous context used:", conv_result['conversation_context_used'], height=100, disabled=True)
            
            current_messages.append({"role": "assistant", "content": response})
    
    else:
        st.info("👆 Enter a website URL in the sidebar to get started!")
        
        if st.session_state.indexed_websites:
            st.subheader("Or select from your indexed websites:")
            cols = st.columns(min(3, len(st.session_state.indexed_websites)))
            for i, site in enumerate(st.session_state.indexed_websites):
                with cols[i % 3]:
                    if st.button(f"💬 {site}", key=f"main_chat_{site}"):
                        st.session_state.current_website = site
                        st.rerun()

if __name__ == "__main__":
    main()