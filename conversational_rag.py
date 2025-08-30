"""
Conversational RAG System with Multi-turn Support and Query Rewriting
Handles follow-up questions by maintaining conversation context and rewriting queries
"""

import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import hashlib

import google.generativeai as genai
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
        

        print(f"ming-debug, add_turn: conversations: {self.conversations}")

        turn = {
            'timestamp': datetime.utcnow().isoformat(),
            'user': user_message,
            'assistant': assistant_response,
            'sources': sources or []
        }

        print(f"ming-debug, add_turn: conversations: {self.conversations}, turn: {turn}, self.max_turns : {self.max_turns }")
        
        self.conversations[domain].append(turn)
        

        print(f"ming-debug: len_conv: {len(self.conversations[domain])}")

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
        
        print(f"ming-debug: context_parts: {context_parts}")
        return "\n".join(context_parts)
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for domain"""
        if domain in self.conversations:
            del self.conversations[domain]

class QueryRewriter:
    """Rewrites user queries based on conversation context to extract clear intent"""
    
    def __init__(self):
        self.model = self._setup_gemini()
    
    def _setup_gemini(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-1.5-flash')
        return None
    
    def rewrite_query(self, current_query: str, conversation_context: str, domain: str) -> Tuple[str, str]:
        """
        Rewrite query to extract clear user intent from conversation context
        Returns: (rewritten_query, reasoning)
        """
        
        if not self.model:
            return current_query, "No query rewriting (API not configured)"
        
        if not conversation_context.strip():
            return current_query, "No context available, using original query"
        
        rewrite_prompt = f"""You are a query rewriting expert for e-commerce shopping conversations.

Your task is to rewrite the user's current question to be a clear, standalone query that captures their true intent based on the conversation context.

CONVERSATION CONTEXT:
{conversation_context}

CURRENT USER QUERY: {current_query}

WEBSITE DOMAIN: {domain}

Instructions:
1. Carefully analyze the CONVERSATION CONTEXT to understand what products/topics have been discussed
2. Identify any pronouns (it, they, these, those) or vague references in the current query
3. Replace vague references with SPECIFIC product names, categories, or attributes from the conversation context
4. If the user is asking a follow-up question, make sure to reference the exact product or topic from the previous conversation
5. Create a clear, standalone query that would work well for product search on {domain}
6. Focus on the user's shopping intent (product features, comparisons, availability, pricing, etc.)

Examples of good query rewriting:
- Context: "User asked about cashmere sweaters" + Query: "What colors does it come in?" 
  → "What colors does the cashmere sweater come in?"
- Context: "User asked about linen shirts" + Query: "How much do they cost?" 
  → "What are the prices for linen shirts?"
- Context: "User asked about wool jacket, assistant mentioned gray wool jacket" + Query: "Do you have it in size M?" 
  → "Do you have the gray wool jacket in size M?"
- Context: "User comparing polo shirts" + Query: "What about the blue one?" 
  → "What about the blue polo shirt?"

IMPORTANT: Use the conversation context to understand EXACTLY what the user is referring to. Be as specific as possible.

Return your response in this format:
REWRITTEN_QUERY: [your rewritten query here]
REASONING: [brief explanation of what you changed and why, referencing the conversation context]
"""
        
        try:
            response = self.model.generate_content(rewrite_prompt)
            response_text = response.text.strip()
            
            # Parse response
            if "REWRITTEN_QUERY:" in response_text and "REASONING:" in response_text:
                lines = response_text.split('\n')
                rewritten = ""
                reasoning = ""
                
                for line in lines:
                    if line.startswith("REWRITTEN_QUERY:"):
                        rewritten = line.replace("REWRITTEN_QUERY:", "").strip()
                    elif line.startswith("REASONING:"):
                        reasoning = line.replace("REASONING:", "").strip()
                
                if rewritten:
                    return rewritten, reasoning
            
            # Fallback: use full response as rewritten query
            return response_text.split('\n')[0], "Query rewritten using AI"
            
        except Exception as e:
            return current_query, f"Query rewriting failed: {str(e)}"

class ConversationalRAG:
    """Enhanced RAG system with conversation awareness and query rewriting"""
    
    def __init__(self):
        self.model = self._setup_gemini()
        self.memory = ConversationMemory()
        self.query_rewriter = QueryRewriter()
    
    def _setup_gemini(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-1.5-flash')
        return None
    
    def get_website_data(self, domain: str) -> tuple:
        """Load documents and search index for a domain"""
        safe_domain = re.sub(r'[^a-zA-Z0-9._-]', '_', domain)
        
        documents_file = f'data_{safe_domain}_documents.json'
        index_file = f'data_{safe_domain}_index.json'
        
        documents = {}
        search_index = {}
        
        if os.path.exists(documents_file):
            with open(documents_file, 'r', encoding='utf-8') as f:
                docs_list = json.load(f)
                documents = {doc['id']: doc for doc in docs_list}
        
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                search_index = json.load(f)
        
        return documents, search_index
    
    def search_website(self, domain: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search website documents with improved query"""
        documents, search_index = self.get_website_data(domain)
        
        if not search_index:
            return []
        
        query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
        
        results = []
        for doc_id, doc_data in search_index.items():
            keywords = set(doc_data['keywords'])
            
            overlap = len(query_words.intersection(keywords))
            if overlap > 0:
                score = overlap / len(query_words.union(keywords))
                results.append({
                    'doc_id': doc_id,
                    'title': doc_data['title'],
                    'url': doc_data['url'],
                    'section': doc_data['section'],
                    'snippet': doc_data['text'],
                    'score': score
                })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    def format_product_text(self, product: Dict[str, Any]) -> str:
        """Format product data into searchable text"""
        text_parts = []
        
        if product.get('product_name'):
            text_parts.append(f"Product: {product['product_name']}")
        
        if product.get('description'):
            text_parts.append(f"Description: {product['description']}")
        
        if product.get('prices'):
            text_parts.append(f"Prices: {', '.join(product['prices'])}")
        
        if product.get('sizes'):
            text_parts.append(f"Available sizes: {', '.join(product['sizes'])}")
        
        attributes = product.get('attributes', {})
        if attributes.get('colors'):
            text_parts.append(f"Colors: {', '.join(attributes['colors'])}")
        if attributes.get('materials'):
            text_parts.append(f"Materials: {', '.join(attributes['materials'])}")
        if attributes.get('brand'):
            text_parts.append(f"Brand: {attributes['brand']}")
        
        if product.get('bullet_points'):
            text_parts.append("Features:")
            text_parts.extend([f"• {point}" for point in product['bullet_points']])
        
        if product.get('availability'):
            text_parts.append(f"Availability: {product['availability'].replace('_', ' ').title()}")
        
        return " | ".join(text_parts)
    
    def save_website_data(self, domain: str, documents: List[Dict[str, Any]]) -> int:
        """Save documents and create search index for a domain"""
        safe_domain = re.sub(r'[^a-zA-Z0-9._-]', '_', domain)
        
        documents_file = f'data_{safe_domain}_documents.json'
        index_file = f'data_{safe_domain}_index.json'
        
        # Save documents
        with open(documents_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        
        # Create search index
        search_index = {}
        for doc in documents:
            doc_id = doc['id']
            text = doc['text'].lower()
            title = doc['title'].lower()
            
            # Extract keywords
            keywords = set()
            words = re.findall(r'\b[a-z]{3,}\b', f"{title} {text}")
            keywords.update(words)
            
            search_index[doc_id] = {
                'keywords': list(keywords),
                'title': doc['title'],
                'url': doc['url'],
                'section': doc['section'],
                'text': doc['text'][:500]
            }
        
        # Save search index
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(search_index, f, indent=2)
        
        return len(documents)
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        save_to_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Generate response with conversation awareness and query rewriting
        Returns: {
            'response': str,
            'sources': List[Dict],
            'rewritten_query': str,
            'rewrite_reasoning': str,
            'conversation_context_used': str
        }
        """
        
        if not self.model:
            return {
                'response': "Please configure GOOGLE_API_KEY in your .env file to use the AI assistant.",
                'sources': [],
                'rewritten_query': user_message,
                'rewrite_reasoning': "API not configured",
                'conversation_context_used': ""
            }
        
        # Get conversation context
        conversation_context = self.memory.get_recent_context(domain, num_turns=3)

        print(f"ming-debug: conversation_context: {conversation_context}")
        
        # Rewrite query based on context
        rewritten_query, rewrite_reasoning = self.query_rewriter.rewrite_query(
            user_message, conversation_context, domain
        )
        
        # Use rewritten query for retrieval
        search_results = self.search_website(domain, rewritten_query)
        
        # Prepare context for response generation
        context = ""
        product_context = ""
        
        if search_results:
            context = f"\n{domain.upper()} Website Information (based on rewritten query):\n"
            for result in search_results:
                context += f"- {result['title']}: {result['snippet'][:200]}...\n"
                context += f"  Source: {result['url']}\n\n"
                
                # Check if this is product data
                if result['section'] == 'product':
                    try:
                        documents, _ = self.get_website_data(domain)
                        if result['doc_id'] in documents:
                            doc = documents[result['doc_id']]
                            if 'product_data' in doc.get('meta', {}):
                                product_data = doc['meta']['product_data']
                                product_context += f"\n🛍️ Product: {product_data.get('product_name', 'Unknown')}\n"
                                product_context += f"   Prices: {product_data.get('prices', [])}\n"
                                product_context += f"   Sizes: {product_data.get('sizes', [])}\n"
                                product_context += f"   Availability: {product_data.get('availability', 'unknown')}\n"
                                if product_data.get('attributes', {}).get('colors'):
                                    product_context += f"   Colors: {product_data['attributes']['colors']}\n"
                                if product_data.get('attributes', {}).get('materials'):
                                    product_context += f"   Materials: {product_data['attributes']['materials']}\n"
                    except:
                        pass
        else:
            context = f"\nNo specific information found for the rewritten query: '{rewritten_query}'\n"
        
        # Improved Amazon Online Shopping Assistant Prompt
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
4. Include specific details like prices, sizes, colors, materials, and availability when available
5. Reference source URLs when providing specific information
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
- Present recommendations with clear feature highlights
- Provide context for why each recommendation might be a good fit
- Connect recommendations to the customer's stated needs from conversation context

For follow-up questions, examples of good conversational responses:
- "The cashmere sweaters we were just talking about come in..."
- "The [specific product] I mentioned costs..."
- "For the [jacket style] you asked about, here are the available sizes..."

Respond as a knowledgeable conversational shopping assistant for {domain}, maintaining natural conversation flow and using the conversation context to provide relevant, personalized assistance.

Remember to format your response with the streaming guidelines using <text format-type=""> tags and start with "RESPONSE:" for answered questions.


{conversation_context if conversation_context.strip() else "This is the start of a new conversation."}

CURRENT USER QUESTION: {user_message}
REWRITTEN QUERY (used for search): {rewritten_query}
QUERY REWRITE REASONING: {rewrite_reasoning}

RETRIEVED INFORMATION:
{context}
{product_context}
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Save to conversation memory
            if save_to_memory:
                self.memory.add_turn(domain, user_message, response_text, search_results)
            
            print(f"ming-debug: self.memory: {self.memory}")
            
            return {
                'response': response_text,
                'sources': search_results,
                'rewritten_query': rewritten_query,
                'rewrite_reasoning': rewrite_reasoning,
                'conversation_context_used': conversation_context
            }
            
        except Exception as e:
            error_msg = f"I apologize, but I encountered an error generating a response: {str(e)}"
            return {
                'response': error_msg,
                'sources': [],
                'rewritten_query': rewritten_query,
                'rewrite_reasoning': rewrite_reasoning,
                'conversation_context_used': conversation_context
            }
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for domain"""
        self.memory.clear_conversation(domain)
    
    def get_conversation_summary(self, domain: str) -> Dict[str, Any]:
        """Get conversation summary with statistics"""

        print(f"ming-debug, get_conversation_summary: domain: {domain}")


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

# Test the conversational system
def test_conversational_rag():
    """Test multi-turn conversation scenarios"""
    
    print("🧪 Testing Conversational RAG System")
    print("=" * 60)
    
    conv_rag = ConversationalRAG()
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
    
    print("💬 Simulating multi-turn conversation:")
    print("-" * 40)
    
    for i, user_message in enumerate(test_conversations, 1):
        print(f"\n👤 Turn {i}: {user_message}")
        
        result = conv_rag.generate_conversational_response(domain, user_message)
        
        print(f"🤖 Assistant: {result['response'][:200]}...")
        print(f"🔍 Query rewritten to: '{result['rewritten_query']}'")
        print(f"💭 Reasoning: {result['rewrite_reasoning']}")
        print(f"📊 Found {len(result['sources'])} relevant sources")
    
    # Show conversation summary
    summary = conv_rag.get_conversation_summary(domain)
    print(f"\n📈 Conversation Summary:")
    print(f"   Total turns: {summary['total_turns']}")
    print(f"   Recent topics: {summary.get('recent_topics', [])}")
    
    print("\n✅ Conversational RAG test complete!")

if __name__ == "__main__":
    test_conversational_rag()