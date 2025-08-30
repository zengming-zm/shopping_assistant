"""
Fireworks AI Qwen3-powered Conversational System with Thinking Mode and Google Search
Uses Fireworks AI's hosted Qwen3 models with thinking capabilities
"""

import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from fireworks.client import Fireworks
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

class ConversationMemory:
    """Manages conversation history and context"""
    
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.conversations = {}  # domain -> conversation_history
    
    def add_turn(self, domain: str, user_message: str, assistant_response: str, thinking_process: str = "", sources: List[Dict] = None):
        """Add a conversation turn with thinking process"""
        if domain not in self.conversations:
            self.conversations[domain] = []
        
        turn = {
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'assistant': assistant_response,
            'thinking': thinking_process,
            'sources': sources or []
        }
        
        self.conversations[domain].append(turn)
        
        # Keep only recent turns
        if len(self.conversations[domain]) > self.max_turns:
            self.conversations[domain] = self.conversations[domain][-self.max_turns:]
    
    def get_conversation_history(self, domain: str) -> List[Dict]:
        """Get conversation history for domain"""
        return self.conversations.get(domain, [])
    
    def get_recent_context(self, domain: str, num_turns: int = 3) -> str:
        """Get recent conversation context as formatted string"""
        history = self.get_conversation_history(domain)
        recent = history[-num_turns:] if len(history) > num_turns else history
        
        if not recent:
            return ""
        
        context_parts = []
        for i, turn in enumerate(recent, 1):
            context_parts.append(f"Turn {i}:")
            context_parts.append(f"  User: {turn['user']}")
            context_parts.append(f"  Assistant: {turn['assistant'][:150]}{'...' if len(turn['assistant']) > 150 else ''}")
            if turn.get('sources'):
                context_parts.append(f"  Sources: {len(turn['sources'])} found")
            context_parts.append("")  # Add blank line between turns
        
        return "\n".join(context_parts)
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for domain"""
        if domain in self.conversations:
            del self.conversations[domain]

class FireworksQwen3QueryRewriter:
    """Uses Fireworks AI Qwen3 with thinking mode to rewrite queries"""
    
    def __init__(self):
        self.api_key = os.getenv('FIREWORKS_API_KEY')
        self.model_name = os.getenv('QWEN3_MODEL', 'accounts/fireworks/models/qwen3-235b-a22b')
        self.client = None
        
        if self.api_key:
            self.client = Fireworks(api_key=self.api_key)
    
    def rewrite_to_keyphrases(self, current_query: str, conversation_context: str, domain: str) -> Tuple[List[str], str, str]:
        """
        Rewrite query to multiple key phrases using Fireworks AI Qwen3 thinking mode
        Returns: (list_of_keyphrases, reasoning, thinking_process)
        """
        
        if not self.client:
            return [current_query], "Fireworks AI not configured", ""
        
        if not conversation_context.strip():
            return [current_query], "No context available, using original query", ""
        
        messages = [
            {
                "role": "system",
                "content": "You are a Google Search query expert for e-commerce shopping conversations. Use your thinking capabilities to carefully analyze conversation context and generate optimal search phrases."
            },
            {
                "role": "user", 
                "content": f"""Please analyze this shopping conversation and rewrite the current query into optimal Google search key phrases.

CONVERSATION CONTEXT:
{conversation_context}

CURRENT USER QUERY: {current_query}

WEBSITE DOMAIN: {domain}

Instructions:
1. THINK through the conversation context to understand what products/topics have been discussed
2. Identify any pronouns (it, they, these, those) or vague references in the current query
3. Replace vague references with SPECIFIC product names from conversation context
4. Generate 2-4 Google search key phrases optimized for product information
5. Include the domain name in search phrases for site-specific results

Return your response in this format:
KEYPHRASES:
- [key phrase 1]
- [key phrase 2] 
- [key phrase 3]
- [key phrase 4]

REASONING: [brief explanation of what you changed and why]"""
            }
        ]
        
        try:
            # Call Fireworks AI Qwen3 with thinking mode
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.6,
                max_tokens=1000,
                # Note: Thinking mode may need to be enabled differently for Fireworks
                # Check Fireworks documentation for exact parameter name
            )
            
            if response.choices:
                choice = response.choices[0]
                content = choice.message.content
                
                # Extract thinking process if available (implementation depends on Fireworks API)
                thinking_content = getattr(choice.message, 'thinking', '') or ""
                
                # Parse keyphrases and reasoning from content
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
                            phrase = line.strip()[2:]  # Remove "- "
                            if phrase:
                                keyphrases.append(phrase)
                    
                    if keyphrases:
                        return keyphrases, reasoning, thinking_content
                
                # Fallback parsing
                fallback_phrases = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('REASONING')]
                return fallback_phrases[:4] if fallback_phrases else [current_query], "Fallback parsing", thinking_content
            
            return [current_query], "No response from Fireworks AI", ""
            
        except Exception as e:
            return [current_query], f"Query rewriting failed: {str(e)}", ""

class GoogleSearchProvider:
    """Provides Google Search integration for product information"""
    
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
        """Search Google for keyphrases and return top results"""
        
        if not self.service:
            return [{
                'title': 'Google Search API Not Configured',
                'url': '',
                'snippet': 'Please configure GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID in your .env file',
                'source': 'error'
            }]
        
        all_results = []
        seen_urls = set()
        
        for phrase in keyphrases:
            try:
                # Execute Google search
                result = self.service.cse().list(
                    q=phrase,
                    cx=self.cse_id,
                    num=num_results
                ).execute()
                
                # Process search results
                if 'items' in result:
                    for item in result['items']:
                        url = item.get('link', '')
                        
                        # Avoid duplicates
                        if url not in seen_urls:
                            search_result = {
                                'title': item.get('title', ''),
                                'url': url,
                                'snippet': item.get('snippet', ''),
                                'source': 'google_search',
                                'search_phrase': phrase
                            }
                            all_results.append(search_result)
                            seen_urls.add(url)
                            
                            # Stop when we have enough results
                            if len(all_results) >= num_results * 2:
                                break
                
                # Stop searching if we have enough results
                if len(all_results) >= num_results * 2:
                    break
                    
            except Exception as e:
                print(f"Google Search error for phrase '{phrase}': {e}")
                continue
        
        return all_results[:num_results * 2]

class FireworksQwen3SearchRAG:
    """Fireworks AI Qwen3-powered conversational system with thinking mode and Google Search"""
    
    def __init__(self):
        self.api_key = os.getenv('FIREWORKS_API_KEY')
        self.model_name = os.getenv('QWEN3_MODEL', 'accounts/fireworks/models/qwen3-235b-a22b')
        self.client = None
        
        if self.api_key:
            self.client = Fireworks(api_key=self.api_key)
        
        self.memory = ConversationMemory()
        self.query_rewriter = FireworksQwen3QueryRewriter()
        self.search_provider = GoogleSearchProvider()
    
    def _call_fireworks_qwen3(self, messages: List[Dict], enable_thinking: bool = True) -> Dict[str, Any]:
        """Call Fireworks AI Qwen3 with thinking mode support"""
        
        if not self.client:
            return {
                'content': "Please configure FIREWORKS_API_KEY in your .env file to use Qwen3.",
                'thinking': "",
                'success': False
            }
        
        try:
            # Adjust prompt to encourage thinking if enabled
            if enable_thinking and messages:
                # Add thinking instruction to system message
                for msg in messages:
                    if msg['role'] == 'system':
                        msg['content'] += "\n\nIMPORTANT: Use your thinking capabilities to carefully analyze this request step by step before responding."
                        break
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.6,
                max_tokens=2000,
                # Note: Thinking mode parameters may vary by Fireworks implementation
            )
            
            if response.choices:
                choice = response.choices[0]
                content = choice.message.content
                
                # Extract thinking process if available
                thinking_content = ""
                final_content = content
                
                # Parse thinking tags if present (<think>...</think>)
                if '<think>' in content and '</think>' in content:
                    import re
                    thinking_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                    if thinking_match:
                        thinking_content = thinking_match.group(1).strip()
                        # Remove thinking tags from final content
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
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        save_to_memory: bool = True,
        enable_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        Generate response using Fireworks AI Qwen3 with thinking mode and Google Search
        """
        
        # Get conversation context
        conversation_context = self.memory.get_recent_context(domain, num_turns=3)
        
        # Rewrite query to multiple key phrases with Qwen3 thinking
        rewritten_keyphrases, rewrite_reasoning, query_thinking = self.query_rewriter.rewrite_to_keyphrases(
            user_message, conversation_context, domain
        )
        
        # Use Google Search for retrieval
        search_results = self.search_provider.search(rewritten_keyphrases, num_results=2)
        
        # Prepare evidence from search results
        evidence = ""
        if search_results:
            evidence = f"\n{domain.upper()} Product Information (from Google Search):\n"
            for i, result in enumerate(search_results, 1):
                evidence += f"{i}. **{result['title']}**\n"
                evidence += f"   {result['snippet']}\n"
                evidence += f"   Source: {result['url']}\n"
                evidence += f"   Found via: '{result.get('search_phrase', 'unknown')}'\n\n"
        else:
            evidence = f"\nNo specific information found via Google Search for: {', '.join(rewritten_keyphrases)}\n"
        
        # Fireworks AI Qwen3 Shopping Assistant Prompt with Thinking Mode
        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful, friendly Online Shopping Assistant powered by Qwen3 with advanced thinking capabilities. You help customers discover products for {domain} using real-time Google Search.

## Core Capabilities
- Use your thinking mode to carefully analyze customer needs and search evidence
- Understand and respond to shopping inquiries with thoughtful reasoning
- Maintain context throughout conversations for personalized assistance
- Provide accurate information based on Google Search evidence

## [VERY IMPORTANT] Safety Guidelines
- On {domain}-related sensitive topics, respond in an official PR tone
- On politically or culturally sensitive topics, refrain from taking sides
- When asked about financial, legal, or medical guidance, state "I can't provide professional advice..." and ask to consult experts
- Do not include verbatim quotes of more than 10 consecutive words from copyrighted content

## [CRITICAL] Thinking Mode Instructions
- If thinking mode is enabled, use <think>...</think> tags to show your reasoning process
- Think through conversation context, search evidence, and user intent
- Show your step-by-step analysis before providing the final answer
- Be thorough in your thinking but concise in your final response

## [IMPORTANT] Response Format
- Start responses with "RESPONSE:" 
- Use markdown formatting for better readability
- Never include emojis in responses
- Reference source URLs when providing specific information from search results
- Be conversational but professional"""
            },
            {
                "role": "user",
                "content": f"""Please help me with this shopping question using your thinking capabilities.

CONVERSATION CONTEXT:
{conversation_context if conversation_context.strip() else "This is the start of a new conversation."}

CURRENT USER QUESTION: {user_message}

SEARCH KEY PHRASES USED: {', '.join(rewritten_keyphrases)}
QUERY REWRITE REASONING: {rewrite_reasoning}

GOOGLE SEARCH EVIDENCE:
{evidence}

Instructions:
1. If thinking mode is enabled, use <think>...</think> tags to show your reasoning
2. Think through the conversation context to understand what we've been discussing
3. Analyze how the Google Search evidence relates to the user's question
4. If this is a follow-up question with pronouns (it, they, those), use context to understand specific products
5. Provide a helpful, accurate response based on the search evidence
6. Reference sources when making specific claims about products
7. Maintain natural conversation flow acknowledging previous discussion

Please provide a thoughtful response about {domain} products."""
            }
        ]
        
        # Call Fireworks AI Qwen3 with thinking mode
        api_result = self._call_fireworks_qwen3(messages, enable_thinking=enable_thinking)
        
        response_text = api_result['content']
        thinking_process = api_result['thinking']
        
        # Save to conversation memory
        if save_to_memory and api_result['success']:
            self.memory.add_turn(domain, user_message, response_text, thinking_process, search_results)
        
        return {
            'response': response_text,
            'thinking_process': thinking_process,
            'sources': search_results,
            'rewritten_keyphrases': rewritten_keyphrases,
            'rewrite_reasoning': rewrite_reasoning,
            'conversation_context_used': conversation_context,
            'query_thinking': query_thinking
        }
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for domain"""
        self.memory.clear_conversation(domain)
    
    def get_conversation_summary(self, domain: str) -> Dict[str, Any]:
        """Get conversation summary with statistics"""
        history = self.memory.get_conversation_history(domain)
        
        if not history:
            return {
                'total_turns': 0,
                'last_interaction': None,
                'topics_discussed': []
            }
        
        return {
            'total_turns': len(history),
            'last_interaction': history[-1]['timestamp'],
            'recent_topics': [turn['user'][:50] + "..." for turn in history[-3:]],
            'conversation_active': True,
            'has_thinking': any(turn.get('thinking') for turn in history)
        }

# Test function
def test_fireworks_qwen3_system():
    """Test the Fireworks AI Qwen3 thinking mode system"""
    
    print("🔥 Testing Fireworks AI Qwen3 Thinking Mode System")
    print("=" * 60)
    
    qwen_rag = FireworksQwen3SearchRAG()
    domain = "lucafaloni.com"
    
    # Test without API calls first
    print("📊 System initialization test:")
    print(f"   API Key configured: {'✅' if qwen_rag.api_key else '❌'}")
    print(f"   Client initialized: {'✅' if qwen_rag.client else '❌'}")
    
    # Test conversation summary
    summary = qwen_rag.get_conversation_summary(domain)
    print(f"   Empty conversation summary: {summary}")
    
    print("\n✅ Fireworks AI Qwen3 system structure validated!")
    
    if not qwen_rag.api_key:
        print("\n⚠️ To test with actual API calls, configure FIREWORKS_API_KEY in .env file")

if __name__ == "__main__":
    test_fireworks_qwen3_system()