from fastapi import FastAPI, HTTPException
import asyncio
import sys
import os
from typing import Dict

# Add the parent directory to the path so we can import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from firecrawl import Firecrawl

print("begin crawling")

firecrawl = Firecrawl(api_key="fc-f31bab16fdf84e42b315b49f61f15305")

res = firecrawl.map(url="https://www.nike.com/", limit=5, sitemap="include")
print(res)
