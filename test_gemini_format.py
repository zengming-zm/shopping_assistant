#!/usr/bin/env python3
"""
Test script for Gemini API format with system_instruction, history, and prompt
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our chat system
from chat import UniversalChatRAG, GeminiProvider

def test_gemini_api_format():
    """Test the new Gemini API format"""
    print("=" * 60)
    print("Testing Gemini API Format")
    print("=" * 60)
    
    # Check if Gemini is available
    provider = GeminiProvider()
    if not provider.is_available:
        print("❌ Gemini provider not available. Check GOOGLE_API_KEY.")
        return False
    
    print("✅ Gemini provider available")
    
    # Test direct API format
    system_prompt = """You are ShopTalk, a helpful shopping assistant.
    
Instructions:
- Be helpful and professional
- Keep responses concise
- Use the conversation history for context"""
    
    chat_history = [
        {"role": "user", "content": "Hello, I'm looking for a laptop"},
        {"role": "assistant", "content": "Hello! I'd be happy to help you find a laptop. What's your budget and intended use?"}
    ]
    
    current_question = "I need something for gaming under $1500"
    
    print(f"System Prompt: {system_prompt[:50]}...")
    print(f"Chat History: {len(chat_history)} messages")
    print(f"Current Question: {current_question}")
    print("\nGenerating response...")
    
    try:
        response = provider.generate_response_with_template(
            system_prompt, chat_history, current_question
        )
        
        print(f"\n✅ Response Generated Successfully:")
        print(f"Response: {response[:200]}...")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_full_chat_system():
    """Test the full chat system with new format"""
    print("\n" + "=" * 60)
    print("Testing Full Chat System with New Format")
    print("=" * 60)
    
    chat_rag = UniversalChatRAG()
    
    # Make sure we're using Gemini
    chat_rag.set_provider("gemini")
    domain = "tech-store.com"
    
    # Mock search function
    def mock_search_function(domain, query, limit=3):
        return [
            {
                'title': 'Gaming Laptops',
                'snippet': 'High-performance gaming laptops starting at $1200',
                'url': 'https://tech-store.com/gaming-laptops'
            }
        ]
    
    conversations = [
        "Hi, I'm looking for a gaming laptop",
        "What's your budget range?",
        "Around $1500. What do you recommend?",
        "Do you have any with RTX graphics cards?"
    ]
    
    print(f"Testing multi-turn conversation with {domain}")
    print(f"Using provider: {chat_rag.default_provider}")
    
    for i, question in enumerate(conversations, 1):
        print(f"\n--- Turn {i} ---")
        print(f"User: {question}")
        
        try:
            result = chat_rag.generate_conversational_response(
                domain=domain,
                user_message=question,
                search_function=mock_search_function
            )
            
            print(f"Assistant: {result['response'][:150]}...")
            print(f"Context used: {len(result.get('conversation_context_used', ''))} chars")
            
        except Exception as e:
            print(f"❌ Error in turn {i}: {e}")
            return False
    
    # Test conversation history
    history = chat_rag.get_conversation_history(domain)
    print(f"\n✅ Conversation completed successfully")
    print(f"Total messages in history: {len(history)}")
    
    return True

def test_react_with_new_format():
    """Test ReAct framework with new API format"""
    print("\n" + "=" * 60)
    print("Testing ReAct Framework with New Format")
    print("=" * 60)
    
    chat_rag = UniversalChatRAG()
    chat_rag.set_provider("gemini")
    chat_rag.set_response_mode("react")
    
    domain = "electronics.com"
    question = "What's the best gaming laptop under $2000?"
    
    def mock_search_function(domain, query, limit=3):
        return [
            {
                'title': 'Best Gaming Laptops 2024',
                'snippet': 'Top gaming laptops under $2000: ASUS ROG, MSI Gaming, Dell G15',
                'url': 'https://electronics.com/gaming-laptops-2024'
            }
        ]
    
    print(f"Question: {question}")
    print(f"Mode: {chat_rag.get_response_mode()}")
    print("\nGenerating ReAct response...")
    
    try:
        result = chat_rag.generate_conversational_response(
            domain=domain,
            user_message=question,
            search_function=mock_search_function
        )
        
        print(f"\n✅ ReAct Response Generated:")
        print(f"Success: {'✅' if result.get('react_success') else '❌'}")
        print(f"Total Turns: {result.get('total_react_turns', 0)}")
        print(f"Final Answer: {result['response'][:200]}...")
        
        # Show ReAct process
        if result.get('react_turns'):
            print(f"\n🔄 ReAct Process Summary:")
            for turn in result['react_turns'][:2]:  # Show first 2 turns
                print(f"Turn {turn['turn']}: {turn['model_output'][:100]}...")
                if 'observation' in turn:
                    print(f"  → Observation: {turn['observation'][:80]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing New Gemini API Format Implementation")
    print("🔧 Make sure you have GOOGLE_API_KEY set in your .env file")
    
    # Check if API key is available
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Error: GOOGLE_API_KEY not found.")
        print("   Please add GOOGLE_API_KEY to your .env file.")
        return
    
    tests = [
        ("Gemini API Format", test_gemini_api_format),
        ("Full Chat System", test_full_chat_system),
        ("ReAct with New Format", test_react_with_new_format)
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
        print("🎉 All tests passed! New Gemini API format is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()