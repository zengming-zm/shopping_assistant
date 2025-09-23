#!/usr/bin/env python3
"""
Test script for Thinking Mode and ReAct Framework functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our chat system
from chat import UniversalChatRAG, SearchTool, ReactAgent, GeminiProvider

def test_thinking_mode():
    """Test thinking mode functionality"""
    print("=" * 50)
    print("Testing Thinking Mode (Chain of Thought)")
    print("=" * 50)
    
    chat_rag = UniversalChatRAG()
    
    # Set to thinking mode
    chat_rag.set_response_mode("thinking")
    
    # Test question
    test_question = "What are the benefits of online shopping?"
    test_domain = "test.com"
    
    print(f"Question: {test_question}")
    print(f"Mode: {chat_rag.get_response_mode()}")
    print("\nGenerating response...")
    
    try:
        result = chat_rag.generate_conversational_response(
            domain=test_domain,
            user_message=test_question
        )
        
        print(f"\nResponse Mode: {result.get('response_mode', 'unknown')}")
        print(f"Provider Used: {result.get('provider_used', 'unknown')}")
        
        if result.get('thinking_process'):
            print(f"\n🤔 Thinking Process:")
            print("-" * 30)
            print(result['thinking_process'])
            print("-" * 30)
        
        print(f"\n✅ Final Answer:")
        print(result['response'])
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_react_mode():
    """Test ReAct framework functionality"""
    print("\n" + "=" * 50)
    print("Testing ReAct Framework")
    print("=" * 50)
    
    chat_rag = UniversalChatRAG()
    
    # Set to react mode
    chat_rag.set_response_mode("react")
    
    # Test question that would benefit from search
    test_question = "Who is the CEO of Apple?"
    test_domain = "apple.com"
    
    print(f"Question: {test_question}")
    print(f"Mode: {chat_rag.get_response_mode()}")
    print("\nGenerating response...")
    
    try:
        # Mock search function for testing
        def mock_search_function(domain, query, limit=3):
            return [
                {
                    'title': 'Apple Leadership',
                    'snippet': 'Tim Cook is the CEO of Apple Inc.',
                    'url': 'https://apple.com/leadership'
                }
            ]
        
        result = chat_rag.generate_conversational_response(
            domain=test_domain,
            user_message=test_question,
            search_function=mock_search_function
        )
        
        print(f"\nResponse Mode: {result.get('response_mode', 'unknown')}")
        print(f"Provider Used: {result.get('provider_used', 'unknown')}")
        print(f"ReAct Success: {'✅' if result.get('react_success') else '❌'}")
        print(f"Total Turns: {result.get('total_react_turns', 0)}")
        
        if result.get('react_turns'):
            print(f"\n🔄 ReAct Process:")
            for turn in result['react_turns'][:2]:  # Show first 2 turns
                print(f"\nTurn {turn['turn']}:")
                print(f"Model Output: {turn['model_output'][:200]}...")
                if 'observation' in turn:
                    print(f"Observation: {turn['observation']}")
        
        print(f"\n✅ Final Answer:")
        print(result['response'])
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_normal_mode():
    """Test normal mode still works"""
    print("\n" + "=" * 50)
    print("Testing Normal Mode")
    print("=" * 50)
    
    chat_rag = UniversalChatRAG()
    
    # Set to normal mode
    chat_rag.set_response_mode("normal")
    
    test_question = "What is e-commerce?"
    test_domain = "test.com"
    
    print(f"Question: {test_question}")
    print(f"Mode: {chat_rag.get_response_mode()}")
    print("\nGenerating response...")
    
    try:
        result = chat_rag.generate_conversational_response(
            domain=test_domain,
            user_message=test_question
        )
        
        print(f"\nResponse Mode: {result.get('response_mode', 'unknown')}")
        print(f"Provider Used: {result.get('provider_used', 'unknown')}")
        print(f"\n✅ Response:")
        print(result['response'])
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Thinking Mode and ReAct Framework Implementation")
    print("🔧 Make sure you have GOOGLE_API_KEY set in your .env file")
    print()
    
    # Check if API key is available
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Warning: GOOGLE_API_KEY not found. Tests may fail.")
        print("   Please add GOOGLE_API_KEY to your .env file.")
        print()
    
    tests = [
        ("Normal Mode", test_normal_mode),
        ("Thinking Mode", test_thinking_mode),
        ("ReAct Mode", test_react_mode)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Implementation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()