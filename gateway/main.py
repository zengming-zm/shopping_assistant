from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import sys
import os

# Add the parent directory to the path so we can import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import RAGQuery, RAGResponse, ShopInfo
from .rag import RAGService
from .agent import AgentOrchestrator


rag_service = RAGService()
agent_orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_orchestrator
    await rag_service.initialize()
    agent_orchestrator = AgentOrchestrator(rag_service)
    yield


app = FastAPI(title="ShopTalk Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    shop_id: str
    message: str
    conversation_history: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    tool_traces: List[Dict[str, Any]]
    followups: List[str]
    action_taken: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await agent_orchestrator.process_query(
            shop_id=request.shop_id,
            user_message=request.message,
            conversation_history=request.conversation_history
        )
        
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            tool_traces=[trace.dict() if hasattr(trace, 'dict') else trace for trace in result["tool_traces"]],
            followups=result["followups"],
            action_taken=result["action_taken"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/query", response_model=RAGResponse)
async def rag_query(query: RAGQuery) -> RAGResponse:
    try:
        return await rag_service.query(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/shops/{shop_id}/info")
async def get_shop_info(shop_id: str) -> ShopInfo:
    try:
        from qdrant_client import QdrantClient
        from shared.config import env_config
        
        client = QdrantClient(url=env_config.QDRANT_URL)
        
        try:
            collection_info = client.get_collection("documents")
            
            search_results = client.scroll(
                collection_name="documents",
                scroll_filter={
                    "must": [
                        {
                            "key": "shop_id",
                            "match": {"value": shop_id}
                        }
                    ]
                },
                limit=1
            )
            
            if search_results[0]:
                first_doc = search_results[0][0].payload
                shop_name = first_doc.get("title", "Unknown Shop")
                shop_url = first_doc.get("url", "")
                
                count_result = client.count(
                    collection_name="documents",
                    count_filter={
                        "must": [
                            {
                                "key": "shop_id",
                                "match": {"value": shop_id}
                            }
                        ]
                    }
                )
                
                return ShopInfo(
                    shop_id=shop_id,
                    name=shop_name,
                    url=shop_url,
                    status="indexed",
                    document_count=count_result.count,
                    chunk_count=count_result.count
                )
            else:
                return ShopInfo(
                    shop_id=shop_id,
                    name="Unknown Shop",
                    url="",
                    status="not_indexed",
                    document_count=0,
                    chunk_count=0
                )
                
        except Exception:
            return ShopInfo(
                shop_id=shop_id,
                name="Unknown Shop",
                url="",
                status="error",
                document_count=0,
                chunk_count=0
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {
        "name": "ShopTalk Gateway",
        "version": "1.0.0",
        "endpoints": {
            "chat": "POST /chat",
            "rag_query": "POST /rag/query",
            "shop_info": "GET /shops/{shop_id}/info",
            "health": "GET /health"
        }
    }