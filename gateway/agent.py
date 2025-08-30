import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from shared.models import ToolTrace, RAGQuery
from .llm_router import LLMRouter
from .rag import RAGService
from .tools import ToolRegistry
from .prompts import PromptManager
from .observability import observability, trace_function, TraceContext


logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, rag_service: RAGService):
        self.llm_router = LLMRouter()
        self.rag_service = rag_service
        self.tool_registry = ToolRegistry(rag_service)
        self.prompt_manager = PromptManager()
        
    @trace_function("agent_process_query")
    async def process_query(
        self, 
        shop_id: str, 
        user_message: str, 
        conversation_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            conversation_history = conversation_history or []
            tool_traces = []
            
            with TraceContext("agent_query", {"shop_id": shop_id, "message_length": len(user_message)}):
                decision = await self._make_planning_decision(shop_id, user_message, conversation_history)
            
            if decision["action"] == "rag_only":
                rag_response = await self._handle_rag_query(shop_id, user_message)
                followups = await self._generate_followups(user_message, rag_response["answer"])
                
                return {
                    "answer": rag_response["answer"],
                    "sources": rag_response["sources"],
                    "tool_traces": tool_traces,
                    "followups": followups,
                    "action_taken": "rag_search"
                }
            
            elif decision["action"] == "tool_use":
                tool_response = await self._handle_tool_usage(
                    shop_id, 
                    user_message, 
                    decision.get("tools", []),
                    conversation_history
                )
                tool_traces.extend(tool_response["tool_traces"])
                
                final_answer = await self._synthesize_tool_response(
                    user_message, 
                    tool_response["results"],
                    shop_id
                )
                
                followups = await self._generate_followups(user_message, final_answer)
                
                return {
                    "answer": final_answer,
                    "sources": tool_response.get("sources", []),
                    "tool_traces": tool_traces,
                    "followups": followups,
                    "action_taken": "tool_execution"
                }
            
            elif decision["action"] == "hybrid":
                rag_response = await self._handle_rag_query(shop_id, user_message)
                
                tool_response = await self._handle_tool_usage(
                    shop_id,
                    user_message,
                    decision.get("tools", []),
                    conversation_history,
                    rag_context=rag_response["answer"]
                )
                tool_traces.extend(tool_response["tool_traces"])
                
                combined_answer = await self._combine_rag_and_tools(
                    user_message,
                    rag_response,
                    tool_response["results"]
                )
                
                followups = await self._generate_followups(user_message, combined_answer)
                
                return {
                    "answer": combined_answer,
                    "sources": rag_response["sources"],
                    "tool_traces": tool_traces,
                    "followups": followups,
                    "action_taken": "hybrid_rag_tools"
                }
            
            else:
                direct_response = await self._handle_direct_response(user_message, conversation_history)
                followups = await self._generate_followups(user_message, direct_response)
                
                return {
                    "answer": direct_response,
                    "sources": [],
                    "tool_traces": [],
                    "followups": followups,
                    "action_taken": "direct_response"
                }
                
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            return {
                "answer": "I encountered an error while processing your request. Please try again.",
                "sources": [],
                "tool_traces": [],
                "followups": [],
                "action_taken": "error"
            }
    
    async def _make_planning_decision(
        self, 
        shop_id: str, 
        user_message: str, 
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        try:
            planner_prompt = await self.prompt_manager.get_prompt(
                "agent/planner", 
                {
                    "user_message": user_message,
                    "conversation_history": conversation_history[-3:] if conversation_history else [],
                    "available_tools": [tool["name"] for tool in self.tool_registry.get_tool_schemas()]
                }
            )
            
            messages = [{"role": "user", "content": planner_prompt}]
            
            response = await self.llm_router.generate_with_fallback(
                "planner",
                messages,
                tools=None,
                temperature=0.1
            )
            
            try:
                decision = json.loads(response)
                return decision
            except json.JSONDecodeError:
                logger.warning("Planner returned non-JSON response, defaulting to RAG")
                return {"action": "rag_only"}
                
        except Exception as e:
            logger.error(f"Planning decision failed: {e}")
            return {"action": "rag_only"}
    
    async def _handle_rag_query(self, shop_id: str, user_message: str) -> Dict[str, Any]:
        rag_query = RAGQuery(shop_id=shop_id, question=user_message)
        rag_response = await self.rag_service.query(rag_query)
        
        return {
            "answer": rag_response.answer,
            "sources": [
                {
                    "url": source.url,
                    "title": source.title,
                    "snippet": source.snippet,
                    "score": source.score
                } for source in rag_response.sources
            ]
        }
    
    async def _handle_tool_usage(
        self, 
        shop_id: str, 
        user_message: str, 
        suggested_tools: List[str],
        conversation_history: List[Dict[str, Any]],
        rag_context: str = None
    ) -> Dict[str, Any]:
        tool_traces = []
        tool_results = {}
        
        try:
            tool_use_prompt = await self.prompt_manager.get_prompt(
                "agent/tool_executor",
                {
                    "user_message": user_message,
                    "rag_context": rag_context,
                    "conversation_history": conversation_history[-2:] if conversation_history else []
                }
            )
            
            messages = [{"role": "user", "content": tool_use_prompt}]
            
            tool_schemas = self.tool_registry.get_tool_schemas()
            
            response = await self.llm_router.generate_with_fallback(
                "planner",
                messages,
                tools=tool_schemas,
                temperature=0.1
            )
            
            if isinstance(response, dict) and "tool_calls" in response:
                for tool_call in response["tool_calls"]:
                    start_time = datetime.utcnow()
                    
                    try:
                        arguments = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
                        
                        if "shop_id" in arguments and not arguments["shop_id"]:
                            arguments["shop_id"] = shop_id
                        
                        result = await self.tool_registry.execute_tool(tool_call["name"], arguments)
                        
                        end_time = datetime.utcnow()
                        latency_ms = int((end_time - start_time).total_seconds() * 1000)
                        
                        trace = ToolTrace(
                            ts=start_time,
                            name=tool_call["name"],
                            input=arguments,
                            output=result,
                            latency_ms=latency_ms
                        )
                        tool_traces.append(trace)
                        
                        tool_results[tool_call["name"]] = result
                        
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        error_trace = ToolTrace(
                            ts=start_time,
                            name=tool_call["name"],
                            input=arguments,
                            output={"error": str(e)},
                            latency_ms=0
                        )
                        tool_traces.append(error_trace)
            
            return {
                "results": tool_results,
                "tool_traces": tool_traces,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"Tool usage handling failed: {e}")
            return {
                "results": {},
                "tool_traces": tool_traces,
                "sources": []
            }
    
    async def _synthesize_tool_response(
        self, 
        user_message: str, 
        tool_results: Dict[str, Any],
        shop_id: str
    ) -> str:
        try:
            synthesis_prompt = await self.prompt_manager.get_prompt(
                "agent/synthesizer",
                {
                    "user_message": user_message,
                    "tool_results": tool_results
                }
            )
            
            messages = [{"role": "user", "content": synthesis_prompt}]
            
            response = await self.llm_router.generate_with_fallback(
                "rag_answer",
                messages,
                temperature=0.1
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Tool response synthesis failed: {e}")
            return f"I was able to gather some information using tools, but encountered an issue synthesizing the response. Here are the raw results: {json.dumps(tool_results, indent=2)}"
    
    async def _combine_rag_and_tools(
        self, 
        user_message: str, 
        rag_response: Dict[str, Any], 
        tool_results: Dict[str, Any]
    ) -> str:
        try:
            combination_prompt = await self.prompt_manager.get_prompt(
                "agent/combiner",
                {
                    "user_message": user_message,
                    "rag_answer": rag_response["answer"],
                    "rag_sources": rag_response["sources"],
                    "tool_results": tool_results
                }
            )
            
            messages = [{"role": "user", "content": combination_prompt}]
            
            response = await self.llm_router.generate_with_fallback(
                "rag_answer",
                messages,
                temperature=0.1
            )
            
            return response
            
        except Exception as e:
            logger.error(f"RAG and tools combination failed: {e}")
            return f"Based on the shop information: {rag_response['answer']}\n\nAdditionally, I gathered: {json.dumps(tool_results, indent=2)}"
    
    async def _handle_direct_response(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        try:
            direct_prompt = await self.prompt_manager.get_prompt(
                "agent/direct",
                {
                    "user_message": user_message,
                    "conversation_history": conversation_history[-3:] if conversation_history else []
                }
            )
            
            messages = [{"role": "user", "content": direct_prompt}]
            
            response = await self.llm_router.generate_with_fallback(
                "followups",
                messages,
                temperature=0.3
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Direct response failed: {e}")
            return "I'm here to help you with shopping questions. Could you please rephrase your question or ask about products, policies, or other shop-related topics?"
    
    async def _generate_followups(self, user_message: str, answer: str) -> List[str]:
        try:
            followup_prompt = await self.prompt_manager.get_prompt(
                "features/followups",
                {
                    "user_message": user_message,
                    "answer": answer
                }
            )
            
            messages = [{"role": "user", "content": followup_prompt}]
            
            response = await self.llm_router.generate_with_fallback(
                "followups",
                messages,
                temperature=0.7
            )
            
            try:
                followups_data = json.loads(response)
                return followups_data.get("followups", [])
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            logger.error(f"Followups generation failed: {e}")
            return []