import logging
from typing import List, Dict, Any, Optional
import httpx
from litellm import acompletion

from shared.config import config, env_config


logger = logging.getLogger(__name__)


class LLMRouter:
    def __init__(self):
        self.provider = config.llm_router.get('provider', 'litellm')
        self.models = config.llm_router.get('models', {})
        self.budgets = config.llm_router.get('budgets', {})
        
        if self.provider == "litellm":
            self._setup_litellm()
        elif self.provider == "openrouter":
            self._setup_openrouter()
    
    def _setup_litellm(self):
        import os
        
        if env_config.OPENAI_API_KEY:
            os.environ['OPENAI_API_KEY'] = env_config.OPENAI_API_KEY
        if env_config.ANTHROPIC_API_KEY:
            os.environ['ANTHROPIC_API_KEY'] = env_config.ANTHROPIC_API_KEY
        if env_config.GOOGLE_API_KEY:
            os.environ['GOOGLE_API_KEY'] = env_config.GOOGLE_API_KEY
    
    def _setup_openrouter(self):
        self.openrouter_base_url = "https://openrouter.ai/api/v1"
        self.openrouter_headers = {
            "Authorization": f"Bearer {env_config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def generate(
        self, 
        model: str, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        try:
            if self.provider == "litellm":
                return await self._generate_with_litellm(model, messages, tools, **kwargs)
            elif self.provider == "openrouter":
                return await self._generate_with_openrouter(model, messages, tools, **kwargs)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            logger.error(f"LLM generation failed with model {model}: {e}")
            raise
    
    async def _generate_with_litellm(
        self, 
        model: str, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        try:
            completion_kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", self.budgets.get("per_request_tokens", 4000)),
                "temperature": kwargs.get("temperature", 0.1)
            }
            
            if tools:
                completion_kwargs["tools"] = tools
                completion_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")
            
            response = await acompletion(**completion_kwargs)
            
            if tools and response.choices[0].message.tool_calls:
                return {
                    "content": response.choices[0].message.content,
                    "tool_calls": [
                        {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                            "id": call.id
                        } for call in response.choices[0].message.tool_calls
                    ]
                }
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LiteLLM generation failed: {e}")
            raise
    
    async def _generate_with_openrouter(
        self, 
        model: str, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", self.budgets.get("per_request_tokens", 4000)),
                "temperature": kwargs.get("temperature", 0.1)
            }
            
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = kwargs.get("tool_choice", "auto")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.openrouter_base_url}/chat/completions",
                    headers=self.openrouter_headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                if tools and result["choices"][0]["message"].get("tool_calls"):
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "tool_calls": [
                            {
                                "name": call["function"]["name"],
                                "arguments": call["function"]["arguments"],
                                "id": call["id"]
                            } for call in result["choices"][0]["message"]["tool_calls"]
                        ]
                    }
                
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
            raise
    
    def get_model_for_task(self, task: str) -> str:
        task_models = {
            "planner": self.models.get("planner", "gemini-2.0-flash-exp"),
            "rag_answer": self.models.get("rag_answer", "claude-3-5-sonnet-20241022"),
            "followups": self.models.get("followups", "gemini-1.5-flash"),
            "default": self.models.get("rag_answer", "claude-3-5-sonnet-20241022")
        }
        return task_models.get(task, task_models["default"])
    
    async def generate_with_fallback(
        self, 
        task: str, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        primary_model = self.get_model_for_task(task)
        fallback_model = self.get_model_for_task("followups")  # Cheaper fallback
        
        try:
            return await self.generate(primary_model, messages, tools, **kwargs)
        except Exception as e:
            logger.warning(f"Primary model {primary_model} failed: {e}. Trying fallback {fallback_model}")
            try:
                return await self.generate(fallback_model, messages, tools, **kwargs)
            except Exception as e2:
                logger.error(f"Fallback model {fallback_model} also failed: {e2}")
                raise e2