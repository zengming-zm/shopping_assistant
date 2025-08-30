import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from qdrant_client import QdrantClient

from gateway.rag import RAGService, RerankerService
from shared.models import RAGQuery, Source


class TestRerankerService:
    @pytest.fixture
    def reranker_service(self):
        with patch('gateway.rag.config') as mock_config:
            mock_config.reranker = "local_bge"
            return RerankerService()
    
    def test_init_with_local_bge(self):
        with patch('gateway.rag.config') as mock_config, \
             patch('gateway.rag.AutoTokenizer'), \
             patch('gateway.rag.AutoModelForSequenceClassification'):
            mock_config.reranker = "local_bge"
            service = RerankerService()
            assert service.reranker_type == "local_bge"
    
    @pytest.mark.asyncio
    async def test_rerank_no_sources(self, reranker_service):
        result = await reranker_service.rerank("test query", [], 5)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_rerank_returns_top_n(self, reranker_service):
        sources = [
            Source(url="http://test.com/1", title="Title 1", snippet="Content 1", score=0.5),
            Source(url="http://test.com/2", title="Title 2", snippet="Content 2", score=0.7),
            Source(url="http://test.com/3", title="Title 3", snippet="Content 3", score=0.3)
        ]
        
        result = await reranker_service.rerank("test query", sources, 2)
        assert len(result) <= 2


class TestRAGService:
    @pytest.fixture
    def rag_service(self):
        with patch('gateway.rag.SentenceTransformer') as mock_st, \
             patch('gateway.rag.QdrantClient') as mock_qdrant:
            service = RAGService()
            service.embeddings_model = Mock()
            service.embeddings_model.encode.return_value = [0.1] * 384
            service.qdrant_client = Mock()
            service.reranker = Mock()
            service.reranker.rerank = AsyncMock(return_value=[])
            return service
    
    @pytest.mark.asyncio
    async def test_query_no_results(self, rag_service):
        rag_service.qdrant_client.search.return_value = []
        
        query = RAGQuery(shop_id="test", question="What is this?")
        result = await rag_service.query(query)
        
        assert "couldn't find any relevant information" in result.answer.lower()
        assert result.sources == []
    
    @pytest.mark.asyncio
    async def test_query_with_results(self, rag_service):
        mock_result = Mock()
        mock_result.score = 0.85
        mock_result.payload = {
            "url": "http://test.com/page1",
            "title": "Test Page",
            "text": "This is test content about the product.",
            "shop_id": "test"
        }
        
        rag_service.qdrant_client.search.return_value = [mock_result]
        rag_service.reranker.rerank.return_value = [
            Source(
                url="http://test.com/page1",
                title="Test Page",
                snippet="This is test content about the product.",
                score=0.85
            )
        ]
        
        with patch.object(rag_service, '_generate_answer', return_value="Test answer"):
            query = RAGQuery(shop_id="test", question="What is this?")
            result = await rag_service.query(query)
            
            assert result.answer == "Test answer"
            assert len(result.sources) == 1
            assert result.sources[0].url == "http://test.com/page1"
    
    def test_prepare_context(self, rag_service):
        sources = [
            Source(url="http://test.com/1", title="Page 1", snippet="Content 1", score=0.9),
            Source(url="http://test.com/2", title="Page 2", snippet="Content 2", score=0.8)
        ]
        
        context = rag_service._prepare_context(sources)
        
        assert "Source 1 (Page 1)" in context
        assert "Content 1" in context
        assert "Source 2 (Page 2)" in context
        assert "Content 2" in context
    
    @pytest.mark.asyncio
    async def test_force_retrieve_policy(self, rag_service):
        mock_result = Mock()
        mock_result.score = 0.9
        mock_result.payload = {
            "url": "http://test.com/shipping-policy",
            "title": "Shipping Policy",
            "text": "We ship worldwide with free shipping over $50.",
            "section": "policy"
        }
        
        rag_service.qdrant_client.search.return_value = [mock_result]
        
        sources = await rag_service.force_retrieve_policy("test", "shipping")
        
        assert len(sources) == 1
        assert sources[0].url == "http://test.com/shipping-policy"
        assert sources[0].title == "Shipping Policy"