from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import asyncio
import sys
import os
from typing import Dict

# Add the parent directory to the path so we can import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .services import CrawlerService
from shared.models import CrawlRequest, CrawlStatus


crawl_jobs: Dict[str, asyncio.Task] = {}
crawler_service = CrawlerService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await crawler_service.initialize()
    yield
    await crawler_service.cleanup()


app = FastAPI(title="ShopTalk Crawler", lifespan=lifespan)


@app.post("/crawl/start")
async def start_crawl(request: CrawlRequest) -> Dict[str, str]:
    if request.shop_id in crawl_jobs and not crawl_jobs[request.shop_id].done():
        raise HTTPException(status_code=400, detail="Crawl already in progress for this shop")
    
    task = asyncio.create_task(crawler_service.crawl_shop(request))
    crawl_jobs[request.shop_id] = task
    
    return {"status": "started", "shop_id": request.shop_id}


@app.get("/crawl/status")
async def get_crawl_status(shop_id: str) -> CrawlStatus:
    return await crawler_service.get_crawl_status(shop_id)


@app.post("/crawl/reindex")
async def reindex_urls(shop_id: str, urls: list[str] = None) -> Dict[str, str]:
    await crawler_service.reindex_urls(shop_id, urls)
    return {"status": "reindex_started", "shop_id": shop_id}


@app.get("/health")
async def health():
    return {"status": "healthy"}