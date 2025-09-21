"""
Abstract base classes for modular shopping assistant architecture
Supports multiple implementations: Direct API calls, LangGraph multi-agent, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

class ConversationMemory:
    """Shared conversation memory implementation"""
    
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.conversations = {}  # domain -> conversation_history
    
    def add_turn(self, domain: str, user_message: str, assistant_response: str, 
                 thinking_process: str = "", sources: List[Dict] = None, metadata: Dict = None):
        """Add a conversation turn with optional thinking process and metadata"""
        if domain not in self.conversations:
            self.conversations[domain] = []
        
        turn = {
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'assistant': assistant_response,
            'thinking': thinking_process,
            'sources': sources or [],
            'metadata': metadata or {}
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
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for domain"""
        if domain in self.conversations:
            del self.conversations[domain]

class BaseQueryRewriter(ABC):
    """Abstract base class for query rewriting implementations"""
    
    @abstractmethod
    def rewrite_to_keyphrases(self, current_query: str, conversation_context: str, domain: str) -> Tuple[List[str], str, str]:
        """
        Rewrite query to multiple key phrases for search
        Returns: (list_of_keyphrases, reasoning, thinking_process)
        """
        pass

class BaseSearchProvider(ABC):
    """Abstract base class for search providers"""
    
    @abstractmethod
    def search(self, keyphrases: List[str], num_results: int = 2) -> List[Dict[str, Any]]:
        """
        Search for keyphrases and return results
        Returns: List of search results with title, url, snippet, source
        """
        pass

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate_response(self, messages: List[Dict], enable_thinking: bool = True) -> Dict[str, Any]:
        """
        Generate response from LLM
        Returns: {'content': str, 'thinking': str, 'success': bool}
        """
        pass

class BaseShoppingAssistant(ABC):
    """Abstract base class for shopping assistant implementations"""
    
    def __init__(self):
        self.memory = ConversationMemory()
    
    @abstractmethod
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        save_to_memory: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate conversational response for shopping queries
        Returns: {
            'response': str,
            'thinking_process': str,
            'sources': List[Dict],
            'rewritten_keyphrases': List[str],
            'rewrite_reasoning': str,
            'conversation_context_used': str,
            'metadata': Dict
        }
        """
        pass
    
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
                'topics_discussed': [],
                'implementation': self.__class__.__name__
            }
        
        return {
            'total_turns': len(history),
            'last_interaction': history[-1]['timestamp'],
            'recent_topics': [turn['user'][:50] + "..." for turn in history[-3:]],
            'conversation_active': True,
            'has_thinking': any(turn.get('thinking') for turn in history),
            'implementation': self.__class__.__name__
        }

class ShoppingAssistantRegistry:
    """Registry for different shopping assistant implementations"""
    
    def __init__(self):
        self._implementations = {}
    
    def register(self, name: str, implementation_class: type, description: str = ""):
        """Register a shopping assistant implementation"""
        self._implementations[name] = {
            'class': implementation_class,
            'description': description
        }
    
    def get_implementation(self, name: str) -> Optional[type]:
        """Get implementation class by name"""
        if name in self._implementations:
            return self._implementations[name]['class']
        return None
    
    def list_implementations(self) -> Dict[str, str]:
        """List all registered implementations with descriptions"""
        return {name: impl['description'] for name, impl in self._implementations.items()}
    
    def create_instance(self, name: str) -> Optional[BaseShoppingAssistant]:
        """Create instance of implementation by name"""
        impl_class = self.get_implementation(name)
        if impl_class:
            return impl_class()
        return None

# Global registry instance
assistant_registry = ShoppingAssistantRegistry()