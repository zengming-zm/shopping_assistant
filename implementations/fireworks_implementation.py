"""
Fireworks AI Qwen3 Implementation
Direct API call implementation using Fireworks AI hosted Qwen3 models
"""

import os
from typing import List, Dict, Any, Tuple
from fireworks.client import Fireworks
from googleapiclient.discovery import build
from dotenv import load_dotenv

from core.base import BaseQueryRewriter, BaseSearchProvider, BaseLLMProvider, BaseShoppingAssistant

load_dotenv()

class FireworksQwen3LLM(BaseLLMProvider):
    """Fireworks AI Qwen3 LLM provider with thinking mode"""
    
    def __init__(self):
        self.api_key = os.getenv('FIREWORKS_API_KEY')
        self.model_name = os.getenv('QWEN3_MODEL', 'accounts/fireworks/models/qwen3-235b-a22b')
        self.client = None
        
        if self.api_key:
            self.client = Fireworks(api_key=self.api_key)
    
    def generate_response(self, messages: List[Dict], enable_thinking: bool = True) -> Dict[str, Any]:
        """Generate response using Fireworks AI Qwen3"""
        
        if not self.client:
            return {
                'content': "Please configure FIREWORKS_API_KEY in your .env file.",
                'thinking': "",
                'success': False
            }
        
        try:
            # Enhance system message for thinking mode
            if enable_thinking and messages:
                for msg in messages:
                    if msg['role'] == 'system':
                        msg['content'] += "\n\nIMPORTANT: Use <think>...</think> tags to show your step-by-step reasoning process before providing your final answer."
                        break
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.6,
                max_tokens=2000
            )
            
            if response.choices:
                choice = response.choices[0]
                content = choice.message.content
                
                # Extract thinking process from <think> tags
                thinking_content = ""
                final_content = content
                
                if '<think>' in content and '</think>' in content:
                    import re
                    thinking_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                    if thinking_match:
                        thinking_content = thinking_match.group(1).strip()
                        final_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                
                return {
                    'content': final_content,
                    'thinking': thinking_content,
                    'success': True
                }
            
            return {
                'content': "No response from Fireworks AI",
                'thinking': "",
                'success': False
            }
            
        except Exception as e:
            return {
                'content': f"Fireworks AI Error: {str(e)}",
                'thinking': "",
                'success': False
            }

class FireworksQueryRewriter(BaseQueryRewriter):
    """Fireworks AI Qwen3-based query rewriter"""
    
    def __init__(self):
        self.llm = FireworksQwen3LLM()
    
    def rewrite_to_keyphrases(self, current_query: str, conversation_context: str, domain: str) -> Tuple[List[str], str, str]:
        """Rewrite query using Fireworks AI Qwen3"""
        
        if not conversation_context.strip():
            return [current_query], "No context available, using original query", ""
        
        messages = [
            {
                "role": "system",
                "content": "You are a Google Search query expert for e-commerce. Use thinking mode to analyze conversation context and generate optimal search phrases."
            },
            {
                "role": "user", 
                "content": f"""Analyze this conversation and rewrite the query into Google search key phrases.

CONVERSATION CONTEXT:
{conversation_context}

CURRENT USER QUERY: {current_query}
WEBSITE DOMAIN: {domain}

Think through the context, identify pronouns/vague references, and generate 2-4 optimized Google search phrases.

Format:
KEYPHRASES:
- [phrase 1]
- [phrase 2]
- [phrase 3]

REASONING: [explanation]"""
            }
        ]
        
        result = self.llm.generate_response(messages, enable_thinking=True)
        
        if result['success']:
            content = result['content']
            thinking = result['thinking']
            
            # Parse keyphrases and reasoning
            keyphrases = []
            reasoning = ""
            
            if "KEYPHRASES:" in content and "REASONING:" in content:
                lines = content.split('\n')
                in_keyphrases = False
                
                for line in lines:
                    if line.startswith("KEYPHRASES:"):
                        in_keyphrases = True
                        continue
                    elif line.startswith("REASONING:"):
                        in_keyphrases = False
                        reasoning = line.replace("REASONING:", "").strip()
                        continue
                    
                    if in_keyphrases and line.strip().startswith("- "):
                        phrase = line.strip()[2:]
                        if phrase:
                            keyphrases.append(phrase)
                
                if keyphrases:
                    return keyphrases, reasoning, thinking
            
            # Fallback
            return [current_query], "Fallback: " + content[:100], thinking
        
        return [current_query], f"Error: {result['content']}", ""

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
                'snippet': 'Please configure GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID',
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
                print(f"Google Search error for '{phrase}': {e}")
                continue
        
        return all_results[:num_results * 2]

class FireworksDirectImplementation(BaseShoppingAssistant):
    """Direct API call implementation using Fireworks AI Qwen3"""
    
    def __init__(self):
        super().__init__()
        self.llm = FireworksQwen3LLM()
        self.query_rewriter = FireworksQueryRewriter()
        self.search_provider = GoogleSearchProvider()
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        save_to_memory: bool = True,
        enable_thinking: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using direct Fireworks AI calls"""
        
        # Get conversation context
        conversation_context = self.memory.get_recent_context(domain, num_turns=3)
        
        # Rewrite query with thinking
        rewritten_keyphrases, rewrite_reasoning, query_thinking = self.query_rewriter.rewrite_to_keyphrases(
            user_message, conversation_context, domain
        )
        
        # Search for evidence
        search_results = self.search_provider.search(rewritten_keyphrases, num_results=2)
        
        # Prepare evidence
        evidence = ""
        if search_results:
            evidence = f"\n{domain.upper()} Product Information (Google Search):\n"
            for i, result in enumerate(search_results, 1):
                evidence += f"{i}. **{result['title']}**\n"
                evidence += f"   {result['snippet']}\n"
                evidence += f"   Source: {result['url']}\n"
                evidence += f"   Via: '{result.get('search_phrase', 'unknown')}'\n\n"
        else:
            evidence = f"\nNo Google Search results for: {', '.join(rewritten_keyphrases)}\n"
        
        # Generate response with Qwen3
        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful Shopping Assistant for {domain} powered by Qwen3 with thinking capabilities.

## Guidelines
- Use thinking mode to analyze customer needs and search evidence carefully
- Provide accurate information based on Google Search evidence
- Maintain conversation context and acknowledge previous discussion
- Be conversational but professional
- Reference sources when providing specific information
- Never include emojis in responses"""
            },
            {
                "role": "user",
                "content": f"""Help with this shopping question using your thinking capabilities.

CONVERSATION CONTEXT:
{conversation_context if conversation_context.strip() else "New conversation"}

USER QUESTION: {user_message}
SEARCH PHRASES: {', '.join(rewritten_keyphrases)}
REWRITE REASONING: {rewrite_reasoning}

GOOGLE SEARCH EVIDENCE:
{evidence}

Think through the context and evidence, then provide a helpful response."""
            }
        ]
        
        api_result = self.llm.generate_response(messages, enable_thinking=enable_thinking)
        
        response_text = api_result['content']
        thinking_process = api_result['thinking']
        
        # Save to memory
        if save_to_memory and api_result['success']:
            self.memory.add_turn(
                domain, user_message, response_text, thinking_process, search_results,
                metadata={'implementation': 'fireworks_direct', 'model': self.llm.model_name}
            )
        
        return {
            'response': response_text,
            'thinking_process': thinking_process,
            'sources': search_results,
            'rewritten_keyphrases': rewritten_keyphrases,
            'rewrite_reasoning': rewrite_reasoning,
            'conversation_context_used': conversation_context,
            'query_thinking': query_thinking,
            'metadata': {
                'implementation': 'fireworks_direct',
                'model': self.llm.model_name,
                'thinking_enabled': enable_thinking
            }
        }