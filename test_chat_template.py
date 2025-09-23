#!/usr/bin/env python3
"""
Test script for Chat Template functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our chat system
from chat import UniversalChatRAG

def test_multi_turn_conversation():
    """Test multi-turn conversation with chat template"""
    print("=" * 60)
    print("Testing Multi-turn Conversation with Chat Template")
    print("=" * 60)
    
    chat_rag = UniversalChatRAG()
    domain = "test-shop.com"
    
    # Mock search function
    def mock_search_function(domain, query, limit=3):
        return [
            {
                'title': 'Test Product Page',
                'snippet': 'We sell high-quality products at great prices.',
                'url': 'https://test-shop.com/products'
            }
        ]
    
    conversations = [
        ("What products do you sell?", "normal"),
        ("What are your prices like?", "normal"),
        ("Do you offer discounts?", "thinking"),
        ("Can you help me find a specific item?", "react"),
        ("Thank you for your help!", "normal")
    ]
    
    print(f"Starting conversation with {domain}")
    print(f"Available providers: {chat_rag.get_available_providers()}")
    print()
    
    for i, (question, mode) in enumerate(conversations, 1):
        print(f"\n--- Turn {i} ({mode.upper()} mode) ---")
        print(f"User: {question}")
        
        # Set response mode
        chat_rag.set_response_mode(mode)
        
        try:
            result = chat_rag.generate_conversational_response(
                domain=domain,
                user_message=question,
                search_function=mock_search_function
            )
            
            print(f"Assistant: {result['response'][:200]}...")
            print(f"Mode used: {result.get('response_mode', 'unknown')}")
            
            # Show thinking process if available
            if result.get('thinking_process'):
                print(f"🤔 Thinking: {result['thinking_process'][:100]}...")
            
            # Show ReAct info if available
            if result.get('react_success') is not None:
                print(f"🔄 ReAct Success: {result['react_success']}")
            
        except Exception as e:
            print(f"❌ Error in turn {i}: {e}")
            return False
    
    # Test conversation history
    print(f"\n--- Conversation History ---")
    history = chat_rag.get_conversation_history(domain)
    print(f"Total messages in history: {len(history)}")
    
    # Test conversation summary
    summary = chat_rag.get_conversation_summary(domain)
    print(f"Conversation summary: {summary}")
    
    return True

def test_different_providers():
    """Test chat template with different providers"""
    print("\n" + "=" * 60)
    print("Testing Chat Template with Different Providers")
    print("=" * 60)
    
    chat_rag = UniversalChatRAG()
    domain = "provider-test.com"
    question = "What is your return policy?"
    
    available_providers = chat_rag.get_available_providers()
    
    for provider in available_providers:
        print(f"\n--- Testing with {provider.upper()} ---")
        
        # Set provider
        chat_rag.set_provider(provider)
        
        # Test conversation with context
        try:
            # First message
            result1 = chat_rag.generate_conversational_response(
                domain=domain,
                user_message="Hello, I'm interested in your products."
            )
            print(f"First response: {result1['response'][:100]}...")
            
            # Second message with context
            result2 = chat_rag.generate_conversational_response(
                domain=domain,
                user_message=question
            )
            print(f"Second response: {result2['response'][:100]}...")
            print(f"Context used: {len(result2.get('conversation_context_used', ''))} chars")
            
        except Exception as e:
            print(f"❌ Error with {provider}: {e}")
    
    return True

def main():
    """Run all tests"""
    print("🧪 Testing Chat Template Implementation")
    print("🔧 Make sure you have API keys set in your .env file")
    
    # Check if API key is available
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Warning: GOOGLE_API_KEY not found. Some tests may fail.")
        print("   Please add API keys to your .env file.")
        print()
    
    tests = [
        ("Multi-turn Conversation", test_multi_turn_conversation),
        ("Different Providers", test_different_providers)
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
        print("🎉 All tests passed! Chat template implementation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()