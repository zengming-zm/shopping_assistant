"""
Quick test of comprehensive crawler to verify it finds accessories
"""

import asyncio
from comprehensive_crawler import ComprehensiveURLDiscovery

async def test_discovery():
    """Test URL discovery for Luca Faloni"""
    
    print("🧪 Testing Comprehensive URL Discovery")
    print("=" * 50)
    
    # Test the URL discovery system
    discovery = ComprehensiveURLDiscovery("https://lucafaloni.com/en/us")
    
    # Test category detection
    test_urls = [
        "https://lucafaloni.com/en/us/shop/accessories",
        "https://lucafaloni.com/en/us/collections/accessories",
        "https://lucafaloni.com/en/us/shop/shirts",
        "https://lucafaloni.com/en/us/shop/knitwear",
        "https://lucafaloni.com/en/us/shop/some-product-name",
        "https://lucafaloni.com/en/us/pages/about",
        "https://lucafaloni.com/en/us/cart",
    ]
    
    print("🔍 Testing URL categorization:")
    for url in test_urls:
        is_category = discovery.looks_like_category_url(url)
        is_product = discovery.looks_like_product_url(url)
        
        if is_category:
            category_type = "📂 CATEGORY"
        elif is_product:
            category_type = "🛍️ PRODUCT"
        else:
            category_type = "📄 OTHER"
        
        print(f"   {category_type}: {url}")
    
    print("\n✅ URL categorization test complete!")

if __name__ == "__main__":
    asyncio.run(test_discovery())