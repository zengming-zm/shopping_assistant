#!/usr/bin/env python3
"""
Test scraping a single Nike product to debug the crawler
"""

from firecrawl import Firecrawl
import json

def test_single_product():
    api_key = "fc-f31bab16fdf84e42b315b49f61f15305"
    app = Firecrawl(api_key=api_key)
    
    test_url = "https://www.nike.com/t/air-max-270-mens-shoes-KkLcGR"
    print(f"Testing scrape of: {test_url}")
    
    try:
        result = app.scrape(
            url=test_url,
            formats=['markdown', 'html'],
        )
        
        print("Scrape result keys:", list(result.__dict__.keys()) if hasattr(result, '__dict__') else type(result))
        
        if hasattr(result, 'markdown'):
            print(f"Markdown length: {len(result.markdown) if result.markdown else 0}")
            print("First 500 chars of markdown:")
            print(result.markdown[:500] if result.markdown else "No markdown content")
        
        if hasattr(result, 'metadata'):
            print(f"Metadata: {result.metadata}")
        
        return result
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    test_single_product()