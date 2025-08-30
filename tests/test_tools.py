import pytest
import httpx
from unittest.mock import Mock, AsyncMock, patch

from gateway.tools import ToolRegistry
from gateway.rag import RAGService


class TestToolRegistry:
    @pytest.fixture
    def mock_rag_service(self):
        return Mock(spec=RAGService)
    
    @pytest.fixture
    def tool_registry(self, mock_rag_service):
        return ToolRegistry(mock_rag_service)
    
    def test_get_tool_schemas(self, tool_registry):
        schemas = tool_registry.get_tool_schemas()
        
        tool_names = [schema["name"] for schema in schemas]
        expected_tools = [
            "convert_currency",
            "search_products", 
            "get_product_detail",
            "get_reviews",
            "geolocate_ip",
            "estimate_shipping"
        ]
        
        for tool in expected_tools:
            assert tool in tool_names
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, tool_registry):
        result = await tool_registry.execute_tool("unknown_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]
    
    @pytest.mark.asyncio
    async def test_convert_currency_success(self, tool_registry):
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "result": 85.23,
            "info": {"rate": 0.8523},
            "date": "2024-01-15"
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await tool_registry._convert_currency(100, "USD", "EUR")
            
            assert result["amount"] == 100
            assert result["from_currency"] == "USD"
            assert result["to_currency"] == "EUR"
            assert result["converted_amount"] == 85.23
            assert result["exchange_rate"] == 0.8523
    
    @pytest.mark.asyncio
    async def test_convert_currency_failure(self, tool_registry):
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )
            
            result = await tool_registry._convert_currency(100, "USD", "EUR")
            assert "error" in result
    
    @pytest.mark.asyncio 
    async def test_search_demo_products_dummyjson(self, tool_registry):
        mock_response = Mock()
        mock_response.json.return_value = {
            "products": [
                {
                    "id": 1,
                    "title": "iPhone 15",
                    "description": "Latest iPhone model",
                    "price": 999,
                    "category": "smartphones",
                    "brand": "Apple",
                    "rating": 4.9,
                    "thumbnail": "http://example.com/iphone.jpg",
                    "images": ["http://example.com/iphone1.jpg"]
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('gateway.tools.config') as mock_config, \
             patch('gateway.tools.env_config') as mock_env, \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_config.demo_apis.get.return_value = "dummyjson"
            mock_env.DEMO_MODE = True
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await tool_registry._search_demo_products("iPhone", 10, {})
            
            assert "products" in result
            assert len(result["products"]) == 1
            assert result["products"][0]["title"] == "iPhone 15"
            assert result["products"][0]["price"] == 999
    
    @pytest.mark.asyncio
    async def test_geolocate_ip_ipapi(self, tool_registry):
        mock_response = Mock()
        mock_response.json.return_value = {
            "ip": "8.8.8.8",
            "country_name": "United States",
            "country_code": "US", 
            "region": "California",
            "city": "Mountain View",
            "postal": "94043",
            "latitude": 37.4056,
            "longitude": -122.0775,
            "timezone": "America/Los_Angeles"
        }
        mock_response.raise_for_status = Mock()
        
        with patch('gateway.tools.config') as mock_config, \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_config.demo_apis.get.return_value = "ipapi"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await tool_registry._geolocate_ip("8.8.8.8")
            
            assert result["ip"] == "8.8.8.8"
            assert result["country"] == "United States"
            assert result["city"] == "Mountain View"
            assert result["latitude"] == 37.4056
    
    @pytest.mark.asyncio
    async def test_estimate_shipping_demo(self, tool_registry):
        with patch('gateway.tools.env_config') as mock_env:
            mock_env.DEMO_MODE = True
            mock_env.EASYPOST_TEST_API_KEY = None
            
            result = await tool_registry._estimate_shipping(
                "New York, NY", 
                "Los Angeles, CA", 
                2.5
            )
            
            assert "estimated_cost" in result
            assert "estimated_days" in result
            assert result["weight"] == 2.5
            assert result["origin"] == "New York, NY"
            assert result["destination"] == "Los Angeles, CA"
            assert "demo" in result.get("note", "").lower()
    
    @pytest.mark.asyncio
    async def test_get_reviews_demo_mode(self, tool_registry):
        with patch('gateway.tools.env_config') as mock_env:
            mock_env.DEMO_MODE = True
            
            result = await tool_registry._get_reviews("product123", "shop1", 3)
            
            assert "reviews" in result
            assert len(result["reviews"]) <= 3
            assert all("rating" in review for review in result["reviews"])
            assert all("comment" in review for review in result["reviews"])