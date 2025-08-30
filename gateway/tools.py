import logging
import json
import re
from typing import Dict, Any, List, Optional
import httpx
from datetime import datetime

from shared.config import config, env_config
from .rag import RAGService


logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service
        self.tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "convert_currency": {
                "schema": {
                    "name": "convert_currency",
                    "description": "Convert between currencies using live exchange rates",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Amount to convert"},
                            "from_currency": {"type": "string", "description": "Source currency code (e.g., USD)"},
                            "to_currency": {"type": "string", "description": "Target currency code (e.g., EUR)"}
                        },
                        "required": ["amount", "from_currency", "to_currency"]
                    }
                },
                "handler": self._convert_currency
            },
            "search_products": {
                "schema": {
                    "name": "search_products",
                    "description": "Search for products in the shop or demo product database",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for products"},
                            "shop_id": {"type": "string", "description": "Shop identifier"},
                            "limit": {"type": "integer", "default": 10, "description": "Maximum number of results"},
                            "filters": {"type": "object", "description": "Additional filters (category, price range, etc.)"}
                        },
                        "required": ["query", "shop_id"]
                    }
                },
                "handler": self._search_products
            },
            "get_product_detail": {
                "schema": {
                    "name": "get_product_detail",
                    "description": "Get detailed information about a specific product",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Product ID or URL"},
                            "shop_id": {"type": "string", "description": "Shop identifier"}
                        },
                        "required": ["product_id", "shop_id"]
                    }
                },
                "handler": self._get_product_detail
            },
            "get_reviews": {
                "schema": {
                    "name": "get_reviews",
                    "description": "Get customer reviews for a product",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Product ID or URL"},
                            "shop_id": {"type": "string", "description": "Shop identifier"},
                            "limit": {"type": "integer", "default": 5, "description": "Maximum number of reviews"}
                        },
                        "required": ["product_id", "shop_id"]
                    }
                },
                "handler": self._get_reviews
            },
            "geolocate_ip": {
                "schema": {
                    "name": "geolocate_ip",
                    "description": "Get location information from IP address for shipping estimates",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "ip_address": {"type": "string", "description": "IP address (optional, uses request IP if not provided)"}
                        },
                        "required": []
                    }
                },
                "handler": self._geolocate_ip
            },
            "estimate_shipping": {
                "schema": {
                    "name": "estimate_shipping",
                    "description": "Estimate shipping costs and delivery time",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "origin": {"type": "string", "description": "Origin address or postal code"},
                            "destination": {"type": "string", "description": "Destination address or postal code"},
                            "weight": {"type": "number", "description": "Package weight in pounds"},
                            "dimensions": {"type": "object", "description": "Package dimensions (length, width, height)"}
                        },
                        "required": ["origin", "destination", "weight"]
                    }
                },
                "handler": self._estimate_shipping
            }
        }
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [tool["schema"] for tool in self.tools.values()]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            handler = self.tools[tool_name]["handler"]
            result = await handler(**arguments)
            return {"result": result}
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return {"error": str(e)}
    
    async def _convert_currency(self, amount: float, from_currency: str, to_currency: str) -> Dict[str, Any]:
        try:
            url = f"https://api.exchangerate.host/convert?from={from_currency}&to={to_currency}&amount={amount}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("success"):
                    return {
                        "amount": amount,
                        "from_currency": from_currency,
                        "to_currency": to_currency,
                        "converted_amount": data["result"],
                        "exchange_rate": data["info"]["rate"],
                        "date": data["date"]
                    }
                else:
                    return {"error": "Currency conversion failed"}
                    
        except Exception as e:
            logger.error(f"Currency conversion failed: {e}")
            return {"error": f"Currency conversion failed: {str(e)}"}
    
    async def _search_products(self, query: str, shop_id: str, limit: int = 10, filters: Dict = None) -> Dict[str, Any]:
        try:
            if env_config.DEMO_MODE:
                return await self._search_demo_products(query, limit, filters)
            else:
                from .rag import RAGQuery
                rag_query = RAGQuery(shop_id=shop_id, question=f"products matching: {query}", top_k=limit)
                rag_response = await self.rag_service.query(rag_query)
                
                products = []
                for source in rag_response.sources:
                    if "product" in source.title.lower() or any(term in source.snippet.lower() for term in ["price", "$", "buy"]):
                        product = {
                            "title": source.title,
                            "description": source.snippet[:200],
                            "url": source.url,
                            "score": source.score
                        }
                        
                        price_match = re.search(r'\$?([\d,]+\.?\d*)', source.snippet)
                        if price_match:
                            product["price"] = float(price_match.group(1).replace(',', ''))
                        
                        products.append(product)
                
                return {"products": products[:limit]}
                
        except Exception as e:
            logger.error(f"Product search failed: {e}")
            return {"error": f"Product search failed: {str(e)}"}
    
    async def _search_demo_products(self, query: str, limit: int, filters: Dict = None) -> Dict[str, Any]:
        try:
            demo_api = config.demo_apis.get("products", "dummyjson")
            
            if demo_api == "dummyjson":
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"https://dummyjson.com/products/search?q={query}&limit={limit}")
                    response.raise_for_status()
                    
                    data = response.json()
                    products = []
                    
                    for item in data.get("products", []):
                        product = {
                            "id": item["id"],
                            "title": item["title"],
                            "description": item["description"],
                            "price": item["price"],
                            "category": item["category"],
                            "brand": item.get("brand"),
                            "rating": item.get("rating"),
                            "thumbnail": item.get("thumbnail"),
                            "images": item.get("images", [])
                        }
                        products.append(product)
                    
                    return {"products": products}
            
            elif demo_api == "fakestore":
                async with httpx.AsyncClient() as client:
                    response = await client.get("https://fakestoreapi.com/products")
                    response.raise_for_status()
                    
                    products = response.json()
                    
                    filtered = [p for p in products if query.lower() in p["title"].lower() or query.lower() in p["description"].lower()]
                    
                    return {"products": filtered[:limit]}
            
            else:
                return {"error": "Unknown demo API configuration"}
                
        except Exception as e:
            logger.error(f"Demo product search failed: {e}")
            return {"error": f"Demo product search failed: {str(e)}"}
    
    async def _get_product_detail(self, product_id: str, shop_id: str) -> Dict[str, Any]:
        try:
            if env_config.DEMO_MODE:
                if product_id.isdigit():
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"https://dummyjson.com/products/{product_id}")
                        response.raise_for_status()
                        return {"product": response.json()}
                else:
                    return {"error": "Invalid product ID for demo mode"}
            else:
                from .rag import RAGQuery
                rag_query = RAGQuery(shop_id=shop_id, question=f"detailed information about product: {product_id}")
                rag_response = await self.rag_service.query(rag_query)
                
                if rag_response.sources:
                    return {
                        "product": {
                            "title": rag_response.sources[0].title,
                            "description": rag_response.answer,
                            "sources": [{"url": s.url, "title": s.title} for s in rag_response.sources]
                        }
                    }
                else:
                    return {"error": "Product not found"}
                    
        except Exception as e:
            logger.error(f"Product detail fetch failed: {e}")
            return {"error": f"Product detail fetch failed: {str(e)}"}
    
    async def _get_reviews(self, product_id: str, shop_id: str, limit: int = 5) -> Dict[str, Any]:
        try:
            if env_config.DEMO_MODE:
                return {
                    "reviews": [
                        {
                            "id": 1,
                            "rating": 4.5,
                            "comment": "Great product! Really satisfied with the quality.",
                            "reviewer": "Customer A",
                            "date": "2024-01-15"
                        },
                        {
                            "id": 2,
                            "rating": 5.0,
                            "comment": "Excellent value for money. Would recommend!",
                            "reviewer": "Customer B",
                            "date": "2024-01-10"
                        }
                    ][:limit]
                }
            else:
                from .rag import RAGQuery
                rag_query = RAGQuery(shop_id=shop_id, question=f"customer reviews for: {product_id}")
                rag_response = await self.rag_service.query(rag_query)
                
                reviews = []
                for source in rag_response.sources:
                    if "review" in source.title.lower() or "rating" in source.snippet.lower():
                        reviews.append({
                            "text": source.snippet,
                            "source_url": source.url,
                            "title": source.title
                        })
                
                return {"reviews": reviews[:limit]}
                
        except Exception as e:
            logger.error(f"Reviews fetch failed: {e}")
            return {"error": f"Reviews fetch failed: {str(e)}"}
    
    async def _geolocate_ip(self, ip_address: str = None) -> Dict[str, Any]:
        try:
            geo_api = config.demo_apis.get("geo", "ipapi")
            
            if geo_api == "ipapi":
                url = f"https://ipapi.co/{ip_address}/json/" if ip_address else "https://ipapi.co/json/"
            elif geo_api == "ip_api":
                url = f"http://ip-api.com/json/{ip_address}" if ip_address else "http://ip-api.com/json"
            else:
                return {"error": "Unknown geo API configuration"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                
                if geo_api == "ipapi":
                    return {
                        "ip": data.get("ip"),
                        "country": data.get("country_name"),
                        "country_code": data.get("country_code"),
                        "region": data.get("region"),
                        "city": data.get("city"),
                        "postal": data.get("postal"),
                        "latitude": data.get("latitude"),
                        "longitude": data.get("longitude"),
                        "timezone": data.get("timezone")
                    }
                else:  # ip_api
                    return {
                        "ip": data.get("query"),
                        "country": data.get("country"),
                        "country_code": data.get("countryCode"),
                        "region": data.get("regionName"),
                        "city": data.get("city"),
                        "postal": data.get("zip"),
                        "latitude": data.get("lat"),
                        "longitude": data.get("lon"),
                        "timezone": data.get("timezone")
                    }
                    
        except Exception as e:
            logger.error(f"Geolocation failed: {e}")
            return {"error": f"Geolocation failed: {str(e)}"}
    
    async def _estimate_shipping(self, origin: str, destination: str, weight: float, dimensions: Dict = None) -> Dict[str, Any]:
        try:
            if env_config.DEMO_MODE or not env_config.EASYPOST_TEST_API_KEY:
                estimated_days = 3 if "express" in destination.lower() else 7
                base_cost = weight * 2.5
                
                return {
                    "estimated_cost": round(base_cost, 2),
                    "estimated_days": estimated_days,
                    "service_type": "Standard Ground",
                    "origin": origin,
                    "destination": destination,
                    "weight": weight,
                    "note": "This is a demo estimate"
                }
            else:
                return {
                    "error": "EasyPost integration not fully implemented in this demo. Showing demo data.",
                    "estimated_cost": 15.50,
                    "estimated_days": 5,
                    "service_type": "Demo Service"
                }
                
        except Exception as e:
            logger.error(f"Shipping estimation failed: {e}")
            return {"error": f"Shipping estimation failed: {str(e)}"}