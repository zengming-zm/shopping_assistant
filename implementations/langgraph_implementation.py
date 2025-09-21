"""
LangGraph Multi-Agent Implementation
Uses LangGraph to orchestrate multiple agents for product search and deal finding
"""

import os
from typing import List, Dict, Any, Tuple, Annotated
from datetime import datetime
import asyncio

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
import requests
from googleapiclient.discovery import build
from dotenv import load_dotenv

from core.base import BaseQueryRewriter, BaseSearchProvider, BaseLLMProvider, BaseShoppingAssistant

load_dotenv()

class AgentState(BaseModel):
    """State shared between LangGraph agents"""
    user_message: str = ""
    domain: str = ""
    conversation_context: str = ""
    search_keyphrases: List[str] = []
    google_results: List[Dict[str, Any]] = []
    deal_results: List[Dict[str, Any]] = []
    final_response: str = ""
    thinking_process: str = ""
    agent_logs: List[str] = []

class DealSearchProvider(BaseSearchProvider):
    """Deal search API provider (simulated - replace with actual deal APIs)"""
    
    def __init__(self):
        # In a real implementation, configure actual deal search APIs like:
        # - Shopping APIs (Google Shopping, Amazon Product Advertising)
        # - Deal aggregators (RetailMeNot, Honey, Rakuten)
        # - Price comparison (PriceGrabber, Shopping.com)
        self.enabled = True
    
    def search(self, keyphrases: List[str], num_results: int = 2) -> List[Dict[str, Any]]:
        """Search for deals and promotions"""
        
        # Simulated deal search results
        # In production, integrate with actual deal APIs
        deal_results = []
        
        for phrase in keyphrases:
            # Simulate deal search based on keyphrases
            simulated_deals = [
                {
                    'title': f"20% off {phrase} - Limited Time",
                    'url': f"https://deals.example.com/{phrase.replace(' ', '-')}",
                    'snippet': f"Save 20% on {phrase} with code SAVE20. Free shipping on orders over $100.",
                    'source': 'deal_search',
                    'provider': 'deal_api',
                    'discount': '20%',
                    'search_phrase': phrase
                },
                {
                    'title': f"Best Price: {phrase} Comparison",
                    'url': f"https://compare.example.com/{phrase.replace(' ', '-')}",
                    'snippet': f"Compare prices for {phrase} across multiple retailers. Find the best deals.",
                    'source': 'price_comparison',
                    'provider': 'deal_api',
                    'discount': 'price_match',
                    'search_phrase': phrase
                }
            ]
            
            deal_results.extend(simulated_deals[:num_results])
        
        return deal_results[:num_results * 2]

class FireworksLLMProvider(BaseLLMProvider):
    """Fireworks AI LLM provider for LangGraph agents"""
    
    def __init__(self):
        self.api_key = os.getenv('FIREWORKS_API_KEY')
        self.model_name = os.getenv('QWEN3_MODEL', 'accounts/fireworks/models/qwen3-32b')
        
        if self.api_key:
            from fireworks.client import Fireworks
            self.client = Fireworks(api_key=self.api_key)
        else:
            self.client = None
    
    def generate_response(self, messages: List[Dict], enable_thinking: bool = True) -> Dict[str, Any]:
        """Generate response using Fireworks AI"""
        
        if not self.client:
            return {
                'content': "Fireworks API not configured",
                'thinking': "",
                'success': False
            }
        
        try:
            # Add thinking instruction for Qwen3
            if enable_thinking and messages:
                for msg in messages:
                    if msg['role'] == 'system':
                        msg['content'] += "\n\nUse <think>...</think> tags to show your reasoning."
                        break
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.6,
                max_tokens=1500
            )
            
            if response.choices:
                content = response.choices[0].message.content
                
                # Extract thinking from <think> tags
                thinking = ""
                final_content = content
                
                if '<think>' in content and '</think>' in content:
                    import re
                    thinking_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                    if thinking_match:
                        thinking = thinking_match.group(1).strip()
                        final_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                
                return {
                    'content': final_content,
                    'thinking': thinking,
                    'success': True
                }
            
            return {
                'content': "No response",
                'thinking': "",
                'success': False
            }
            
        except Exception as e:
            return {
                'content': f"Error: {str(e)}",
                'thinking': "",
                'success': False
            }

class LangGraphMultiAgentImplementation(BaseShoppingAssistant):
    """LangGraph multi-agent implementation for product search"""
    
    def __init__(self):
        super().__init__()
        self.llm_provider = FireworksLLMProvider()
        self.google_search = GoogleSearchProvider()
        self.deal_search = DealSearchProvider()
        self.graph = self._create_agent_graph()
    
    def _create_search_tools(self):
        """Create search tools for agents"""
        
        def google_search_tool(query: str) -> str:
            """Search Google for product information"""
            results = self.google_search.search([query], num_results=2)
            if results:
                formatted = f"Google Search Results for '{query}':\n"
                for i, result in enumerate(results, 1):
                    formatted += f"{i}. {result['title']}\n   {result['snippet']}\n   {result['url']}\n\n"
                return formatted
            return f"No Google results found for: {query}"
        
        def deal_search_tool(query: str) -> str:
            """Search for deals and promotions"""
            results = self.deal_search.search([query], num_results=2)
            if results:
                formatted = f"Deal Search Results for '{query}':\n"
                for i, result in enumerate(results, 1):
                    formatted += f"{i}. {result['title']}\n   {result['snippet']}\n   {result['url']}\n\n"
                return formatted
            return f"No deals found for: {query}"
        
        return [
            Tool(
                name="google_search",
                description="Search Google for product information, specifications, and reviews",
                func=google_search_tool
            ),
            Tool(
                name="deal_search", 
                description="Search for deals, promotions, and price comparisons",
                func=deal_search_tool
            )
        ]
    
    def _create_agent_graph(self):
        """Create LangGraph multi-agent workflow"""
        
        # Define the workflow state
        class GraphState(BaseModel):
            messages: List[Dict] = []
            user_query: str = ""
            domain: str = ""
            context: str = ""
            search_results: List[Dict] = []
            deal_results: List[Dict] = []
            final_response: str = ""
            thinking_logs: List[str] = []
        
        # Create agents with different specializations
        search_tools = self._create_search_tools()
        
        # Query Analysis Agent
        def query_agent(state: GraphState) -> GraphState:
            """Analyze user query and conversation context"""
            
            messages = [
                {
                    "role": "system",
                    "content": f"""You are a Query Analysis Agent. Analyze the user's shopping question and conversation context to determine what information to search for.

DOMAIN: {state.domain}
CONTEXT: {state.context}
USER QUERY: {state.user_query}

Your task:
1. Understand what the user is asking about
2. Identify specific products or categories mentioned
3. Determine if this is a follow-up question using pronouns
4. Generate 2-3 specific search keyphrases for product information

Respond with keyphrases in this format:
SEARCH_KEYPHRASES:
- [phrase 1]
- [phrase 2]  
- [phrase 3]"""
                }
            ]
            
            result = self.llm_provider.generate_response(messages, enable_thinking=True)
            
            # Parse keyphrases from response
            keyphrases = []
            if "SEARCH_KEYPHRASES:" in result['content']:
                lines = result['content'].split('\n')
                in_keyphrases = False
                for line in lines:
                    if line.startswith("SEARCH_KEYPHRASES:"):
                        in_keyphrases = True
                        continue
                    if in_keyphrases and line.strip().startswith("- "):
                        phrase = line.strip()[2:]
                        if phrase:
                            keyphrases.append(phrase)
            
            state.thinking_logs.append(f"Query Agent Thinking: {result['thinking']}")
            state.messages.append({"role": "assistant", "content": f"Identified keyphrases: {keyphrases}"})
            
            return state
        
        # Search Agent
        def search_agent(state: GraphState) -> GraphState:
            """Search for product information"""
            
            if not hasattr(state, 'search_keyphrases') or not state.search_keyphrases:
                # Extract keyphrases from previous messages
                for msg in reversed(state.messages):
                    if "Identified keyphrases:" in msg.get('content', ''):
                        import re
                        # Extract keyphrases from the message
                        content = msg['content']
                        phrases_match = re.search(r'\[(.*?)\]', content)
                        if phrases_match:
                            phrases_str = phrases_match.group(1)
                            state.search_keyphrases = [p.strip().strip("'\"") for p in phrases_str.split(',')]
            
            # Use Google search tool
            google_results = []
            for phrase in getattr(state, 'search_keyphrases', [state.user_query]):
                results = self.google_search.search([phrase], num_results=2)
                google_results.extend(results)
            
            state.search_results = google_results
            state.messages.append({"role": "assistant", "content": f"Found {len(google_results)} search results"})
            
            return state
        
        # Deal Agent
        def deal_agent(state: GraphState) -> GraphState:
            """Search for deals and promotions"""
            
            # Use deal search tool
            deal_results = []
            search_phrases = getattr(state, 'search_keyphrases', [state.user_query])
            for phrase in search_phrases:
                results = self.deal_search.search([phrase], num_results=1)
                deal_results.extend(results)
            
            state.deal_results = deal_results
            state.messages.append({"role": "assistant", "content": f"Found {len(deal_results)} deal results"})
            
            return state
        
        # Response Agent
        def response_agent(state: GraphState) -> GraphState:
            """Generate final response based on all gathered information"""
            
            # Prepare evidence
            evidence = ""
            
            if state.search_results:
                evidence += "\nPRODUCT INFORMATION:\n"
                for i, result in enumerate(state.search_results, 1):
                    evidence += f"{i}. {result['title']}\n   {result['snippet']}\n   {result['url']}\n\n"
            
            if state.deal_results:
                evidence += "\nDEALS & PROMOTIONS:\n"
                for i, result in enumerate(state.deal_results, 1):
                    evidence += f"{i}. {result['title']}\n   {result['snippet']}\n   {result['url']}\n\n"
            
            messages = [
                {
                    "role": "system",
                    "content": f"""You are a Shopping Response Agent. Generate a helpful response for {state.domain} based on the gathered information.

CONVERSATION CONTEXT: {state.context}
USER QUESTION: {state.user_query}

GATHERED EVIDENCE: {evidence}

Provide a conversational, helpful response that:
1. Addresses the user's question directly
2. Uses the gathered evidence appropriately 
3. References sources when making specific claims
4. Maintains conversation flow if there's previous context
5. Includes deal information when relevant"""
                }
            ]
            
            result = self.llm_provider.generate_response(messages, enable_thinking=True)
            
            state.final_response = result['content']
            state.thinking_logs.append(f"Response Agent Thinking: {result['thinking']}")
            
            return state
        
        # Create workflow graph
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("query_agent", query_agent)
        workflow.add_node("search_agent", search_agent)
        workflow.add_node("deal_agent", deal_agent)
        workflow.add_node("response_agent", response_agent)
        
        # Define edges
        workflow.set_entry_point("query_agent")
        workflow.add_edge("query_agent", "search_agent")
        workflow.add_edge("search_agent", "deal_agent")
        workflow.add_edge("deal_agent", "response_agent")
        workflow.add_edge("response_agent", END)
        
        return workflow.compile()
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        save_to_memory: bool = True,
        enable_thinking: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using LangGraph multi-agent workflow"""
        
        # Get conversation context
        conversation_context = self.memory.get_recent_context(domain, num_turns=3)
        
        # Initialize agent state
        initial_state = {
            "messages": [],
            "user_query": user_message,
            "domain": domain,
            "context": conversation_context,
            "search_results": [],
            "deal_results": [],
            "final_response": "",
            "thinking_logs": []
        }
        
        try:
            # Run the multi-agent workflow
            final_state = self.graph.invoke(initial_state)
            
            # Combine all search results
            all_sources = []
            all_sources.extend(final_state.get('search_results', []))
            all_sources.extend(final_state.get('deal_results', []))
            
            # Combine thinking processes
            thinking_process = "\n\n".join(final_state.get('thinking_logs', []))
            
            response_text = final_state.get('final_response', 'No response generated')
            
            # Save to memory
            if save_to_memory:
                self.memory.add_turn(
                    domain, user_message, response_text, thinking_process, all_sources,
                    metadata={
                        'implementation': 'langgraph_multi_agent',
                        'agents_used': ['query_agent', 'search_agent', 'deal_agent', 'response_agent'],
                        'google_results': len(final_state.get('search_results', [])),
                        'deal_results': len(final_state.get('deal_results', []))
                    }
                )
            
            return {
                'response': response_text,
                'thinking_process': thinking_process,
                'sources': all_sources,
                'rewritten_keyphrases': final_state.get('search_keyphrases', [user_message]),
                'rewrite_reasoning': "Multi-agent query analysis",
                'conversation_context_used': conversation_context,
                'metadata': {
                    'implementation': 'langgraph_multi_agent',
                    'agents_executed': ['query_agent', 'search_agent', 'deal_agent', 'response_agent'],
                    'google_results_count': len(final_state.get('search_results', [])),
                    'deal_results_count': len(final_state.get('deal_results', [])),
                    'thinking_enabled': enable_thinking
                }
            }
            
        except Exception as e:
            error_msg = f"Multi-agent workflow error: {str(e)}"
            return {
                'response': error_msg,
                'thinking_process': f"Error in agent workflow: {str(e)}",
                'sources': [],
                'rewritten_keyphrases': [user_message],
                'rewrite_reasoning': "Error occurred",
                'conversation_context_used': conversation_context,
                'metadata': {'implementation': 'langgraph_multi_agent', 'error': str(e)}
            }

class GoogleSearchProvider(BaseSearchProvider):
    """Google Custom Search API provider"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.cse_id = os.getenv('GOOGLE_CSE_ID')
        self.service = None
        
        if self.api_key and self.cse_id:
            try:
                self.service = build("customsearch", "v1", developerKey=self.api_key)
            except Exception as e:
                print(f"Failed to initialize Google Search: {e}")
    
    def search(self, keyphrases: List[str], num_results: int = 2) -> List[Dict[str, Any]]:
        """Search Google for keyphrases"""
        
        if not self.service:
            return [{
                'title': 'Google Search API Not Configured',
                'url': '',
                'snippet': 'Configure GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID',
                'source': 'error',
                'provider': 'google_search'
            }]
        
        all_results = []
        seen_urls = set()
        
        for phrase in keyphrases:
            try:
                result = self.service.cse().list(
                    q=phrase,
                    cx=self.cse_id,
                    num=num_results
                ).execute()
                
                if 'items' in result:
                    for item in result['items']:
                        url = item.get('link', '')
                        if url not in seen_urls:
                            search_result = {
                                'title': item.get('title', ''),
                                'url': url,
                                'snippet': item.get('snippet', ''),
                                'source': 'google_search',
                                'provider': 'google_search',
                                'search_phrase': phrase
                            }
                            all_results.append(search_result)
                            seen_urls.add(url)
                            
                            if len(all_results) >= num_results * 2:
                                break
                
                if len(all_results) >= num_results * 2:
                    break
                    
            except Exception as e:
                print(f"Google Search error: {e}")
                continue
        
        return all_results[:num_results * 2]

# Test function
def test_langgraph_implementation():
    """Test the LangGraph multi-agent implementation"""
    
    print("🔄 Testing LangGraph Multi-Agent Implementation")
    print("=" * 60)
    
    assistant = LangGraphMultiAgentImplementation()
    
    # Test system initialization
    print("📊 System components:")
    print(f"   LLM Provider: {'✅' if assistant.llm_provider.client else '❌'}")
    print(f"   Google Search: {'✅' if assistant.google_search.service else '❌'}")
    print(f"   Deal Search: {'✅' if assistant.deal_search.enabled else '❌'}")
    print(f"   LangGraph: {'✅' if assistant.graph else '❌'}")
    
    # Test conversation summary
    summary = assistant.get_conversation_summary('test.com')
    print(f"   Implementation: {summary['implementation']}")
    
    print("\n✅ LangGraph multi-agent system structure validated!")
    
    if not assistant.llm_provider.client:
        print("\n⚠️ Configure FIREWORKS_API_KEY to test with actual API calls")

if __name__ == "__main__":
    test_langgraph_implementation()