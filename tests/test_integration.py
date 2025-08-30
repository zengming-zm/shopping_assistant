import pytest
import asyncio
from unittest.mock import Mock, patch

from gateway.agent import AgentOrchestrator
from gateway.rag import RAGService
from shared.models import RAGQuery


@pytest.mark.asyncio
class TestIntegration:
    @pytest.fixture
    async def mock_rag_service(self):
        service = Mock(spec=RAGService)
        service.query = Mock()
        return service
    
    @pytest.fixture
    async def agent(self, mock_rag_service):
        with patch('gateway.agent.LLMRouter'), \
             patch('gateway.agent.ToolRegistry'), \
             patch('gateway.agent.PromptManager'):
            return AgentOrchestrator(mock_rag_service)
    
    async def test_simple_rag_query(self, agent, mock_rag_service):
        mock_rag_service.query.return_value = Mock(
            answer="Our return policy allows returns within 30 days.",
            sources=[
                Mock(
                    url="http://shop.com/returns",
                    title="Return Policy", 
                    snippet="Returns are accepted within 30 days of purchase.",
                    score=0.95
                )
            ]
        )
        
        with patch.object(agent, '_make_planning_decision') as mock_decision, \
             patch.object(agent, '_generate_followups') as mock_followups:
            
            mock_decision.return_value = {"action": "rag_only"}
            mock_followups.return_value = ["What items can't be returned?"]
            
            result = await agent.process_query(
                shop_id="test_shop",
                user_message="What's your return policy?",
                conversation_history=[]
            )
            
            assert "30 days" in result["answer"]
            assert len(result["sources"]) == 1
            assert result["sources"][0]["url"] == "http://shop.com/returns"
            assert result["action_taken"] == "rag_search"
            assert len(result["followups"]) == 1
    
    async def test_tool_usage_flow(self, agent, mock_rag_service):
        with patch.object(agent, '_make_planning_decision') as mock_decision, \
             patch.object(agent, '_handle_tool_usage') as mock_tool_usage, \
             patch.object(agent, '_synthesize_tool_response') as mock_synthesize, \
             patch.object(agent, '_generate_followups') as mock_followups:
            
            mock_decision.return_value = {
                "action": "tool_use", 
                "tools": ["convert_currency"]
            }
            mock_tool_usage.return_value = {
                "results": {
                    "convert_currency": {
                        "result": {
                            "converted_amount": 85.0,
                            "from_currency": "USD",
                            "to_currency": "EUR"
                        }
                    }
                },
                "tool_traces": [],
                "sources": []
            }
            mock_synthesize.return_value = "$100 USD equals €85.00 EUR"
            mock_followups.return_value = ["What about other currencies?"]
            
            result = await agent.process_query(
                shop_id="test_shop",
                user_message="Convert $100 to EUR",
                conversation_history=[]
            )
            
            assert "85.00" in result["answer"]
            assert result["action_taken"] == "tool_execution"
            assert len(result["followups"]) == 1
    
    async def test_hybrid_rag_and_tools(self, agent, mock_rag_service):
        mock_rag_service.query.return_value = Mock(
            answer="We ship worldwide. Standard shipping takes 5-7 business days.",
            sources=[
                Mock(
                    url="http://shop.com/shipping",
                    title="Shipping Info",
                    snippet="We offer worldwide shipping with various options.",
                    score=0.9
                )
            ]
        )
        
        with patch.object(agent, '_make_planning_decision') as mock_decision, \
             patch.object(agent, '_handle_tool_usage') as mock_tool_usage, \
             patch.object(agent, '_combine_rag_and_tools') as mock_combine, \
             patch.object(agent, '_generate_followups') as mock_followups:
            
            mock_decision.return_value = {
                "action": "hybrid",
                "tools": ["estimate_shipping"]
            }
            mock_tool_usage.return_value = {
                "results": {
                    "estimate_shipping": {
                        "result": {
                            "estimated_cost": 15.99,
                            "estimated_days": 7
                        }
                    }
                },
                "tool_traces": [],
                "sources": []
            }
            mock_combine.return_value = "We ship worldwide in 5-7 days. Estimated cost to your location: $15.99"
            mock_followups.return_value = ["Do you offer expedited shipping?"]
            
            result = await agent.process_query(
                shop_id="test_shop", 
                user_message="How much does shipping cost to California?",
                conversation_history=[]
            )
            
            assert "worldwide" in result["answer"]
            assert "$15.99" in result["answer"]
            assert result["action_taken"] == "hybrid_rag_tools"
            assert len(result["sources"]) == 1
    
    async def test_conversation_with_history(self, agent, mock_rag_service):
        conversation_history = [
            {"role": "user", "content": "Do you sell laptops?"},
            {"role": "assistant", "content": "Yes, we have a great selection of laptops."},
            {"role": "user", "content": "What brands do you carry?"}
        ]
        
        mock_rag_service.query.return_value = Mock(
            answer="We carry Apple, Dell, HP, Lenovo, and ASUS laptops.",
            sources=[
                Mock(
                    url="http://shop.com/laptops",
                    title="Laptop Collection",
                    snippet="Browse our selection of premium laptops from top brands.",
                    score=0.88
                )
            ]
        )
        
        with patch.object(agent, '_make_planning_decision') as mock_decision, \
             patch.object(agent, '_generate_followups') as mock_followups:
            
            mock_decision.return_value = {"action": "rag_only"}
            mock_followups.return_value = ["Which laptop would you recommend for gaming?"]
            
            result = await agent.process_query(
                shop_id="test_shop",
                user_message="What brands do you carry?", 
                conversation_history=conversation_history
            )
            
            assert any(brand in result["answer"] for brand in ["Apple", "Dell", "HP", "Lenovo", "ASUS"])
            assert result["action_taken"] == "rag_search"
            
            mock_decision.assert_called_once()
            args = mock_decision.call_args[0]
            assert args[1] == "What brands do you carry?"  # user message
            assert len(args[2]) <= 5  # conversation history should be limited