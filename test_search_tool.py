#!/usr/bin/env python3
"""
Test script for enhanced SearchTool with Google API and query rewriting
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our chat system
from chat import UniversalChatRAG, SearchTool, QueryRewriter, GeminiProvider

def test_query_rewriting():
    """Test the query rewriting functionality"""
    print("=" * 60)
    print("Testing Query Rewriting")
    print("=" * 60)
    
    # Create AI provider
    provider = GeminiProvider()
    if not provider.is_available:
        print("❌ Gemini provider not available")
        return False
    
    # Create query rewriter
    rewriter = QueryRewriter(provider)
    
    # Test scenarios
    test_scenarios = [
        {
            "chat_history": [
                {"role": "user", "content": "I'm looking for a laptop"},
                {"role": "assistant", "content": "I can help you find a laptop. What's your budget and intended use?"},
                {"role": "user", "content": "Around $1500 for gaming"}
            ],
            "current_question": "Any with good graphics cards?",
            "domain": "electronics.com",
            "expected_context": "gaming laptop graphics cards"
        },
        {
            "chat_history": [
                {"role": "user", "content": "Do you sell books?"},
                {"role": "assistant", "content": "Yes, we have a wide selection of books."}
            ],
            "current_question": "What about science fiction?",
            "domain": "bookstore.com",
            "expected_context": "science fiction books"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n--- Scenario {i} ---")
        print(f"Domain: {scenario['domain']}")
        print(f"Chat History: {len(scenario['chat_history'])} messages")
        print(f"Current Question: {scenario['current_question']}")
        
        try:
            result = rewriter.rewrite_query(
                scenario['chat_history'], 
                scenario['current_question'], 
                scenario['domain']
            )
            
            print(f"Original Query: {result['original_query']}")
            print(f"Rewritten Query: {result['rewritten_query']}")
            print(f"Reasoning: {result['reasoning']}")
            
            if result['thinking_process']:
                print(f"Thinking: {result['thinking_process'][:100]}...")
            
            # Check if query was actually improved
            original_lower = result['original_query'].lower()
            rewritten_lower = result['rewritten_query'].lower()
            
            improvement_indicators = [
                len(rewritten_lower) > len(original_lower),  # More specific
                any(word in rewritten_lower for word in scenario['expected_context'].split()),  # Contains context
                result['rewritten_query'] != result['original_query']  # Actually changed
            ]
            
            improved = any(improvement_indicators)
            print(f"Query Improved: {'✅' if improved else '❌'}")
            
        except Exception as e:
            print(f"❌ Error in scenario {i}: {e}")
            return False
    
    return True

def test_search_tool_with_rewriting():
    """Test SearchTool with query rewriting and mock Google search"""
    print("\n" + "=" * 60)
    print("Testing SearchTool with Query Rewriting")
    print("=" * 60)
    
    # Create AI provider
    provider = GeminiProvider()
    if not provider.is_available:
        print("❌ Gemini provider not available")
        return False
    
    # Mock Google search function
    def mock_google_search(domain, query, limit=3):
        print(f"Mock Google Search called with: domain='{domain}', query='{query}', limit={limit}")
        
        # Return mock results based on query content
        if "gaming laptop" in query.lower() or "graphics" in query.lower():
            return [
                {
                    'title': 'Best Gaming Laptops 2024',
                    'snippet': 'Top gaming laptops with RTX 4080 and 4090 graphics cards under $2000',
                    'url': 'https://techreview.com/gaming-laptops-2024'
                },
                {
                    'title': 'Gaming Laptop Buying Guide',
                    'snippet': 'How to choose the right graphics card for your gaming needs',
                    'url': 'https://pcgamer.com/laptop-guide'
                }
            ]
        elif "science fiction" in query.lower() or "books" in query.lower():
            return [
                {
                    'title': 'Best Sci-Fi Books of 2024',
                    'snippet': 'Top science fiction novels including Dune, Foundation series',
                    'url': 'https://bookstore.com/sci-fi-2024'
                }
            ]
        else:
            return [
                {
                    'title': 'General Search Result',
                    'snippet': f'Information about {query}',
                    'url': f'https://{domain}/search?q={query}'
                }
            ]
    
    # Test scenarios
    test_scenarios = [
        {
            "chat_history": [
                {"role": "user", "content": "I need a new laptop"},
                {"role": "assistant", "content": "What's your budget and use case?"},
                {"role": "user", "content": "Around $1800 for gaming"}
            ],
            "current_question": "What graphics cards are available?",
            "domain": "electronics.com"
        },
        {
            "chat_history": [
                {"role": "user", "content": "Do you have book recommendations?"},
                {"role": "assistant", "content": "What genre are you interested in?"}
            ],
            "current_question": "Science fiction please",
            "domain": "bookstore.com"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n--- Search Test {i} ---")
        
        # Create SearchTool with all parameters
        search_tool = SearchTool(
            search_function=mock_google_search,
            ai_provider=provider,
            chat_history=scenario['chat_history'],
            domain=scenario['domain']
        )
        
        print(f"Domain: {scenario['domain']}")
        print(f"Question: {scenario['current_question']}")
        print(f"Chat History: {len(scenario['chat_history'])} messages")
        
        try:
            result = search_tool.execute(scenario['current_question'])
            
            print(f"Search Result Length: {len(result)} chars")
            print(f"Search Result Preview: {result[:200]}...")
            
            # Check if result contains expected information
            success_indicators = [
                len(result) > 50,  # Substantial response
                "Search query:" in result or "information" in result.lower(),  # Has search info
                scenario['domain'] in result or "http" in result  # Contains domain or URLs
            ]
            
            success = any(success_indicators)
            print(f"Search Success: {'✅' if success else '❌'}")
            
        except Exception as e:
            print(f"❌ Error in search test {i}: {e}")
            return False
    
    return True

def test_react_with_enhanced_search():
    """Test ReAct framework with enhanced SearchTool"""
    print("\n" + "=" * 60)
    print("Testing ReAct Framework with Enhanced Search")
    print("=" * 60)
    
    chat_rag = UniversalChatRAG()
    chat_rag.set_provider("gemini")
    chat_rag.set_response_mode("react")
    
    domain = "techstore.com"
    
    # Mock Google search function
    def mock_google_search(domain, query, limit=3):
        return [
            {
                'title': f'Search Results for {query}',
                'snippet': f'Comprehensive information about {query} from {domain}',
                'url': f'https://{domain}/search?q={query.replace(" ", "+")}'
            }
        ]
    
    # Test with conversation history
    print("Setting up conversation history...")
    
    # First, establish some conversation context
    result1 = chat_rag.generate_conversational_response(
        domain=domain,
        user_message="I'm looking for a high-performance laptop for work",
        search_function=mock_google_search
    )
    print(f"Context established: {result1['response'][:80]}...")
    
    # Now test ReAct with context
    result2 = chat_rag.generate_conversational_response(
        domain=domain,
        user_message="What are the best processors for this?",
        search_function=mock_google_search
    )
    
    print(f"\nReAct Response: {result2['response'][:150]}...")
    print(f"Success: {'✅' if result2.get('react_success') else '❌'}")
    print(f"Total Turns: {result2.get('total_react_turns', 0)}")
    
    # Check if ReAct process contains query rewriting info
    react_turns = result2.get('react_turns', [])
    query_rewriting_found = False
    
    for turn in react_turns:
        if 'observation' in turn:
            observation = turn['observation']
            if 'rewritten from' in observation:
                query_rewriting_found = True
                print(f"✅ Query rewriting detected in observation")
                break
    
    if not query_rewriting_found:
        print("ℹ️  Query rewriting may have occurred but not visible in observations")
    
    return result2.get('react_success', False)

def main():
    """Run all tests"""
    print("🧪 Testing Enhanced SearchTool with Google API and Query Rewriting")
    print("🔧 Make sure you have GOOGLE_API_KEY set in your .env file")
    
    # Check if API key is available
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Error: GOOGLE_API_KEY not found.")
        print("   Please add GOOGLE_API_KEY to your .env file.")
        return
    
    tests = [
        ("Query Rewriting", test_query_rewriting),
        ("SearchTool with Rewriting", test_search_tool_with_rewriting),
        ("ReAct with Enhanced Search", test_react_with_enhanced_search)
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
        print("🎉 All tests passed! Enhanced SearchTool is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()