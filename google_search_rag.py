"""
Google Search-based Conversational System
Replaces local RAG with Google Search API for real-time product information
"""

import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import hashlib

import google.generativeai as genai
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

class ConversationMemory:
    """Manages conversation history and context"""
    
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.conversations = {}  # domain -> conversation_history
    
    def add_turn(self, domain: str, user_message: str, assistant_response: str, sources: List[Dict] = None):
        """Add a conversation turn"""
        if domain not in self.conversations:
            self.conversations[domain] = []
        
        turn = {
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'assistant': assistant_response,
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

class QueryRewriter:
    """Rewrites user queries to multiple key phrases for Google Search"""
    
    def __init__(self):
        self.model = self._setup_gemini()
    
    def _setup_gemini(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-1.5-flash')
        return None
    
    def rewrite_to_keyphrases(self, current_query: str, conversation_context: str, domain: str) -> Tuple[List[str], str]:
        """
        Rewrite query to multiple key phrases for Google Search
        Returns: (list_of_keyphrases, reasoning)
        """
        
        if not self.model:
            return [current_query], "No query rewriting (API not configured)"
        
        if not conversation_context.strip():
            return [current_query], "No context available, using original query"
        
        rewrite_prompt = f"""You are a Google Search query expert for e-commerce shopping conversations.

Your task is to convert the user's current question into multiple effective Google search key phrases that will find the most relevant product information.

CONVERSATION CONTEXT:
{conversation_context}

CURRENT USER QUERY: {current_query}

WEBSITE DOMAIN: {domain}

Instructions:
1. Analyze the CONVERSATION CONTEXT to understand what products/topics have been discussed
2. Identify any pronouns (it, they, these, those) or vague references in the current query
3. Replace vague references with SPECIFIC product names, categories, or attributes from conversation context
4. Generate 2-4 Google search key phrases that will find relevant product information
5. Each key phrase should be optimized for Google Search (include domain, product specifics, user intent)
6. Focus on the user's shopping intent (product features, comparisons, availability, pricing, etc.)

Examples of good key phrase generation:
- Context: "User asked about cashmere sweaters" + Query: "What colors does it come in?"
  → ["cashmere sweater colors {domain}", "{domain} cashmere sweater available colors"]
- Context: "User asked about linen shirts" + Query: "How much do they cost?"
  → ["linen shirt price {domain}", "{domain} linen shirt cost"]
- Context: "User comparing polo shirts" + Query: "What about the blue one?"
  → ["blue polo shirt {domain}", "{domain} blue polo shirt details"]

IMPORTANT: 
- Include the domain name in search phrases for site-specific results
- Be specific about the product being referenced from conversation context
- Generate 2-4 distinct key phrases that approach the search from different angles
- Each phrase should be 3-8 words long

Return your response in this format:
KEYPHRASES:
- [key phrase 1]
- [key phrase 2]
- [key phrase 3]
- [key phrase 4]

REASONING: [brief explanation of what you changed and why, referencing the conversation context]
"""
        
        try:
            response = self.model.generate_content(rewrite_prompt)
            response_text = response.text.strip()
            
            # Parse response
            keyphrases = []
            reasoning = ""
            
            if "KEYPHRASES:" in response_text and "REASONING:" in response_text:
                lines = response_text.split('\n')
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
                    return keyphrases, reasoning
            
            # Fallback: split response by lines and take non-empty ones
            fallback_phrases = [line.strip() for line in response_text.split('\n') if line.strip() and not line.startswith('REASONING')]
            return fallback_phrases[:4] if fallback_phrases else [current_query], "Fallback key phrase extraction"
            
        except Exception as e:
            return [current_query], f"Query rewriting failed: {str(e)}"

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
        """
        Search Google for keyphrases and return top results
        Returns: List of search results with title, url, snippet
        """
        
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
        
        return all_results[:num_results * 2]  # Return top results

class GoogleSearchRAG:
    """Google Search-based conversational system replacing local RAG"""
    
    def __init__(self):
        self.model = self._setup_gemini()
        self.memory = ConversationMemory()
        self.query_rewriter = QueryRewriter()
        self.search_provider = GoogleSearchProvider()
    
    def _setup_gemini(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-1.5-flash')
        return None
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        save_to_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Generate response using Google Search instead of local RAG
        Returns: {
            'response': str,
            'sources': List[Dict],
            'rewritten_keyphrases': List[str],
            'rewrite_reasoning': str,
            'conversation_context_used': str
        }
        """
        
        if not self.model:
            return {
                'response': "Please configure GOOGLE_API_KEY in your .env file to use the AI assistant.",
                'sources': [],
                'rewritten_keyphrases': [user_message],
                'rewrite_reasoning': "API not configured",
                'conversation_context_used': ""
            }
        
        # Get conversation context
        conversation_context = self.memory.get_recent_context(domain, num_turns=3)
        
        # Rewrite query to multiple key phrases based on context
        rewritten_keyphrases, rewrite_reasoning = self.query_rewriter.rewrite_to_keyphrases(
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
        
        # Amazon Online Shopping Assistant Prompt with Google Search Evidence
        prompt = f"""You are a helpful, friendly Online Shopping Assistant who helps customers discover products that match their needs for {domain}. Your goal is to create a natural, conversational shopping experience while still providing structured, helpful information.

## Core Capabilities
- Understand and respond to a wide range of shopping inquiries
- Adapt your conversation style to match the customer's tone and needs
- Help customers discover products through a mix of questions, suggestions, and recommendations
- Maintain context throughout the conversation to provide relevant assistance

## [VERY IMPORTANT] Safety Guidelines
- On {domain}-related sensitive topics, respond in an official PR tone
- On politically or culturally sensitive topics, refrain from taking sides or provide a balanced response in an official PR tone
- When the question is about financial, legal, or medical guidance, ALWAYS start your response stating "I can't provide professional advice..." and ALWAYS ASK the customer to consult experts
- Do not include verbatim quotes of more than 10 consecutive words from books, song lyrics or music, movies, or articles

## [CRITICAL] Conversation Context Integration
CONVERSATION CONTEXT:
{conversation_context if conversation_context.strip() else "This is the start of a new conversation."}

CURRENT USER QUESTION: {user_message}
SEARCH KEY PHRASES USED: {', '.join(rewritten_keyphrases)}
QUERY REWRITE REASONING: {rewrite_reasoning}

GOOGLE SEARCH EVIDENCE:
{evidence}

## [VERY IMPORTANT] Streaming Guidelines
- Improve response visibility by utilizing markdown style responses that include bolded ("**text**"), numbered list ("1. text"), bullets ("- text") and headers ("## text")
- Use "markdown" format-type if content includes any of bolded, numbered list, bullets or headers
- Use "plaintext" format-type if content does not include any markdown element
- For each response sub-section, wrap the content as following: <text format-type=""> Sub-section content </text>
- Always apply streaming format for the entire response
- For a **responded answer** or **clarifying question**, the response should start with "RESPONSE:" followed by the content wrapped in <text format-type=""> tags
- Never include emojis

## [IMPORTANT] Context-Aware Instructions
1. Use the CONVERSATION CONTEXT above to understand what we've been discussing
2. Answer the user's CURRENT question naturally, referencing previous discussion when relevant
3. If this is a follow-up question (pronouns like "it", "they", "those"), be specific about what products you're referring to
4. Use the GOOGLE SEARCH EVIDENCE to provide accurate, up-to-date information
5. Reference source URLs when providing specific information from the search results
6. Maintain natural conversation flow - acknowledge what we discussed before
7. For follow-up questions, explicitly mention the product/topic being referenced

## Conversational Guidelines
- Use a warm, friendly tone that makes customers feel comfortable and understood
- Personalize your responses based on the customer's stated preferences
- Balance professionalism with approachability
- Use natural transitions between questions and recommendations
- Acknowledge customer concerns and respond empathetically when needed
- Match your language complexity to the customer's
- Avoid duplicate or verbose content. Ensure responses are concise and minimize cognitive load

## Response Approach
When making specific product suggestions:
- Start with a brief educational paragraph about the product category
- Present recommendations with clear feature highlights based on Google Search evidence
- Provide context for why each recommendation might be a good fit
- Connect recommendations to the customer's stated needs from conversation context
- Always reference sources from the Google Search evidence when making claims

For follow-up questions, examples of good conversational responses:
- "The cashmere sweaters we were just talking about, based on the search results, come in..."
- "According to the search results for the [specific product] I mentioned, it costs..."
- "For the [jacket style] you asked about, the search shows these available sizes..."

Respond as a knowledgeable conversational shopping assistant for {domain}, using the Google Search evidence to provide accurate, up-to-date information while maintaining natural conversation flow.

Remember to format your response with the streaming guidelines using <text format-type=""> tags and start with "RESPONSE:" for answered questions.
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Save to conversation memory
            if save_to_memory:
                self.memory.add_turn(domain, user_message, response_text, search_results)
            
            return {
                'response': response_text,
                'sources': search_results,
                'rewritten_keyphrases': rewritten_keyphrases,
                'rewrite_reasoning': rewrite_reasoning,
                'conversation_context_used': conversation_context
            }
            
        except Exception as e:
            error_msg = f"I apologize, but I encountered an error generating a response: {str(e)}"
            return {
                'response': error_msg,
                'sources': [],
                'rewritten_keyphrases': rewritten_keyphrases,
                'rewrite_reasoning': rewrite_reasoning,
                'conversation_context_used': conversation_context
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
            'conversation_active': True
        }

# Test the Google Search conversational system
def test_google_search_rag():
    """Test multi-turn conversation scenarios with Google Search"""
    
    print("🔍 Testing Google Search RAG System")
    print("=" * 60)
    
    search_rag = GoogleSearchRAG()
    domain = "lucafaloni.com"
    
    # Test conversation scenarios
    test_conversations = [
        # Turn 1: Initial question
        "Do you have any cashmere sweaters?",
        
        # Turn 2: Follow-up with pronoun reference
        "What colors do they come in?",
        
        # Turn 3: Further specification
        "How much does the gray one cost?",
        
        # Turn 4: Size inquiry
        "Do you have it in size M?",
    ]
    
    print("💬 Simulating multi-turn conversation with Google Search:")
    print("-" * 40)
    
    for i, user_message in enumerate(test_conversations, 1):
        print(f"\n👤 Turn {i}: {user_message}")
        
        result = search_rag.generate_conversational_response(domain, user_message)
        
        print(f"🤖 Assistant: {result['response'][:200]}...")
        print(f"🔍 Key phrases: {result['rewritten_keyphrases']}")
        print(f"💭 Reasoning: {result['rewrite_reasoning']}")
        print(f"📊 Found {len(result['sources'])} Google Search results")
    
    # Show conversation summary
    summary = search_rag.get_conversation_summary(domain)
    print(f"\n📈 Conversation Summary:")
    print(f"   Total turns: {summary['total_turns']}")
    print(f"   Recent topics: {summary.get('recent_topics', [])}")
    
    print("\n✅ Google Search RAG test complete!")

if __name__ == "__main__":
    test_google_search_rag()