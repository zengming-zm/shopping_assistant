#!/usr/bin/env python3
"""
Test script for persistent conversation history across Streamlit session
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our chat system
from chat import UniversalChatRAG, GeminiProvider

def test_persistent_gemini_sessions():
    """Test that Gemini chat sessions persist across multiple interactions"""
    print("=" * 60)
    print("Testing Persistent Gemini Chat Sessions")
    print("=" * 60)
    
    # Create chat system
    chat_rag = UniversalChatRAG()
    chat_rag.set_provider("gemini")
    
    domain = "test-store.com"
    
    # Mock search function
    def mock_search_function(domain, query, limit=3):
        return [
            {
                'title': 'Test Store Products',
                'snippet': 'We offer great products at competitive prices.',
                'url': 'https://test-store.com/products'
            }
        ]
    
    print(f"Testing conversation persistence with {domain}")
    print(f"Provider: {chat_rag.default_provider}")
    
    # First conversation turn
    print("\n--- First Turn ---")
    result1 = chat_rag.generate_conversational_response(
        domain=domain,
        user_message="Hi, I'm looking for a laptop under $1000",
        search_function=mock_search_function
    )
    print(f"User: Hi, I'm looking for a laptop under $1000")
    print(f"Assistant: {result1['response'][:100]}...")
    
    # Second conversation turn
    print("\n--- Second Turn ---")
    result2 = chat_rag.generate_conversational_response(
        domain=domain,
        user_message="What's your return policy?",
        search_function=mock_search_function
    )
    print(f"User: What's your return policy?")
    print(f"Assistant: {result2['response'][:100]}...")
    print(f"Context used: {len(result2.get('conversation_context_used', ''))} chars")
    
    # Third conversation turn - should remember laptop context
    print("\n--- Third Turn ---")
    result3 = chat_rag.generate_conversational_response(
        domain=domain,
        user_message="Can you recommend one for gaming?",
        search_function=mock_search_function
    )
    print(f"User: Can you recommend one for gaming?")
    print(f"Assistant: {result3['response'][:100]}...")
    print(f"Context used: {len(result3.get('conversation_context_used', ''))} chars")
    
    # Check conversation history
    history = chat_rag.get_conversation_history(domain)
    print(f"\n✅ Total messages in history: {len(history)}")
    
    # Test that context references previous messages
    laptop_mentioned = any("laptop" in result3['response'].lower() for _ in [1])
    context_has_history = len(result3.get('conversation_context_used', '')) > 0
    
    print(f"Context contains history: {'✅' if context_has_history else '❌'}")
    print(f"Response references context: {'✅' if laptop_mentioned else '❌'}")
    
    return context_has_history and laptop_mentioned

def test_session_persistence_simulation():
    """Simulate multiple Streamlit sessions to test persistence"""
    print("\n" + "=" * 60)
    print("Testing Session Persistence Simulation")
    print("=" * 60)
    
    domain = "electronics.com"
    
    # Session 1: Create initial conversation
    print("\n--- Simulated Session 1 ---")
    chat_rag_1 = UniversalChatRAG()
    chat_rag_1.set_provider("gemini")
    
    result1 = chat_rag_1.generate_conversational_response(
        domain=domain,
        user_message="I need help choosing a smartphone"
    )
    print(f"Session 1 - User: I need help choosing a smartphone")
    print(f"Session 1 - Assistant: {result1['response'][:80]}...")
    
    # Get the Gemini provider instance
    gemini_provider = chat_rag_1.providers.get("gemini")
    print(f"Chat sessions in Session 1: {len(gemini_provider.chat_sessions) if gemini_provider else 0}")
    
    # Session 2: Continue conversation (simulate Streamlit rerun)
    print("\n--- Simulated Session 2 (Streamlit Rerun) ---")
    chat_rag_2 = UniversalChatRAG()
    chat_rag_2.set_provider("gemini")
    
    # In real Streamlit, we would preserve the chat_rag instance in session_state
    # For testing, we'll manually copy the chat sessions
    if gemini_provider and hasattr(gemini_provider, 'chat_sessions'):
        chat_rag_2.providers["gemini"].chat_sessions = gemini_provider.chat_sessions.copy()
        
        # Also copy conversation history
        chat_rag_2.conversation_manager.conversations = chat_rag_1.conversation_manager.conversations.copy()
    
    result2 = chat_rag_2.generate_conversational_response(
        domain=domain,
        user_message="What's the best camera quality?"
    )
    print(f"Session 2 - User: What's the best camera quality?")
    print(f"Session 2 - Assistant: {result2['response'][:80]}...")
    print(f"Context used in Session 2: {len(result2.get('conversation_context_used', ''))} chars")
    
    # Check if context was preserved
    has_context = len(result2.get('conversation_context_used', '')) > 0
    print(f"Context preserved across sessions: {'✅' if has_context else '❌'}")
    
    return has_context

def test_multiple_domains():
    """Test that different domains have separate conversation histories"""
    print("\n" + "=" * 60)
    print("Testing Multiple Domain Separation")
    print("=" * 60)
    
    chat_rag = UniversalChatRAG()
    chat_rag.set_provider("gemini")
    
    # Domain 1 conversation
    domain1 = "bookstore.com"
    result1 = chat_rag.generate_conversational_response(
        domain=domain1,
        user_message="I'm looking for science fiction books"
    )
    print(f"Domain 1 ({domain1}): Looking for sci-fi books")
    print(f"Response: {result1['response'][:60]}...")
    
    # Domain 2 conversation
    domain2 = "petstore.com"
    result2 = chat_rag.generate_conversational_response(
        domain=domain2,
        user_message="I need food for my cat"
    )
    print(f"Domain 2 ({domain2}): Need cat food")
    print(f"Response: {result2['response'][:60]}...")
    
    # Continue Domain 1 conversation
    result3 = chat_rag.generate_conversational_response(
        domain=domain1,
        user_message="Any recommendations from Asimov?"
    )
    print(f"Domain 1 follow-up: Any Asimov recommendations?")
    print(f"Response: {result3['response'][:60]}...")
    print(f"Context: {len(result3.get('conversation_context_used', ''))} chars")
    
    # Check conversation histories
    history1 = chat_rag.get_conversation_history(domain1)
    history2 = chat_rag.get_conversation_history(domain2)
    
    print(f"\nDomain 1 history: {len(history1)} messages")
    print(f"Domain 2 history: {len(history2)} messages")
    
    # Check Gemini chat sessions
    gemini_provider = chat_rag.providers.get("gemini")
    if gemini_provider:
        session_count = len(gemini_provider.chat_sessions)
        print(f"Total Gemini chat sessions: {session_count}")
    
    return len(history1) == 4 and len(history2) == 2  # 2 turns each domain

def main():
    """Run all tests"""
    print("🧪 Testing Persistent Conversation History")
    print("🔧 Make sure you have GOOGLE_API_KEY set in your .env file")
    
    # Check if API key is available
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Error: GOOGLE_API_KEY not found.")
        print("   Please add GOOGLE_API_KEY to your .env file.")
        return
    
    tests = [
        ("Persistent Gemini Sessions", test_persistent_gemini_sessions),
        ("Session Persistence Simulation", test_session_persistence_simulation),
        ("Multiple Domain Separation", test_multiple_domains)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔍 Running {test_name} test...")
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Persistent conversation history is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()