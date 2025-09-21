"""
Chat Module for Universal ShopTalk
Supports multi-turn conversations with multiple AI APIs (Gemini, Claude, GPT)
"""

import os
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import google.generativeai as genai
import openai
import anthropic
from dotenv import load_dotenv

load_dotenv()

class ConversationManager:
    """Manages conversation history and context"""
    
    def __init__(self):
        self.conversations = {}
        self.max_history_length = 10  # Maximum number of turns to keep in memory
        self.context_window = 4000    # Maximum characters for context
    
    def add_message(self, domain: str, role: str, content: str):
        """Add a message to the conversation history"""
        if domain not in self.conversations:
            self.conversations[domain] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.conversations[domain].append(message)
        
        # Keep only recent messages to prevent memory overflow
        if len(self.conversations[domain]) > self.max_history_length * 2:
            self.conversations[domain] = self.conversations[domain][-self.max_history_length * 2:]
    
    def get_conversation_history(self, domain: str) -> List[Dict[str, Any]]:
        """Get conversation history for a domain"""
        return self.conversations.get(domain, [])
    
    def get_context_string(self, domain: str, exclude_last: bool = False) -> str:
        """Get conversation context as formatted string"""
        history = self.get_conversation_history(domain)
        if exclude_last and len(history) > 0:
            history = history[:-1]
        
        context_parts = []
        for msg in history[-6:]:  # Last 3 exchanges (6 messages)
            role_label = "Customer" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg['content']}")
        
        context = "\n".join(context_parts)
        
        # Truncate if too long
        if len(context) > self.context_window:
            context = context[-self.context_window:]
            # Try to start from a complete message
            if "\n" in context:
                context = context[context.find("\n") + 1:]
        
        return context
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for a domain"""
        if domain in self.conversations:
            del self.conversations[domain]
    
    def get_conversation_summary(self, domain: str) -> Dict[str, Any]:
        """Get summary of conversation"""
        history = self.get_conversation_history(domain)
        user_messages = [msg for msg in history if msg["role"] == "user"]
        assistant_messages = [msg for msg in history if msg["role"] == "assistant"]
        
        return {
            "total_turns": len(user_messages),
            "total_messages": len(history),
            "last_interaction": history[-1]["timestamp"] if history else None
        }

class AIProvider:
    """Base class for AI providers"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response from AI model"""
        raise NotImplementedError
    
    def check_availability(self) -> bool:
        """Check if the AI provider is available"""
        return self.is_available

class GeminiProvider(AIProvider):
    """Google Gemini AI Provider"""
    
    def __init__(self):
        super().__init__("Gemini")
        self.model = None
        self._setup()
    
    def _setup(self):
        """Setup Gemini API"""
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.is_available = True
            except Exception as e:
                print(f"Failed to setup Gemini: {e}")
                self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using Gemini"""
        if not self.is_available or not self.model:
            return "Gemini is not available. Please check your GOOGLE_API_KEY."
        
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Error generating response with Gemini: {str(e)}"

class ClaudeProvider(AIProvider):
    """Anthropic Claude AI Provider"""
    
    def __init__(self):
        super().__init__("Claude")
        self.client = None
        self._setup()
    
    def _setup(self):
        """Setup Claude API"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.is_available = True
            except Exception as e:
                print(f"Failed to setup Claude: {e}")
                self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using Claude"""
        if not self.is_available or not self.client:
            return "Claude is not available. Please check your ANTHROPIC_API_KEY."
        
        try:
            messages = []
            if context:
                messages.append({"role": "user", "content": context})
                messages.append({"role": "assistant", "content": "I understand the conversation context."})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return f"Error generating response with Claude: {str(e)}"

class GPTProvider(AIProvider):
    """OpenAI GPT AI Provider"""
    
    def __init__(self):
        super().__init__("GPT")
        self.client = None
        self._setup()
    
    def _setup(self):
        """Setup OpenAI API"""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                self.client = openai.OpenAI(api_key=api_key)
                self.is_available = True
            except Exception as e:
                print(f"Failed to setup GPT: {e}")
                self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using GPT"""
        if not self.is_available or not self.client:
            return "GPT is not available. Please check your OPENAI_API_KEY."
        
        try:
            messages = []
            if context:
                messages.append({"role": "system", "content": f"Previous conversation context:\n{context}"})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response with GPT: {str(e)}"

class UniversalChatRAG:
    """Universal Chat RAG system with multiple AI provider support"""
    
    def __init__(self):
        self.conversation_manager = ConversationManager()
        self.providers = {
            "gemini": GeminiProvider(),
            "claude": ClaudeProvider(),
            "gpt": GPTProvider()
        }
        self.default_provider = "gemini"
        
        # Find the first available provider as default
        for name, provider in self.providers.items():
            if provider.is_available:
                self.default_provider = name
                break
    
    def get_available_providers(self) -> List[str]:
        """Get list of available AI providers"""
        return [name for name, provider in self.providers.items() if provider.is_available]
    
    def set_provider(self, provider_name: str) -> bool:
        """Set the active AI provider"""
        if provider_name in self.providers and self.providers[provider_name].is_available:
            self.default_provider = provider_name
            return True
        return False
    
    def search_website_content(self, domain: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search website content (placeholder for integration with existing search)"""
        # This would integrate with the existing search functionality
        # For now, return empty list as placeholder
        return []
    
    def format_search_context(self, search_results: List[Dict[str, Any]], domain: str) -> str:
        """Format search results into context string"""
        if not search_results:
            return f"No specific information found for {domain}. Please provide general assistance."
        
        context = f"\n{domain.upper()} Website Information:\n"
        for result in search_results:
            context += f"- {result.get('title', 'Unknown')}: {result.get('snippet', '')[:200]}...\n"
            if 'url' in result:
                context += f"  Source: {result['url']}\n\n"
        
        return context
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        provider_name: Optional[str] = None,
        search_function: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Generate a conversational response with context"""
        
        print(f"ming-debug: conversation_manager.conversations: {self.conversation_manager.conversations}")

        # Use specified provider or default
        provider_name = provider_name or self.default_provider
        provider = self.providers.get(provider_name)

        print(f"ming-debug: provider: {provider}")
        
        if not provider or not provider.is_available:
            return {
                'response': f"AI provider '{provider_name}' is not available.",
                'provider_used': provider_name,
                'conversation_context_used': "",
                'sources': [],
                'rewritten_keyphrases': [user_message],
                'rewrite_reasoning': "Provider not available"
            }
        
        # Get conversation context
        conversation_context = self.conversation_manager.get_context_string(domain, exclude_last=True)
        print(f"ming-debug: conversation_context: {conversation_context}")
        
        # Search for relevant content
        search_results = []
        if search_function:
            try:
                search_results = search_function(domain, user_message, limit=3)
            except Exception as e:
                print(f"Search function error: {e}")
        
        print(f"ming-debug: search_results: {search_results}")
        # Format website context
        website_context = self.format_search_context(search_results, domain)
        
        # Build the prompt
        prompt = f"""You are ShopTalk, a universal shopping assistant that helps customers with questions about any website.

Current website: {domain}
AI Provider: {provider.name}
Customer question: {user_message}

{website_context}

Previous conversation context:
{conversation_context}

Instructions:
- Use the provided website information to answer questions about products, services, and policies
- Consider the conversation history to provide contextual responses
- For product questions, include specific details like prices, sizes, colors, materials, and availability when available
- If you have specific information from the website, reference it with source URLs
- If you don't have specific information, acknowledge this and provide helpful general guidance
- Maintain a helpful, professional tone appropriate for customer service
- Focus on being accurate and citing sources when available
- For product recommendations, consider the customer's needs and highlight relevant features
- Keep responses concise but informative

Respond as a knowledgeable shopping assistant for {domain}.
"""
        
        print(f"ming-debug: prompt: {prompt}")

        # Generate response
        response = provider.generate_response(prompt, conversation_context)
        
        # Add to conversation history
        self.conversation_manager.add_message(domain, "user", user_message)
        self.conversation_manager.add_message(domain, "assistant", response)

        print(f"ming-debug: after Add to conversation history - domain: {domain}, "
              f"user_message: {user_message}, response: {response}"
              f"conversation_manager.conversations: {self.conversation_manager.conversations}")
        
        return {
            'response': response,
            'provider_used': provider_name,
            'conversation_context_used': conversation_context,
            'sources': search_results,
            'rewritten_keyphrases': [user_message],  # Simplified for now
            'rewrite_reasoning': "Using original query"
        }
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for a domain"""
        self.conversation_manager.clear_conversation(domain)
    
    def get_conversation_summary(self, domain: str) -> Dict[str, Any]:
        """Get conversation summary for a domain"""
        return self.conversation_manager.get_conversation_summary(domain)
    
    def get_conversation_history(self, domain: str) -> List[Dict[str, Any]]:
        """Get full conversation history for a domain"""
        return self.conversation_manager.get_conversation_history(domain)

# Convenience function for easy integration
def create_chat_system() -> UniversalChatRAG:
    """Create and return a new chat system instance"""
    return UniversalChatRAG()