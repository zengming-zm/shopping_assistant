import logging
from typing import List, Optional
import json
import httpx
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from shared.config import config, env_config
from shared.models import RAGQuery, RAGResponse, Source


logger = logging.getLogger(__name__)


class RerankerService:
    def __init__(self):
        self.reranker_type = config.reranker
        self.local_reranker = None
        
        if self.reranker_type == "local_bge":
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import torch
                
                model_name = "BAAI/bge-reranker-v2-m3"
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model.to(self.device)
            except ImportError:
                logger.warning("BGE reranker dependencies not available, falling back to no reranking")
                self.reranker_type = "none"
    
    async def rerank(self, query: str, sources: List[Source], top_n: int) -> List[Source]:
        if self.reranker_type == "none" or not sources:
            return sources[:top_n]
        
        try:
            if self.reranker_type == "local_bge":
                return await self._rerank_with_bge(query, sources, top_n)
            elif self.reranker_type == "cohere":
                return await self._rerank_with_cohere(query, sources, top_n)
            elif self.reranker_type == "jina_cloud":
                return await self._rerank_with_jina(query, sources, top_n)
            else:
                return sources[:top_n]
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return sources[:top_n]
    
    async def _rerank_with_bge(self, query: str, sources: List[Source], top_n: int) -> List[Source]:
        import torch
        
        pairs = [(query, source.snippet) for source in sources]
        
        with torch.no_grad():
            inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float()
            scores = torch.sigmoid(scores).cpu().numpy()
        
        scored_sources = list(zip(sources, scores))
        scored_sources.sort(key=lambda x: x[1], reverse=True)
        
        reranked = []
        for source, score in scored_sources[:top_n]:
            source.score = float(score)
            reranked.append(source)
        
        return reranked
    
    async def _rerank_with_cohere(self, query: str, sources: List[Source], top_n: int) -> List[Source]:
        if not env_config.COHERE_API_KEY:
            logger.warning("Cohere API key not available")
            return sources[:top_n]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.cohere.ai/v1/rerank",
                headers={"Authorization": f"Bearer {env_config.COHERE_API_KEY}"},
                json={
                    "model": "rerank-english-v3.0",
                    "query": query,
                    "documents": [source.snippet for source in sources],
                    "top_n": top_n
                }
            )
            response.raise_for_status()
            
            results = response.json()
            reranked = []
            
            for result in results["results"]:
                idx = result["index"]
                source = sources[idx]
                source.score = result["relevance_score"]
                reranked.append(source)
            
            return reranked
    
    async def _rerank_with_jina(self, query: str, sources: List[Source], top_n: int) -> List[Source]:
        if not env_config.JINA_API_KEY:
            logger.warning("Jina API key not available")
            return sources[:top_n]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.jina.ai/v1/rerank",
                headers={"Authorization": f"Bearer {env_config.JINA_API_KEY}"},
                json={
                    "model": "jina-reranker-v2-base-multilingual",
                    "query": query,
                    "documents": [{"text": source.snippet} for source in sources],
                    "top_n": top_n
                }
            )
            response.raise_for_status()
            
            results = response.json()
            reranked = []
            
            for result in results["results"]:
                idx = result["index"]
                source = sources[idx]
                source.score = result["relevance_score"]
                reranked.append(source)
            
            return reranked


class RAGService:
    def __init__(self):
        self.embeddings_model = None
        self.qdrant_client = None
        self.reranker = RerankerService()
    
    async def initialize(self):
        self.embeddings_model = SentenceTransformer(config.embeddings_model)
        self.qdrant_client = QdrantClient(url=env_config.QDRANT_URL)
    
    async def query(self, query: RAGQuery) -> RAGResponse:
        try:
            query_vector = self.embeddings_model.encode(query.question).tolist()
            
            search_results = self.qdrant_client.search(
                collection_name="documents",
                query_vector=query_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="shop_id",
                            match=MatchValue(value=query.shop_id)
                        )
                    ]
                ),
                limit=query.top_k
            )
            
            sources = []
            for result in search_results:
                source = Source(
                    url=result.payload["url"],
                    title=result.payload["title"],
                    snippet=result.payload["text"][:300] + "..." if len(result.payload["text"]) > 300 else result.payload["text"],
                    score=result.score
                )
                sources.append(source)
            
            if not sources:
                return RAGResponse(
                    answer="I couldn't find any relevant information in this shop's content to answer your question.",
                    sources=[]
                )
            
            reranked_sources = await self.reranker.rerank(query.question, sources, query.rerank_top_n)
            
            context = self._prepare_context(reranked_sources)
            
            answer = await self._generate_answer(query.question, context, reranked_sources)
            
            return RAGResponse(
                answer=answer,
                sources=reranked_sources
            )
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return RAGResponse(
                answer="I encountered an error while searching for information. Please try again.",
                sources=[]
            )
    
    def _prepare_context(self, sources: List[Source]) -> str:
        context_parts = []
        for i, source in enumerate(sources, 1):
            context_parts.append(f"Source {i} ({source.title}):\n{source.snippet}\n")
        return "\n".join(context_parts)
    
    async def _generate_answer(self, question: str, context: str, sources: List[Source]) -> str:
        from .llm_router import LLMRouter
        
        llm_router = LLMRouter()
        
        prompt = f"""You are a shopping assistant. Answer the customer's question using ONLY the provided shop content.

Question: {question}

Shop Content:
{context}

Guidelines:
- Answer directly and helpfully
- If the information isn't in the shop content, say so
- Include relevant details like prices, policies, or product features when available
- Keep the answer concise but informative
- If you mention specific information, reference which source it came from

Answer:"""

        try:
            model = config.llm_router.get('models', {}).get('rag_answer', 'claude-3-5-sonnet-20241022')
            response = await llm_router.generate(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"Based on the shop's content, I found {len(sources)} relevant sources, but I encountered an issue generating a comprehensive answer. Please check the sources provided."
    
    async def force_retrieve_policy(self, shop_id: str, policy_type: str = "shipping") -> List[Source]:
        try:
            policy_terms = {
                "shipping": ["shipping", "delivery", "fulfillment"],
                "return": ["return", "refund", "exchange"],
                "privacy": ["privacy", "data", "personal information"],
                "terms": ["terms", "conditions", "agreement"]
            }
            
            terms = policy_terms.get(policy_type, ["policy"])
            
            sources = []
            for term in terms:
                search_results = self.qdrant_client.search(
                    collection_name="documents",
                    query_vector=self.embeddings_model.encode(f"{term} policy").tolist(),
                    query_filter=Filter(
                        must=[
                            FieldCondition(key="shop_id", match=MatchValue(value=shop_id)),
                            FieldCondition(key="section", match=MatchValue(value="policy"))
                        ]
                    ),
                    limit=3
                )
                
                for result in search_results:
                    source = Source(
                        url=result.payload["url"],
                        title=result.payload["title"],
                        snippet=result.payload["text"][:500],
                        score=result.score
                    )
                    sources.append(source)
            
            return sources[:5]
            
        except Exception as e:
            logger.error(f"Policy retrieval failed: {e}")
            return []