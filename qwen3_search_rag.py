"""
Qwen3-powered Conversational System with Thinking Mode and Google Search
Uses Qwen3's thinking capabilities for enhanced reasoning in shopping conversations
"""

import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import requests

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

class Qwen3QueryRewriter:
    """Uses Qwen3 with thinking mode to rewrite queries to multiple key phrases"""
    
    def __init__(self):
        self.api_base = os.getenv('QWEN3_API_BASE', 'http://localhost:8000/v1')
        self.api_key = os.getenv('QWEN3_API_KEY', 'dummy')
        self.model_name = os.getenv('QWEN3_MODEL', 'Qwen/Qwen3-32B')
    
    def rewrite_to_keyphrases(self, current_query: str, conversation_context: str, domain: str) -> Tuple[List[str], str, str]:
        """
        Rewrite query to multiple key phrases using Qwen3 thinking mode
        Returns: (list_of_keyphrases, reasoning, thinking_process)
        """
        
        if not conversation_context.strip():
            return [current_query], "No context available, using original query", ""
        
        messages = [
            {
                "role": "system",
                "content": """You are a Google Search query expert for e-commerce shopping conversations. You will use thinking mode to carefully analyze conversation context and generate optimal search phrases.

Your task is to convert the user's current question into multiple effective Google search key phrases that will find the most relevant product information."""
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
            # Call Qwen3 API with thinking mode enabled
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": 0.6,
                    "max_tokens": 1000,
                    "thinking": True  # Enable thinking mode
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract thinking process and final answer
                thinking_content = ""
                final_content = ""
                
                if 'choices' in result and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    message = choice.get('message', {})
                    
                    # Check if thinking process is available
                    if 'thinking' in message:
                        thinking_content = message['thinking']
                    
                    content = message.get('content', '')
                    final_content = content
                    
                    # Parse keyphrases and reasoning from content
                    keyphrases = []
                    reasoning = ""
                    
                    if "KEYPHRASES:" in final_content and "REASONING:" in final_content:
                        lines = final_content.split('\n')
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
                    fallback_phrases = [line.strip() for line in final_content.split('\n') if line.strip() and not line.startswith('REASONING')]
                    return fallback_phrases[:4] if fallback_phrases else [current_query], "Fallback parsing", thinking_content
            
            return [current_query], f"API call failed: {response.status_code}", ""
            
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

class Qwen3SearchRAG:
    """Qwen3-powered conversational system with thinking mode and Google Search"""
    
    def __init__(self):
        self.api_base = os.getenv('QWEN3_API_BASE', 'http://localhost:8000/v1')
        self.api_key = os.getenv('QWEN3_API_KEY', 'dummy')
        self.model_name = os.getenv('QWEN3_MODEL', 'Qwen/Qwen3-32B')
        self.memory = ConversationMemory()
        self.query_rewriter = Qwen3QueryRewriter()
        self.search_provider = GoogleSearchProvider()
    
    def _call_qwen3_api(self, messages: List[Dict], enable_thinking: bool = True) -> Dict[str, Any]:
        """Call Qwen3 API with thinking mode support"""
        
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": 0.6 if enable_thinking else 0.7,
                    "top_p": 0.95 if enable_thinking else 0.8,
                    "max_tokens": 2000,
                    "thinking": enable_thinking
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    message = choice.get('message', {})
                    
                    return {
                        'content': message.get('content', ''),
                        'thinking': message.get('thinking', ''),
                        'success': True
                    }
            
            return {
                'content': f"API Error: {response.status_code}",
                'thinking': "",
                'success': False
            }
            
        except Exception as e:
            return {
                'content': f"Connection Error: {str(e)}",
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
        Generate response using Qwen3 with thinking mode and Google Search
        Returns: {
            'response': str,
            'thinking_process': str,
            'sources': List[Dict],
            'rewritten_keyphrases': List[str],
            'rewrite_reasoning': str,
            'conversation_context_used': str
        }
        """
        
        # Get conversation context
        conversation_context = self.memory.get_recent_context(domain, num_turns=3)
        
        # Rewrite query to multiple key phrases with thinking
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
        
        # Qwen3 Shopping Assistant Prompt with Thinking Mode
        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful, friendly Online Shopping Assistant powered by Qwen3 with thinking capabilities. You help customers discover products for {domain} using real-time Google Search.

## Core Capabilities
- Use thinking mode to carefully analyze customer needs and search evidence
- Understand and respond to shopping inquiries with thoughtful reasoning
- Maintain context throughout conversations for personalized assistance
- Provide accurate information based on Google Search evidence

## [VERY IMPORTANT] Safety Guidelines
- On {domain}-related sensitive topics, respond in an official PR tone
- On politically or culturally sensitive topics, refrain from taking sides
- When asked about financial, legal, or medical guidance, state "I can't provide professional advice..." and ask to consult experts
- Do not include verbatim quotes of more than 10 consecutive words from copyrighted content

## [CRITICAL] Response Format
- Start responses with "RESPONSE:" 
- Use markdown formatting for better readability
- Never include emojis in responses
- Reference source URLs when providing specific information
- Be concise but helpful"""
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
1. THINK through the conversation context to understand what we've been discussing
2. THINK about how the Google Search evidence relates to the user's question
3. If this is a follow-up question with pronouns (it, they, those), use context to understand what specific products are referenced
4. Provide a helpful, accurate response based on the search evidence
5. Reference sources when making specific claims about products
6. Maintain natural conversation flow acknowledging previous discussion when relevant

Please use your thinking mode to carefully analyze this request and provide a thoughtful response."""
            }
        ]
        
        # Call Qwen3 with thinking mode
        api_result = self._call_qwen3_api(messages, enable_thinking=enable_thinking)
        
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
def test_qwen3_system():
    """Test the Qwen3 thinking mode system"""
    
    print("🧠 Testing Qwen3 Thinking Mode System")
    print("=" * 60)
    
    qwen_rag = Qwen3SearchRAG()
    domain = "lucafaloni.com"
    
    # Test conversation scenarios
    test_conversations = [
        "Do you have any cashmere sweaters?",
        "What colors do they come in?", 
        "How much does the gray one cost?",
        "Do you have it in size M?",
    ]
    
    print("💬 Simulating multi-turn conversation with Qwen3 thinking:")
    print("-" * 50)
    
    for i, user_message in enumerate(test_conversations, 1):
        print(f"\n👤 Turn {i}: {user_message}")
        
        result = qwen_rag.generate_conversational_response(domain, user_message)
        
        if result['thinking_process']:
            print(f"🧠 Thinking: {result['thinking_process'][:100]}...")
        
        print(f"🤖 Response: {result['response'][:200]}...")
        print(f"🔍 Key phrases: {result['rewritten_keyphrases']}")
        print(f"📊 Found {len(result['sources'])} Google Search results")
    
    print("\n✅ Qwen3 thinking mode test complete!")

if __name__ == "__main__":
    test_qwen3_system()